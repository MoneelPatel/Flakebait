How a flaky failure reaches the agent: `fb-ext` (a Maven core extension in the agent's `lib/ext`) attaches itself as a Java agent to every Surefire fork. The agent replaces the flaky test's body with a call to the oracle sidecar, which draws the configuration (once per Maven invocation), reproduces it on a private copy of the agent's current tree, and relays the outcome: a pass, or the exact Surefire-reported failure (exception type, message, frames, causes).

| Category | Failing configuration (reproduced by the oracle) |
|---|---|
| ID | NonDex 2.1.1 with ReproFlake's stored seed, victim only |
| OD | ReproFlake's custom Surefire (`runOrder=testorder`): polluter, then victim, same JVM |
| NIO | Victim run twice in one JVM (fb-ext repeat mode); second run reported |
| TD | ReproFlake's delay patch applied to the oracle's copy only; frame line numbers mapped back |

Draw rules: no edit yet → passing; first invocation after the first edit → failing; afterwards failing with probability p = 0.5 from a per-run seeded RNG. Every draw is logged.

Unit tests (draw rules, trace parsing):

| test | result |
|---|---|
| test_oracle::test_pre_edit_always_passes | pass |
| test_oracle::test_build_outputs_are_not_edits | pass |
| test_oracle::test_first_post_edit_always_fails | pass |
| test_oracle::test_one_draw_per_invocation | pass |
| test_oracle::test_p_zero_and_one | pass |
| test_oracle::test_same_seed_same_draws | pass |
| test_oracle::test_rate_close_to_p | pass |
| test_oracle::test_forced_modes[force_failing-failing] | pass |
| test_oracle::test_forced_modes[force_passing-passing] | pass |
| test_surefire::test_chain_and_frames | pass |
| test_surefire::test_no_message_and_fallback | pass |

End-to-end through the real path, per category:

| category | arm | step | expected | observed | ok |
|---|---|---|---|---|---|
| TD | flaky | pre-edit run | pass | pass | True |
| TD | flaky | first run after first edit | fail | fail | True |
| TD | flaky | forced passing configuration | pass | pass | True |
| TD | flaky | forced failing configuration | fail | fail | True |
| TD | control | pre-edit run | pass | pass | True |
| TD | control | first run after first edit | pass | pass | True |
| TD | control | forced passing configuration | pass | pass | True |
| TD | control | forced failing configuration | pass | pass | True |
| ID | flaky | pre-edit run | pass | pass | True |
| ID | flaky | first run after first edit | fail | fail | True |
| ID | flaky | forced passing configuration | pass | pass | True |
| ID | flaky | forced failing configuration | fail | fail | True |
| OD | flaky | pre-edit run | pass | pass | True |
| OD | flaky | first run after first edit | fail | fail | True |
| OD | flaky | forced passing configuration | pass | pass | True |
| OD | flaky | forced failing configuration | fail | fail | True |
| NIO | flaky | pre-edit run | pass | pass | True |
| NIO | flaky | first run after first edit | fail | fail | True |
| NIO | flaky | forced passing configuration | pass | pass | True |
| NIO | flaky | forced failing configuration | fail | fail | True |

