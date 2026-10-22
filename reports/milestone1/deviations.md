# Milestone 1 deviations

| # | Deviation | Reason | Impact |
|---|-----------|--------|--------|
| 1 | The single index row labelled `britle` is counted as OD. | The ReproFlake index has 125 `od` + 1 `britle`; the paper reports 126 OD. | Counts match the proposal (819/126/125/36, 9 unclassified excluded). |
| 2 | Builds and runs on an Apple M1 (arm64) Mac, not a Linux amd64 server. | No server available for Milestone 1. | Java 8 images use `maven:3.8.6-eclipse-temurin-8` (native arm64) in place of ReproFlake's `maven:3.8.6-openjdk-8`. A test that fails a 20/20 check gets one retry under amd64 emulation of the original image before rejection. TD timing results carry a platform caveat. |
| 3 | ReproFlake zips are downloaded lazily, in shuffled candidate order, not as the full 44 GB bundle. | Disk space (137 GB free). | None on selection: candidates are still examined strictly in shuffled order. |
