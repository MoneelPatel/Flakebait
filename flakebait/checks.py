"""End-to-end checks of the run topology, without an agent (no API calls).

isolation   from inside the agent's container: no network except the model API through the proxy, Maven
            cannot download, one commit in git history, no hidden metadata visible; plus what an agent
            could find about the shim (recorded, not hidden).
shim        through the real path (agent container -> fb-ext -> oracle -> reproduction -> relay):
            pre-edit run passes, first run after an edit fails with the real failure, forced passing passes,
            forced failing fails; relayed failure text matches the direct reproduction.

Usage: uv run python -m flakebait.checks --instances <id> [<id> ...]
Writes reports/milestone1/isolation_checks.md and reports/milestone1/shim_e2e.csv.
"""
import argparse
import csv
import json
import re
import shlex

from . import paths
from .harness import ORACLE_PORT, Run, sh

ISOLATION = [
    ("direct internet access fails", "curl -s -m 8 --noproxy '*' https://example.com -o /dev/null; echo rc=$?",
     lambda o: "rc=0" not in o),
    ("proxy refuses other hosts", "curl -s -m 8 -o /dev/null -w '%{http_code}' https://example.com; echo; true",
     lambda o: "000" in o or "403" in o),
    ("proxy refuses Maven Central", "curl -s -m 8 -o /dev/null -w '%{http_code}' https://repo1.maven.org/maven2/; echo",
     lambda o: "000" in o or "403" in o),
    ("model API reachable through proxy", "curl -s -m 15 -o /dev/null -w '%{http_code}' https://api.anthropic.com/v1/models; echo",
     lambda o: o.strip()[:3] in ("200", "401", "403", "404", "405")),
    ("Maven cannot download (online settings forced)",
     "printf '<settings><offline>false</offline></settings>' > /tmp/online.xml; "
     "mvn -B -q -s /tmp/online.xml dependency:get -Dartifact=org.example:does-not-exist:1.0 >/tmp/mvn.log 2>&1; "
     "echo rc=$?; grep -m1 -oE 'Unknown host|Could not transfer|Network is unreachable|Could not resolve|offline' /tmp/mvn.log",
     lambda o: "rc=0" not in o),
    ("git history has exactly one commit", "cd /work && git log --oneline | wc -l", lambda o: o.strip() == "1"),
    ("developer fix not reachable through git", "cd /work && git log --all --oneline | wc -l; git stash list | wc -l",
     lambda o: o.split() == ["1", "0"]),
    ("hidden metadata not visible",
     "ls -d /oracle /opt/fb/py 2>&1; find / -xdev \\( -name meta.json -o -name oracle_log.jsonl -o -name delay.patch "
     "-o -name Fixed.patch -o -name reference_source.txt \\) 2>/dev/null | head",
     lambda o: "meta.json" not in o and "oracle_log" not in o and "Fixed.patch" not in o
     and "No such file" in o),
]
DISCOVERABLE = [
    ("which mvn", "which mvn; readlink -f $(which mvn)"),
    ("Maven lib/ext", "ls /usr/share/maven/lib/ext"),
    ("oracle hostname resolves", "getent hosts fb-oracle || echo unresolved"),
]


def isolation(instance: str) -> list[dict]:
    run = Run(instance, mode="force_passing", l3=False, run_id=f"check-isolation-{instance}")
    run.prepare()
    rows = []
    try:
        run.start()
        for name, cmd, ok in ISOLATION:
            r = sh(["docker", "exec", run.names["agent"], "bash", "-lc", cmd], timeout=300)
            out = (r.stdout + r.stderr).strip()
            rows.append({"check": name, "pass": bool(ok(out)), "output": out[-300:]})
        rows.append({"check": "agent's web tools disabled", "pass": "--disallowedTools" in " ".join(
            run.agent_cmd("x", None)) and "WebSearch,WebFetch" in run.agent_cmd("x", None),
            "output": "claude ... --disallowedTools WebSearch,WebFetch"})
        for name, cmd in DISCOVERABLE:
            r = sh(["docker", "exec", run.names["agent"], "bash", "-lc", cmd], timeout=60)
            rows.append({"check": f"(discoverable) {name}", "pass": None, "output": (r.stdout + r.stderr).strip()[-300:]})
    finally:
        run.stop()
    return rows


