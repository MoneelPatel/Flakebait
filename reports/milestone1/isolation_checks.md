# Isolation checks

Instance: `repair-nio-quickcheckc1c19-L2-flaky`. Run from inside the agent's container with the full run topology (agent, oracle, proxy on an internal Docker network).

| Check | Result | Evidence |
|---|---|---|
| direct internet access fails | PASS | `rc=6` |
| Maven Central unreachable | PASS | `000` |
| meter forwards only to the OpenAI API (any Host header) | PASS | `{<br>  "object": "list",<br>  "data": [<br>    {<br>      "id": "gpt-5.4-mini",<br>      "object": "model",<br>      "created": 1773451123,<br>      "owned_by": "system",<br>      "shutdown_date": null<br>    },<br>    {<br>      "id": "o1-pro",<br>      "object": "model",<br>      "created": 1742251791,<br>      "owned_by": "system",` |
| real API key not in the agent's environment | PASS | `0<br>placeholder-only` |
| Maven cannot download (online settings forced) | PASS | `rc=1` |
| git history has exactly one commit | PASS | `1` |
| developer fix not reachable through git | PASS | `1<br>0` |
| hidden metadata not visible | PASS | `ls: cannot access '/oracle': No such file or directory<br>ls: cannot access '/opt/fb/py': No such file or directory` |
| agent's web search disabled | PASS | `codex exec ... -c web_search="disabled"` |
| (discoverable) which mvn | n/a | `/usr/local/bin/mvn<br>/usr/local/bin/mvn` |
| (discoverable) Maven lib/ext | n/a | `fb-ext.jar<br>README.txt` |
| (discoverable) oracle and meter hostnames resolve | n/a | `172.18.0.3      fb-oracle<br>172.18.0.2      fb-meter` |
| (discoverable) mvn wrapper | n/a | `ensed console output (installed ahead of Maven on PATH; see mvn_condense.py).<br># FB_MVN_PROPS carries properties the module needs to build offline in this environment (repro.BUILD_MODES).<br>set -o pipefail<br>/usr/share/maven/bin/mvn ${FB_MVN_PROPS} "$@" 2>&1 \| python3 -u /usr/local/lib/fb/mvn_condense.py` |

Rows marked *(discoverable)* record what an agent could find about the interception machinery. They are not failures; trajectories are checked for such probing (`exposure.py`).
