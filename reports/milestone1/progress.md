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
- Phase 1: candidate order; eligibility walker with all checks. First pass finished on Oct 23 (15.3 h): TD 1,
  NIO 4, OD 0, ID 10. Two problems found in it and fixed (deviations #17, #18): the custom OD Surefire crashed on
  whole-suite runs (all 126 OD rejected at (f)), and the caps keyed on ReproFlake's project names (4 NIO tests
  from one junit-quickcheck module). Second pass running: cached evaluations replay; OD is evaluated anew.
- Phase 2: reproduction of both configurations for all four categories; shim (`fb-ext` + oracle); end-to-end
  relay checks per category (`shim_e2e.csv`).
- Phase 3: coverage, mutator, seeding, instance builder, validation, success checker; all built pilot
  instances valid (`instance_validation.csv`).
- Phase 4: harness (agent image, allow-list proxy, oracle sidecar, L3 CI phase); isolation checks.
- Phase 5/6: exposure detector; pilot with Claude Code (default model): 24 runs, $16.90, before the fixes.
- Phase 7: report builder.

## Open
- OD selection (second pass) and the OD pilot tests (3 tests, 12 runs) follow automatically
  (`flakebait.pilot_auto`, budget $50 hard: `--max-budget-usd 4` per phase, $8 reserved per run).
- TD (1/10) and NIO (1/10) shortfalls are final: every candidate was examined; no backfill.
