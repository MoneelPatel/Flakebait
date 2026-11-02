# Response to the Milestone 1 feedback

Changes made in response to the feedback of Oct 25, with the design decisions recorded as deviations #32-#36
(`reports/milestone1/deviations.md`). Main-study numbers come from `main_runs.csv` (168 runs, Nov 2); the tables are in `main_results.md` and the
findings in `findings.md`.

## 1. Beyond mutation: realistic bugs and bug reports

**What current benchmarks do.** SWE-bench (and SWE-bench-java/Multi-SWE-bench), Defects4J and GitBug-Java use
real bug-fix commits: the task is the pre-fix code plus the real issue text, success is the fix's tests passing.
SWE-smith and R2E-Gym scale this up synthetically: they revert real fix commits ("PR mirror"), or have a language
model rewrite a function to introduce a bug, then have a model write the issue from the bug and the failing tests,
describing the symptom rather than pasting test output.

**What Flakebait does now** (`flakebait/bugs.py`, deviation #32). For each selected flaky test, the fault is the
first that passes the seeding filters from:

1. a **real bug-fix commit** in the upstream repository's history before ReproFlake's snapshot, reverted on the
   target class (whole commit, or one hunk if the whole no longer applies);
2. a **bug written by GPT-6 Luna** in a method the flaky test covers (a plausible developer mistake: wrong
   boundary, missed case, wrong default, misused API), up to 3 rounds, each told why earlier bugs were rejected;
3. the PIT mutant from Milestone 1, as a last resort.

The filters are unchanged in substance: the fault compiles, is detected by at least two deterministic tests
(one in the flaky test's class, failing when that class runs alone), and leaves the flaky test's behavior
unchanged 20/20.

**What the bug report looks like.** The model writes a GitHub-style issue from the fault's diff, the detecting
tests' failure messages, and, for reverted commits, the original commit message and linked issue: what the user
did, what they expected, what happened. Rules, checked automatically (`bugs.issue_problems`) with up to three
rewrites: no test output, no test names, no location or quoted code from the fault, no fix, no flakiness terms,
and no invented values. The prompt is that issue plus one line naming the test that reproduces it (needed for the
exposure level). Example (ormlite-core, LLM-written fault):

> **Custom database column names are ignored**
> When I map a field to a database column whose name differs from the Java field name, ORMLite appears to use the
> Java name instead of the configured column name. [...] With this mapping, I expect persistence operations to use
> `display_name`. Instead, they look for a column based on `name`, and database operations fail [...]

**Finding.** Few real fix commits survive: most fix-like commits touching the target class are performance or
documentation changes, no longer apply to the snapshot, or are not detected by the module's tests. Fault kinds per
test are in `data/bugs/*.json` and the instance manifest. Final counts: all 28 tests got an LLM-written bug; no
reverted fix commit and no mutant was needed.

## 2. What counts as success, and what if the agent may not touch tests

**Success is behavioral, not textual.** The check never compares the agent's change with the original code. It
copies the agent's final tree, replaces the module's tests with the pristine originals, and runs the full suite
under the passing configuration with the flaky test excluded. The task succeeds if every detecting test (named and
held out) and every other deterministic test passes. Any change that achieves this counts, including a different
fix in a different place. Restoring the pristine tests prevents "fixing" the task by editing tests.

**Tests locked** (deviation #34). The prompt study (RQ4) adds a third variant, *locked*: "Do not modify any test
code (files under src/test); fix the bug in the production code." The outcome classifiers still detect test edits,
so we measure: compliance, whether the agent then recognizes the flaky failure and reports it, whether it damages
production code trying to make the flaky test pass, and whether it gives up at the caps (turn cap hits, time cap
hits, runs ending without a fix) _(prompt study, Milestone 3)_.

## 3. Open-source / local models, and resources

**Cost is not the binding constraint with Codex on GPT-6 Luna.** The pilot's 36 valid runs cost $1.02 (mean $0.028 per
run, max $0.06; most input tokens are cached at $0.01/M). The whole design (168 main-study runs + 252 prompt-study
runs + judging) projects to about $15-25 of the $100 budget. The university's resources are therefore sufficient
for the Codex study as designed; the limits are local compute (Maven builds and reproductions) and time.

**Local arm** (deviation #35). Codex CLI runs against `gpt-oss:20b` served by Ollama on the M1 Pro (32 GB), through
the same meter (calls logged at price 0), on the 9 pilot tests at L2, both arms. It answers whether the setup works
with an open-weight model. Result (18 runs, Nov 2): the pipeline works end to end with a local model, but
Ollama could not parse gpt-oss:20b's file-edit tool calls, so no run made an edit (`findings.md`); a different
model server or model is needed before a comparison. It is slow (one run at a time;
the model and the build containers share 32 GB), so a full open-model arm would need a GPU server.

## 4. Effectiveness per category, and whether the setup is realistic

**Per-category breakdown.** The pilot (Milestone 1) by category, L2 flaky arm: observed exposure ID 2/3, OD 3/3,
NIO 2/2, TD 1/1; at L1: ID 0/3, OD 1/3, NIO 0/2, TD 0/1. All main-study tables are per category (`main_results.md`). Main study, flaky arm: the failure was recognized as
unrelated in 79% of exposed main phases and 91% of exposed L3 phases, and fixed at the root in 74% of exposed
runs. NIO is the hardest: half its runs hit the turn cap, and 5/30 ended with the agent undoing its own correct
fix (`findings.md`).

**Realism: the category-faithful shim** (deviation #33). In Milestone 1 the shim decided the flaky test's outcome
by a random draw, no matter how the agent ran its tests. That is realistic for ID (hash/iteration order varies
between JVMs) and TD (timing), but not for OD and NIO, whose failures depend on *how* the tests are run. Now:

- **OD.** Every Maven run gets a seeded random test-class order (as CI systems with shuffled or filesystem-dependent
  order do), and the failure occurs only when the polluter really ran before the victim in that JVM. Running the
  test alone passes; the agent can see the order in Surefire's output ("Running ..." lines) and control it with
  `-Dtest` or `-Dsurefire.runOrder`.
- **NIO.** With probability 0.5 per Maven run, the test runs twice in the JVM, and both executions are reported
  (the class's "Tests run" count includes both), so the agent can notice the repetition.

The agent's explicit choices always take precedence, so it *has* the control the feedback asks about; whether it
uses it is part of RQ1/RQ3 (trajectory analysis of order- and repetition-related reasoning). It mostly does not:
at L2 the agent runs the named class alone, so OD failed in only 3/21 main phases (ID 24/27, NIO 27/30), and
then in 21/21 full-suite CI runs.

**A finding on OD realism.** A fully native shuffled order almost never reproduced ReproFlake's OD failure: for
ormlite-core, the victim passed in all five random orders in which the polluter ran first, because tests between
the polluter and the victim (or the polluter's own class) reset the shared state. ReproFlake's failing
configuration (polluter immediately followed by victim) is therefore much rarer in realistic full-suite runs than
the dataset suggests. We keep the validated failing configuration, conditioned on the polluter really running
first.

## 5. ReproFlake issues

Drafted for the maintainers in `reports/milestone2/reproflake_issues.md`: a confirmed crash of the custom OD
Surefire on any run without `-Dtest` (all 126 OD entries; patch included), an archive without a Maven repository,
archives missing artifacts needed offline, index labeling issues, and lists of entries whose fix or failing
configuration did not reproduce in our environment (to be checked on ReproFlake's reference setup before being
called bugs).
