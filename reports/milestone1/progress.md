# Milestone 1 progress

## Done
- Phase 0: environment checked and tooling approved (Python + uv; Java 8 target for Java components; temurin images on arm64).
- ReproFlake index and scripts fetched to `data/reproflake/meta/` (not committed).
- Seeds fixed in `config/seeds.yaml`.
- `selection/candidates.py`: category counts (`category_counts.csv`, all match) and per-category seeded candidate order (`candidate_order.csv`).
- `scripts/prefetch_zips.py`: background download of the first 15 distinct zips per category (all TD zips). Log at `data/prefetch.log`.

## Next
1. Build the base images (temurin 8/11/17 + ReproFlake tooling: NonDex, custom Surefire for OD).
2. `selection/eligibility.py`: walk `candidate_order.csv`, check caps → (a) → (f) → (e) → (b) → (c) → (d), and write `selection_log.csv`.
3. Shim + TD agent (Phase 2), then seeding (Phase 3).
