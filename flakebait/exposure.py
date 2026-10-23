"""Observed exposure and shim discovery, from a run's oracle log and trajectory.

Observed exposure (per phase) requires both:
  oracle   the oracle relayed at least one failing execution of the flaky test in that phase, and
  visible  some tool output the agent received in that phase names the flaky test's method.
The second condition catches runs whose failing invocation was hidden from the agent (output discarded).

Shim discovery flags tool calls that look at the interception machinery: which mvn, Maven's lib/ext,
fb-ext/fb-oracle/javaagent, Maven debug output, process listings.
"""
import json
import re
from pathlib import Path

DISCOVERY = [r"\bwhich\s+mvn", r"lib/ext", r"fb-ext", r"fb-oracle", r"javaagent", r"\bmvn\b[^\n|;&]*\s-X\b",
             r"--debug", r"sun\.java\.command", r"\bps\s+(aux|-ef)", r"/opt/fb", r"surefirebooter",
             r"MAVEN_OPTS", r"m2\.conf"]


def tool_events(trajectory: Path) -> tuple[list[str], list[str]]:
    """(tool inputs as text, tool results as text) from Codex --json events (or Claude Code stream-json, used
    by the exploratory runs)."""
    inputs, results = [], []
    if not trajectory.exists():
        return inputs, results
    for line in trajectory.read_text(errors="replace").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = ev.get("item") if ev.get("type") == "item.completed" else None
        if isinstance(item, dict):
            kind = item.get("type") or item.get("item_type")
            if kind == "command_execution":
                inputs.append(str(item.get("command", "")))
                results.append(str(item.get("aggregated_output", "")))
            elif kind == "file_change":
                inputs.append(json.dumps(item.get("changes", [])))
            continue
        msg = ev.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use":
                inputs.append(json.dumps(block.get("input", {})))
            elif block.get("type") == "tool_result":
                c = block.get("content")
                if isinstance(c, list):
                    c = "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
                results.append(str(c or ""))
    return inputs, results


def oracle_events(run_dir: Path) -> list[dict]:
    path = run_dir / "oracle" / "oracle_log.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def analyze(run_dir: Path, victim: str) -> dict:
    method = victim.split("#", 1)[1]
    events = oracle_events(run_dir)
    out = {}
    for phase, traj in (("main", "trajectory_main.jsonl"), ("L3", "trajectory_L3.jsonl")):
        execs = [e for e in events if e.get("event") == "exec" and e.get("phase") == phase]
        fails = [e for e in execs if e.get("verdict") == "FAIL"]
        inputs, results = tool_events(run_dir / traj)
        visible = any(re.search(rf"\b{re.escape(method)}\b", r) for r in results)
        out[f"{phase}_flaky_runs"] = len(execs)
        out[f"{phase}_flaky_failures"] = len(fails)
        out[f"{phase}_oracle_exposed"] = bool(fails)
        out[f"{phase}_victim_visible"] = visible
        out[f"{phase}_observed_exposure"] = bool(fails) and visible
        out[f"{phase}_draws"] = [{"rule": e.get("rule"), "config": e.get("config"), "u": e.get("u"),
                                  "verdict": e.get("verdict")} for e in execs]
        hits = sorted({p for p in DISCOVERY for i in inputs if re.search(p, i)})
        out[f"{phase}_shim_discovery"] = hits
    out["oracle_errors"] = [e for e in events if e.get("event") == "oracle_error"]
    out["relay_fallbacks"] = sum(1 for e in events if e.get("event") == "exec" and e.get("verdict") == "RUN")
    return out
