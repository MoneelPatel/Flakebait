"""End-to-end check of the category-faithful shim (deviations.md #33), without an agent (no model calls).

Starts the real run topology for one instance and runs Maven in the agent's container the way an agent would:
the full module suite several times, the victim's class alone, and (OD) the suite with a fixed order. Prints,
per command, the test classes in the order Surefire ran them, how often the victim ran, and whether it failed;
then the oracle's draws.

Usage: uv run python scripts/check_faithful.py <instance> [--repeats 4]
"""
import argparse
import json
import re
import shlex

from flakebait.harness import Run, load_api_key, sh


def victim_result(run: Run, meta: dict) -> tuple[int, bool, list[str]]:
    """From the victim class's Surefire XML report: how many times the victim ran, whether any run failed, and
    every failing test of the module (class.method)."""
    cls, method = meta["victim"].split("#", 1)
    mod = "" if meta["module"] in (".", "") else meta["module"] + "/"
    xml = sh(["docker", "exec", run.names["agent"], "bash", "-c",
              f"cat /work/{mod}target/surefire-reports/TEST-*.xml 2>/dev/null"]).stdout
    runs = failed = 0
    failing = []
    for m in re.finditer(r'<testcase name="([^"]+)" classname="([^"]+)"[^>]*?(/>|>(.*?)</testcase>)', xml, re.S):
        bad = bool(m.group(4)) and re.search(r"<(failure|error)\b", m.group(4)) is not None
        if bad:
            failing.append(m.group(2).rsplit(".", 1)[-1] + "." + m.group(1))
        if m.group(2) == cls and m.group(1) == method:
            runs += 1
            failed += bad
    return runs, failed > 0, sorted(set(failing))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("instance")
    ap.add_argument("--repeats", type=int, default=4)
    args = ap.parse_args()
    load_api_key()      # the meter needs it to start; no model call is made
    run = Run(args.instance, l3=False, run_id=f"check-faithful-{args.instance}")
    meta = run.meta
    pl = "" if meta["module"] in (".", "") else f"-pl {shlex.quote(meta['module'])} "
    cls = meta["victim"].split("#", 1)[0].rsplit(".", 1)[-1]
    cmds = [f"mvn test {pl}"] * args.repeats + [f"mvn test {pl}-Dtest={cls}"] * 2
    if meta["category"] == "OD":
        cmds.append(f"mvn test {pl}-Dsurefire.runOrder=alphabetical")
    run.prepare()
    print("shim:", run.record["shim"])
    try:
        run.start()
        for cmd in cmds:
            sh(["docker", "exec", run.names["agent"], "bash", "-c", "rm -rf /work/*/target/surefire-reports "
                "/work/target/surefire-reports"])
            r = sh(["docker", "exec", "-w", "/work", run.names["agent"], "bash", "-lc", cmd], timeout=1800)
            out = r.stdout + r.stderr
            order = [l.split("Running ", 1)[1].strip().rsplit(".", 1)[-1] for l in out.splitlines()
                     if "] Running " in l or l.startswith("Running ")]
            n, failed, failing = victim_result(run, meta)
            print(f"\n$ {cmd}\n  victim executions: {n}  victim failed: {failed}")
            print(f"  failing tests ({len(failing)}): {', '.join(failing[:8])}")
            vic = meta["victim"].split("#", 1)[0].rsplit(".", 1)[-1]
            pol = (meta.get("polluter") or "#").split("#", 1)[0].rsplit(".", 1)[-1]
            if pol and vic in order:
                print(f"  polluter {pol} ran before the victim: {pol in order[:order.index(vic)]}")
    finally:
        run.stop()
    print("\noracle draws:")
    for line in (run.dir / "oracle" / "oracle_log.jsonl").read_text().splitlines():
        rec = json.loads(line)
        if rec.get("event") in ("draw", "exec", "oracle_error"):
            print(" ", {k: rec[k] for k in rec if k in ("event", "rule", "order_seed", "repeat", "u", "verdict",
                                                       "native", "error")})


if __name__ == "__main__":
    main()
