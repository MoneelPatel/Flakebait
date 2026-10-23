"""Unattended pilot: follow selection, and as pilot tests are accepted, build, validate and run them.

Every --interval seconds:
  1. pilot tests so far = first 3 ID / 3 OD / 2 NIO / 2 TD accepted (instances.pilot_tests)
  2. build any of their 4 instances (L1/L2 x flaky/control) not built yet, and validate them
  3. the first time a category has a valid flaky instance, run the end-to-end shim check on it
  4. run the agent on valid instances without a pilot run yet, within the budget (pilot.run_all)
Stops when all 40 pilot runs exist, or when selection has stopped and nothing is left to do.

Usage: uv run python -m flakebait.pilot_auto [--interval 600]   (budget: caps.study_stop_usd in config/study.yaml)
"""
import argparse
import csv
import json
import subprocess
import time

from . import paths
from .checks import shim
from .evaluation import validate
from .harness import CAPS, api_ready, load_api_key
from .instances import ARMS, LEVELS, accepted_candidates, build, instance_id, pilot_tests, write_prompt_reports
from .pilot import run_all, summarize


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def selection_running() -> bool:
    return subprocess.run(["pgrep", "-f", "flakebait.selection"], capture_output=True).returncode == 0


def validated(iid: str) -> bool | None:
    meta = paths.INSTANCES / iid / "meta.json"
    if not meta.exists():
        return None
    return json.loads(meta.read_text()).get("validated")


def merge_csv(path, rows: list[dict], key: str = "instance") -> None:
    old = list(csv.DictReader(open(path))) if path.exists() else []
    done = {r[key] for r in rows}
    allrows = [r for r in old if r[key] not in done] + rows
    fields = list(dict.fromkeys(k for r in allrows for k in r))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(allrows)


def step(budget: float, checked: set[str]) -> int:
    tests = pilot_tests(accepted_candidates())
    built_rows, val_rows = [], []
    for c in tests:
        for level in LEVELS:
            for arm in ARMS:
                iid = instance_id(c, level, arm)
                if validated(iid) is None:
                    try:
                        build(c, level, arm)
                        meta = json.loads((paths.INSTANCES / iid / "meta.json").read_text())
                        built_rows.append({"instance": iid, "test": c.flaky_test, "category": c.category,
                                           "level": level, "arm": arm, "target_class": meta["target_class"],
                                           "mutant_operator": meta["mutant"]["operator"],
                                           "mutant_location": f"{meta['source']}:{meta['mutant']['line']}",
                                           "named_test": meta["named_test"],
                                           "held_out_tests": " ".join(meta["held_out"]),
                                           "prompt_forbidden_hits": "; ".join(meta["prompt_forbidden_hits"]),
                                           "status": "built"})
                        log(f"built {iid}")
                    except Exception as e:
                        built_rows.append({"instance": iid, "test": c.flaky_test, "category": c.category,
                                           "level": level, "arm": arm, "status": f"error: {e}"})
                        log(f"build failed {iid}: {e}")
                        continue
                    val_rows.append(validate(paths.INSTANCES / iid, log=log))
    if built_rows:
        merge_csv(paths.REPORTS / "instances_manifest.csv", built_rows)
        write_prompt_reports(sorted(r["instance"] for r in csv.DictReader(open(paths.REPORTS / "instances_manifest.csv"))
                                    if r["status"] == "built"))
    if val_rows:
        merge_csv(paths.REPORTS / "instance_validation.csv", val_rows)

    # One end-to-end shim check per category (flaky arm) and one control instance overall.
    e2e = paths.REPORTS / "shim_e2e.csv"
    have = {(r["category"], r["arm"]) for r in csv.DictReader(open(e2e))} if e2e.exists() else set()
    for c in tests:
        for arm in ARMS:
            iid = instance_id(c, "L2", arm)
            want = (c.category, arm) not in have and (arm == "flaky" or not any(a == "control" for _, a in have))
            if want and validated(iid) and iid not in checked:
                checked.add(iid)
                rows = shim(iid)
                _merge_e2e(e2e, rows)
                have.add((c.category, arm))
                log(f"shim e2e {iid}: {[r['ok'] for r in rows]}")

    ready = [instance_id(c, l, a) for c in tests for l in LEVELS for a in ARMS if validated(instance_id(c, l, a))]
    ok, why = api_ready()
    if ok:
        run_all(None, budget, 1, ready)
    else:
        log(f"model API not ready ({why}); building and validating only")
    done = len(list(csv.DictReader(open(paths.REPORTS / "pilot_runs.csv")))) if (paths.REPORTS / "pilot_runs.csv").exists() else 0
    log(f"pilot tests {len(tests)}/10, valid instances {len(ready)}, pilot runs {done}")
    return done


def _merge_e2e(path, rows: list[dict]) -> None:
    old = list(csv.DictReader(open(path))) if path.exists() else []
    inst = {r["instance"] for r in rows}
    allrows = [r for r in old if r["instance"] not in inst] + rows
    fields = ["instance", "category", "arm", "step", "expected", "observed", "ok", "failure_excerpt"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(allrows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=CAPS["study_stop_usd"])
    ap.add_argument("--interval", type=int, default=600)
    args = ap.parse_args()
    if not load_api_key():
        raise SystemExit("OPENAI_API_KEY is not set (environment or .env)")
    checked: set[str] = set()
    while True:
        try:
            done = step(min(args.budget, CAPS["study_stop_usd"]), checked)
        except Exception as e:  # keep following selection; the error is in the log
            log(f"step failed: {type(e).__name__}: {e}")
            done = 0
        if done >= 40:
            break
        if not selection_running():
            step(min(args.budget, CAPS["study_stop_usd"]), checked)
            break
        time.sleep(args.interval)
    rows = list(csv.DictReader(open(paths.REPORTS / "pilot_runs.csv"))) if (paths.REPORTS / "pilot_runs.csv").exists() else []
    summarize(rows)
    log("pilot finished")


if __name__ == "__main__":
    main()