def _mvn_victim(run: Run) -> tuple[str, str]:
    m = run.meta["module"]
    cls = run.meta["victim"].split("#", 1)[0]
    pl = f"-pl {shlex.quote(m)} " if m not in (".", "") else ""
    r = sh(["docker", "exec", run.names["agent"], "bash", "-lc",
            f"cd /work && mvn -B -Dstyle.color=never {pl}test -Dtest={shlex.quote(cls)} -DfailIfNoTests=false"],
           timeout=3600)
    out = r.stdout + r.stderr
    method = run.meta["victim"].split("#", 1)[1]
    failed = bool(re.search(rf"{re.escape(method)}.*(FAILURE|ERROR)!", out)) or \
        bool(re.search(rf"(Failures|Errors):.*\n(.*\n)*?.*{re.escape(method)}", out))
    return ("fail" if failed else "pass"), out


def _set(run: Run, phase: str, mode: str) -> None:
    run.oracle_phase(phase, mode)


def shim(instance: str) -> list[dict]:
    """Agent-mode rules, then forced modes, through the real interception path."""
    run = Run(instance, mode="agent", p=0.5, l3=False, run_id=f"check-shim-{instance}")
    run.prepare()
    rows = []
    try:
        run.start()
        got, _ = _mvn_victim(run)
        rows.append({"instance": instance, "step": "pre-edit run", "expected": "pass", "observed": got})
        # A harmless edit: a trailing newline in the target class's source file. (A new file would also count
        # as an edit, but license checks such as Apache RAT fail the build on unknown files.)
        sh(["docker", "exec", run.names["agent"], "bash", "-lc", f"echo >> /work/{shlex.quote(run.meta['source'])}"])
        got, out = _mvn_victim(run)
        # The control arm carries the developer fix, so its failing configuration passes.
        failing_expect = "pass" if run.meta["arm"] == "control" else "fail"
        rows.append({"instance": instance, "step": "first run after first edit", "expected": failing_expect,
                     "observed": got,
                     "failure_excerpt": _excerpt(out, run.meta["victim"])})
        _set(run, "check", "force_passing")
        got, _ = _mvn_victim(run)
        rows.append({"instance": instance, "step": "forced passing configuration", "expected": "pass", "observed": got})
        _set(run, "check2", "force_failing")
        got, out = _mvn_victim(run)
        rows.append({"instance": instance, "step": "forced failing configuration",
                     "expected": failing_expect, "observed": got,
                     "failure_excerpt": _excerpt(out, run.meta["victim"])})
    finally:
        run.stop()
    for r in rows:
        r["category"] = run.meta["category"]
        r["arm"] = run.meta["arm"]
        r["ok"] = r["expected"] == r["observed"]
    return rows


def _excerpt(out: str, victim: str) -> str:
    method = victim.split("#", 1)[1]
    lines = out.splitlines()
    for i, l in enumerate(lines):
        if method in l and ("FAILURE" in l or "ERROR" in l):
            return "\n".join(lines[i:i + 4])[:600]
    return ""



def write_isolation(rows: list[dict], instance: str) -> None:
    lines = ["# Isolation checks", "", f"Instance: `{instance}`. Run from inside the agent's container with the full "
             "run topology (agent, oracle, proxy on an internal Docker network).", "",
             "| Check | Result | Evidence |", "|---|---|---|"]
    for r in rows:
        res = "n/a" if r["pass"] is None else ("PASS" if r["pass"] else "FAIL")
        ev = r["output"].replace("|", "\\|").replace("\n", "<br>")
        lines.append(f"| {r['check']} | {res} | `{ev}` |" if ev else f"| {r['check']} | {res} | |")
    lines += ["", "Rows marked *(discoverable)* record what an agent could find about the interception machinery. "
              "They are not failures; trajectories are checked for such probing (`exposure.py`)."]
    (paths.REPORTS / "isolation_checks.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", nargs="+", required=True)
    ap.add_argument("--skip-isolation", action="store_true")
    args = ap.parse_args()
    if not args.skip_isolation:
        rows = isolation(args.instances[0])
        write_isolation(rows, args.instances[0])
        print(json.dumps(rows, indent=1))
    all_rows = []
    for inst in args.instances:
        rows = shim(inst)
        all_rows += rows
        print(json.dumps(rows, indent=1), flush=True)
    path = paths.REPORTS / "shim_e2e.csv"
    # Merge with earlier runs of this check (one instance per category is checked separately).
    if path.exists():
        done = {r["instance"] for r in all_rows}
        all_rows = [r for r in csv.DictReader(open(path)) if r["instance"] not in done] + all_rows
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["instance", "category", "arm", "step", "expected", "observed", "ok",
                                          "failure_excerpt"], extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)


if __name__ == "__main__":
    main()
