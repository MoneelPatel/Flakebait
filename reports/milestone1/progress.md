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
uv run python -m flakebait.pilot --plan                 # then, after approval:
ANTHROPIC_API_KEY=... uv run python -m flakebait.pilot --run --budget 50
uv run python analysis/build_milestone1_report.py       # regenerates reports/milestone1/README.md
```

Logs of long jobs: `data/logs/` (`selection.log`, `validate-*.log`).

## Done
- Phase 0: environment checked; tooling approved (Python + uv, Java 8 target, temurin images on arm64).
- Phase 1 code: candidate order, eligibility walker with all checks; selection running.
- Phase 2: reproduction of both configurations for all four categories, verified on one test per category;
  shim (`fb-ext` + oracle) with draw-rule unit tests; end-to-end relay verified on an ID test (flaky and
  control arms: pre-edit pass, first post-edit failure with the exact NonDex failure, forced modes).
- Phase 3 code: coverage, mutator, seeding, instance builder, validation, success checker; seeding verified
  end to end (commons-lang, HADOOP-10394).
- Phase 4: harness (agent image, allow-list proxy, oracle sidecar, L3 CI phase); isolation checks pass.
- Phase 5: exposure detector. Phase 7: report builder.

## Open
- Selection to finish (all categories); then pilot instances, validation, per-category shim checks.
- Pilot needs approval of the run plan and cost (model choice, budget), and `ANTHROPIC_API_KEY`.
- The harness has not yet run a real agent (no API calls made so far).
