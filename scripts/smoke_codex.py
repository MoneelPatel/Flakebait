"""Smoke test: one tiny Codex CLI task through the meter, in the agent image, on an internal network.

Checks the model id, the meter's key swap, usage logging and pricing. Its cost is logged like any run
(runs/smoke-*/meter/meter_log.jsonl), so it counts toward the study budget.

Usage: uv run python scripts/smoke_codex.py
"""
import json
import sys
import time
import uuid

from flakebait import paths
from flakebait.harness import CAPS, METER_PORT, PLACEHOLDER_KEY, STUDY, Run, load_api_key, sh, study_spend


def main() -> None:
    if not load_api_key():
        raise SystemExit("OPENAI_API_KEY is not set (environment or .env)")
    if study_spend() + CAPS["usd_per_run"] > CAPS["study_stop_usd"]:
        raise SystemExit("study budget reached")
    tag = uuid.uuid4().hex[:8]
    d = paths.RUNS / f"smoke-{time.strftime('%Y%m%d-%H%M%S')}"
    (d / "meter").mkdir(parents=True)
    (d / "work").mkdir()
    (d / "work" / "hello.txt").write_text("hello\n")
    sh(["git", "-C", str(d / "work"), "init", "-q"])
    sh(["git", "-C", str(d / "work"), "-c", "user.email=fb@example.com", "-c", "user.name=fb", "add", "-A"])
    sh(["git", "-C", str(d / "work"), "-c", "user.email=fb@example.com", "-c", "user.name=fb", "commit", "-qm", "init"])
    run = Run.__new__(Run)          # reuse the harness's command line and meter settings
    run.model = STUDY["model"]
    net, meter, agent = f"fbnet-{tag}", f"fb-meter-{tag}", f"fb-agent-{tag}"
    pr = STUDY["prices"]
    try:
        sh(["docker", "network", "create", "--internal", net]).check_returncode()
        sh(["docker", "run", "-d", "--rm", "--name", meter, "--network", net, "--network-alias", "fb-meter",
            "-v", f"{paths.ROOT / 'docker' / 'meter.py'}:/meter.py:ro",
            "--mount", f"type=bind,source={d / 'meter'},target=/meter",
            "-e", "OPENAI_API_KEY", "-e", "TURN_CAP=5", "-e", "RUN_CAP_USD=0.05",
            "-e", f"PRICE_INPUT={pr['input']}", "-e", f"PRICE_CACHED={pr['cached_input']}",
            "-e", f"PRICE_CACHE_WRITE={pr['cache_write']}", "-e", f"PRICE_OUTPUT={pr['output']}", "fb-base:8", "python3", "-u", "/meter.py", str(METER_PORT)]
           ).check_returncode()
        sh(["docker", "network", "connect", "bridge", meter]).check_returncode()
        sh(["docker", "run", "-d", "--rm", "--name", agent, "--network", net, "-e", f"CODEX_API_KEY={PLACEHOLDER_KEY}",
            "--mount", f"type=bind,source={d / 'work'},target=/work", "fb-agent:8", "sleep", "infinity"]
           ).check_returncode()
        time.sleep(2)
        cmd = run.agent_cmd("Run `cat hello.txt` and reply with its contents only.", None)
        p = sh(["docker", "exec", "-w", "/work", agent, *cmd], timeout=300)
        (d / "trajectory_main.jsonl").write_text(p.stdout)
        print("rc", p.returncode)
        print("stderr tail:", p.stderr[-1500:])
        for line in p.stdout.splitlines():
            ev = json.loads(line)
            if ev.get("type") in ("thread.started", "turn.completed", "turn.failed", "error") or \
               (ev.get("type") == "item.completed" and (ev.get("item") or {}).get("type") in ("agent_message", "command_execution")):
                print(json.dumps(ev)[:400])
        # Isolation: the agent's container must not reach the internet directly.
        r = sh(["docker", "exec", agent, "bash", "-c", "curl -s -m 5 -o /dev/null -w '%{http_code}' https://api.openai.com/v1/models || echo BLOCKED"])
        print("direct internet from agent:", r.stdout.strip())
    finally:
        sh(["docker", "rm", "-f", meter, agent])
        sh(["docker", "network", "rm", net])
    print("meter log:")
    print((d / "meter" / "meter_log.jsonl").read_text())
    print(f"study spend ${study_spend():.6f}")
    sys.exit(0)


if __name__ == "__main__":
    main()
