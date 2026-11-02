# Milestone 1 progress

## Pipeline (commands, in order)

```bash
scripts/build_java.sh                                   # fb-ext, fb-tools, jacoco agent, od-ext -> data/jars
for v in 8 11 17; do
  docker build -f docker/Dockerfile.base  --build-arg JAVA=$v -t fb-base:$v  docker
  docker build -f docker/Dockerfile.agent --build-arg JAVA=$v -t fb-agent:$v docker
done
uv run python -m flakebait.candidates                   # category counts + seeded candidate order
FB_MEM=3500m uv run python -m flakebait.selection --workers 2   # long; resumable (data/evaluations cache)
uv run python -m flakebait.instances --pilot            # 10 pilot tests x L1/L2 x flaky/control
uv run python -m flakebait.evaluation --validate        # instance_validation.csv
uv run python -m flakebait.checks --instances <one flaky instance per category> <a control instance>
uv run python scripts/smoke_codex.py                   # one metered Codex call (OPENAI_API_KEY in .env)
uv run python -m flakebait.pilot --plan                 # then:
uv run python -m flakebait.pilot --run                  # or unattended: python -m flakebait.pilot_auto
uv run python analysis/build_milestone1_report.py       # regenerates reports/milestone1/README.md
```

Logs of long jobs: `data/logs/` (`selection.log`, `validate-*.log`).

## Done
- Phase 0: environment checked; tooling approved (Python + uv, Java 8 target, temurin images on arm64).
- Phase 1: candidate order; eligibility walker with all checks. Final pass finished Oct 25 (24.6 h, cached
  evaluations reused): **28 tests: TD 1, NIO 10, OD 7, ID 10** (`selected_tests.csv`). Caps were relaxed with the
  project owner: class cap for TD/NIO (#20) and OD (#30), no cap for NIO (#31). TD (1/10) and OD (7/10)
  shortfalls are final: every candidate was examined; no backfill. Earlier passes' logs: `data/logs/before-od-classcap/`.
- Phase 2: reproduction of both configurations for all four categories; shim (`fb-ext` + oracle) with condensed
  Maven output; end-to-end relay checks per category (`shim_e2e.csv`).
- Phase 3: coverage, mutator, seeding, instance builder, validation, success checker; 36 pilot instances
  (9 tests x L1/L2 x flaky/control), all valid (`instance_validation.csv`).
- Phase 4: Codex CLI 0.163.0 harness on gpt-6-luna (metering proxy, oracle sidecar, L3 CI phase); isolation
  checks all pass (`isolation_checks.md`).
- Phase 5/6: exposure detector; **Codex pilot: 36 valid runs on 9 tests, $1.15 total study spend** (mean $0.028
  per run). Decisions (`pilot_decision.md`): main study at **L2** (L1 exposure 1/9, L2 8/9); model **kept**
  (control success 16/18); projected 480 remaining runs about $14.
- Phase 7: report builder.

## Observations to carry forward
- 14/36 pilot runs hit the 30-call turn cap, 12 of them on the flaky arm (2 on control): the agent spends its
  calls on the flaky failure. Cost is not a concern (max $0.06 per run), so the cap is not cut; RQ analyses should
  report capped runs separately.
- The pilot has 9 tests, not 10: TD has only one eligible test, so its second pilot slot is empty.
- `pilot_observations_claude_exploratory.md` describes the earlier Claude Code pilot, not the Codex runs.

## Open (Milestone 2)
- Build and validate instances for the remaining 19 selected tests (and control twins).
- Outcome classifiers, LLM judge and labeling guide; main study (240 runs at L2).
