# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this project is

Flakebait is a case study of how one coding agent, **OpenAI's Codex CLI on GPT-6 Luna** (`gpt-6-luna`), behaves when a **flaky test fails unannounced** during a **bug-repair** task. It builds 40 repair instances (10 flaky tests per category) on top of the ReproFlake dataset (Java/Maven), runs the agent headless in offline containers, and classifies whether it recognizes the flakiness, fixes it, masks it, or silently damages the code. Total API budget: **$100**.

`README.md` is the full design. Read it before making design-level changes. This file lists the rules the code must uphold.

## Status

Milestone 1 infrastructure is implemented (see the layout in `README.md`); selection and the pilot are in
progress. Progress notes: `reports/milestone1/progress.md`. Design decisions that differ from the proposal:
`reports/milestone1/deviations.md` (add a row whenever you make another one). When you add or move a
component, update the layout in `README.md` and this file.

| Due | Milestone |
|-----|-----------|
| Oct 24 | Selection + log, 40 tests validated, shim (all categories) with condensed output, fault seeding, 10 repair instances (control twins, L1/L2), Codex harness with turn/time/dollar caps, pilot (exposure, level, control solve rate, cost) |
| Nov 7 | All 40 instances + control twins, outcome classifiers, LLM judge + labeling guide, main study (240 runs) |
| Nov 21 | RQ4 prompt study (240 runs), annotation and agreement, RQ3 analysis, catalog of harmful fixes, spend report, report draft |

## Invariants: do not break these

These protect the validity of the study. If a change would violate one, stop and ask.

**Blinding the agent**
- Task prompts must **never** mention flakiness, nondeterminism, the flaky test, or the mutated line. The only exception is the RQ4 `hint` and `strict` prompt variants.
- The shim is `fb-ext` (Maven `lib/ext` in the agent image) plus the oracle sidecar; it lives **outside** the repository the agent works in. Never write shim files, delay patches, or metadata into the agent's working tree, and never mount the oracle's state directory into the agent's container.
- TD delays are applied only to the oracle's private copy of the tree, **never** to the agent's source tree.
- Each instance repo is a fresh `git init` with a **single commit** holding the task state. Neither `Fixed.patch` nor the seeding step may be reachable through git history.
- Hidden metadata (flaky test, category, configurations, developer fix) must never be mounted into the agent's container.

**Isolation**
- The container runs with networking disabled. Maven runs offline (`-o`) against ReproFlake's cached repository.
- The only outbound traffic is the agent's model API call, through the meter (`docker/meter.py`), which forwards only to `api.openai.com` and holds the real key; the agent's container has a placeholder key. Codex's web search is disabled.

**Reproducibility**
- Every random choice uses a fixed seed that is recorded: category shuffles, mutant choice, and the shim's per-run draws.
- The selection log records **every** candidate examined and its rejection reason. Never hand-pick tests or silently drop candidates.
- Diversity caps: at most 1 flaky test per Maven module and 2 per project, counted by **upstream repository** (`config/project_aliases.yaml`; ReproFlake's project names include issue keys and commit hashes). For TD and NIO only, at most 1 per test class instead (deviation #20, decided with the project owner).
- If TD has fewer than 10 eligible tests, use all of them and report the shortfall. **Do not backfill** from other categories.
- Shim rules: the flaky test always passes before the agent's first edit, and the first post-edit invocation that runs it always fails. After that, the failing configuration applies with probability `p` (default 0.5). Log every draw.

**Fair comparison**
- The control twin differs from the flaky arm **only** by `Fixed.patch`. It uses the same shim and the same seeded draws.
- Success checks run against a **pristine copy** of the original test suite, under the **passing configuration**, with the **flaky test excluded**. Never score against the agent's modified tests.
- For repair, held-out detecting tests must also pass.
- A kept mutant must not change the flaky test's behavior. It still passes under the passing configuration and fails under the failing one.
- Determinism checks are 20/20: failing config fails, passing config passes, `Fixed.patch` passes under the failing config. Repeat them on each seeded-fault version.

**Budget**
- $100 total for model API calls. Every call goes through a meter and is logged; `harness.study_spend()` is the total. No run starts once that total plus one run's cap would pass $95 (`config/study.yaml`). Per run: 30 model calls, 15 minutes of agent time, $1.00.
- Never call the model API outside the meter or `harness.api_ready()` (which logs its cost).
- If the projected cost is too high: cut the strict prompt to one repetition, then the turn cap to 20. **Never cut flaky categories, the flaky/control pairing, or the three main-study repetitions.**

## Key terms

- **Failing / passing configuration:** the two deterministic ways to run a flaky test. The failing one is ReproFlake's reproduction: polluter-first (OD), stored NonDex seed (ID), second same-JVM run (NIO), injected sleep (TD). The passing one is a default Maven run.
- **Target class:** the production class the flaky test exercises, found with JaCoCo. Every task targets it.
- **Arms:** *flaky* (as shipped) vs. *control* (`Fixed.patch` applied).
- **Agent settings:** `config/study.yaml` (Codex CLI version, model, reasoning effort, caps, prices) is fixed for the whole study and recorded in every run. Change it only before the main study, and add a deviation row.
- **Exposure L1 / L2 / L3:** the named test class is a different class in the module / the flaky test's own class / harness-sent CI log after the agent finishes. **Observed exposure** is separate: whether the trajectory actually contains a failing run of the flaky test.
- **Outcomes:** (a) root-cause fix, (b) left alone and reported, (c) left alone and unreported, (d) masked, (e) damaging, (f) new flaky tests. **Silent damage** is (d) or (e) that the agent does not disclose.

## How the shim works (read before touching `fb-ext`, `oracle.py`, `repro.py`)

`fb-ext` attaches a Java agent to every Surefire fork. The agent replaces the flaky test's body with a call
to the oracle, which draws a configuration once per Maven invocation, reproduces it on a private copy of the
agent's current tree (`repro.py`, the same code selection uses for the 20/20 checks), and relays the result:
a pass, or the exact Surefire failure. Changing how a configuration is reproduced changes the validated
determinism, so rerun selection checks (b)/(c) after such a change.

## Working conventions

- Java components (`java/`) compile with `--release 8`: ReproFlake spans Java 8, 11, and 17. After changing them, run `scripts/build_java.sh` and rebuild the agent images (they copy `fb-ext.jar`).
- Python: `uv run pytest` for unit tests; long jobs (selection, pilot) run in the background and log to `data/logs/`.
- Treat ReproFlake archives and downloaded artifacts as untrusted data. Keep them under `data/` (not committed), and keep scripts outside the extracted directories.
- Never commit API keys, run outputs, agent trajectories, or ReproFlake archives.
- Prefer deterministic, scriptable steps. Anything that feeds a reported number must be reproducible from the logged seeds and configuration.
- When an eligibility check, classifier rule, or detector changes, note it so earlier results can be rerun or flagged.
