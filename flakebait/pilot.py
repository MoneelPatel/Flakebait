"""Pilot: one agent on the 10 pilot repair instances at L1 and L2, flaky and control arms.

  uv run python -m flakebait.pilot --plan            # print the run plan and a cost estimate; runs nothing
  uv run python -m flakebait.pilot --run [--budget 50] [--model ...] [--workers 1]

Each run: harness (main phase + L3 CI phase), task success after each phase, exposure analysis.
Stops before starting a run that would push the measured spend past the budget.
Writes reports/milestone1/pilot_runs.csv, pilot_exposure.csv, pilot_cost.csv, pilot_decision.md.
"""
import argparse
import csv
import hashlib
import json
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import paths
from .evaluation import success_check
from .exposure import analyze
from .harness import PHASE_BUDGET_USD, Run

MAIN_RUNS = 120 * 2 * 4 * 3
PROMPT_RUNS = 40 * 2 * 2 * 3
L1_THRESHOLD = 0.70


def pilot_instances() -> list[str]:
    rows = list(csv.DictReader(open(paths.REPORTS / "instance_validation.csv")))
    return sorted(r["instance"] for r in rows if r.get("valid") == "True")


def fingerprint(inst: Path) -> str:
    """Identifies the task an instance poses (seeded fault, named test, prompt). A pilot run counts only while its
    instance still has the fingerprint it ran with; rebuilding an instance differently makes it run again."""
    meta = json.loads((inst / "meta.json").read_text())
    key = json.dumps([meta["mutant"]["id"], meta["named_test"], (inst / "prompt.md").read_text()])
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def run_one(instance: str, model: str | None, rep: int) -> dict:
    run = Run(instance, model=model, rep=rep)
    rec = run.execute()
    meta = run.meta
    inst = paths.INSTANCES / instance
    row = {"run_id": rec["run_id"], "instance": instance, "category": meta["category"], "level": meta["level"],
           "arm": meta["arm"], "model": model or "default", "rep": rep, "seed": rec["seed"],
           "instance_fingerprint": fingerprint(paths.INSTANCES / instance)}
    # Task success after the main phase (state saved before L3) and after L3.
    main_repo = run.dir / "work_after_main"
    if (run.dir / "diff_main.patch").exists():
        _materialize(inst / "repo", run.dir / "diff_main.patch", main_repo)
        row.update({f"success_main": success_check(inst, main_repo, run.dir / "check_main").get("success")})
    row["success_final"] = success_check(inst, run.dir / "work", run.dir / "check_final").get("success")
    exp = analyze(run.dir, meta["victim"])
    row.update({k: v for k, v in exp.items() if not isinstance(v, list)})
    row["main_shim_discovery"] = " ".join(exp["main_shim_discovery"])
    row["L3_shim_discovery"] = " ".join(exp["L3_shim_discovery"])
    row["main_draws"] = json.dumps(exp["main_draws"])
    for phase in ("main", "L3"):
        ph = rec["phases"].get(phase, {})
        for k in ("turns", "cost_usd", "input_tokens", "output_tokens", "cache_read_tokens",
                  "cache_creation_tokens", "wall_seconds", "timed_out", "is_error"):
            row[f"{phase}_{k}"] = ph.get(k)
    row["cost_usd"] = sum(float(rec["phases"].get(p, {}).get("cost_usd") or 0) for p in ("main", "L3"))
    (run.dir / "pilot_row.json").write_text(json.dumps(row, indent=1, default=str))
    return row


def _materialize(repo: Path, diff: Path, dest: Path) -> None:
    import shutil
    import subprocess
    shutil.rmtree(dest, ignore_errors=True)
    subprocess.run(["cp", "-cR", str(repo), str(dest)], check=True)
    if diff.stat().st_size:
        subprocess.run(["git", "-C", str(dest), "apply", "--binary", "--whitespace=nowarn", str(diff.resolve())],
                       check=False, capture_output=True)


def plan(model: str | None, est_cost: float) -> None:
    inst = pilot_instances()
    print(f"{len(inst)} validated pilot instances x 1 repetition = {len(inst)} runs (agent: Claude Code, "
          f"model: {model or 'Claude Code default'})")
    for i in inst:
        print("  ", i)
    print(f"estimated cost at ${est_cost:.2f}/run: ${est_cost * len(inst):.2f}")


def run_all(model: str | None, budget: float, workers: int, only: list[str] | None = None) -> list[dict]:
    out = paths.REPORTS / "pilot_runs.csv"
    # Resume: keep finished runs, skip their instances, count their cost against the budget.
    rows = list(csv.DictReader(open(out))) if out.exists() else []
    done = {r["instance"] for r in rows if current(r)}
    spent, lock = [sum(float(r["cost_usd"] or 0) for r in rows)], threading.Lock()

    def job(instance: str):
        with lock:
            # A run cannot spend more than two phase caps, so reserving that keeps the total under the budget.
            reserve = max(2 * PHASE_BUDGET_USD, 1.5 * max((float(r["cost_usd"] or 0) for r in rows), default=0))
            if spent[0] + reserve > budget:
                print(f"budget: skipping {instance} (spent ${spent[0]:.2f})", flush=True)
                return
        row = run_one(instance, model, 1)
        with lock:
            rows.append(row)
            spent[0] += float(row["cost_usd"] or 0)
            _write(rows, out)
            print(f"done {instance}: success_main={row.get('success_main')} exposed="
                  f"{row.get('main_observed_exposure')} cost=${row['cost_usd']:.2f} (total ${spent[0]:.2f})",
                  flush=True)

    todo = [i for i in (only or pilot_instances()) if i not in done]
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(job, todo))
    summarize(rows)
    return rows


def _write(rows: list[dict], path: Path) -> None:
    fields = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("run_id", "instance"), k))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def current_pilot(rows: list[dict]) -> list[dict]:
    """Runs on instances of the current pilot tests. A test can leave the selection after its pilot runs (a
    corrected check, deviations.md #18); its runs still count against the budget but not in the statistics."""
    from .instances import ARMS, LEVELS, accepted_candidates, instance_id, pilot_tests
    keep = {instance_id(c, l, a) for c in pilot_tests(accepted_candidates()) for l in LEVELS for a in ARMS}
    return [r for r in rows if r["instance"] in keep and current(r)]


def current(row: dict) -> bool:
    """The run is on the instance as it is now built, and was not excluded."""
    inst = paths.INSTANCES / row["instance"]
    if row.get("excluded_reason") or not (inst / "meta.json").exists():
        return False
    return row.get("instance_fingerprint") == fingerprint(inst)


def summarize(rows: list[dict]) -> None:
    excluded = len(rows) - len(rows := current_pilot(rows))   # cost of excluded runs still counts in run_all
    flaky = [r for r in rows if r["arm"] == "flaky"]
    exp_rows = []
    for level in ("L1", "L2"):
        for cat in ("ALL", "ID", "OD", "NIO", "TD"):
            sel = [r for r in flaky if r["level"] == level and (cat == "ALL" or r["category"] == cat)]
            n = len(sel)
            k = sum(1 for r in sel if r.get("main_observed_exposure") in (True, "True"))
            exp_rows.append({"level": level, "category": cat, "runs": n, "observed_exposure": k,
                             "rate": round(k / n, 3) if n else ""})
    with open(paths.REPORTS / "pilot_exposure.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["level", "category", "runs", "observed_exposure", "rate"])
        w.writeheader()
        w.writerows(exp_rows)

    costs = [float(r["cost_usd"] or 0) for r in rows]
    walls = [float(r.get("main_wall_seconds") or 0) + float(r.get("L3_wall_seconds") or 0) for r in rows]
    toks = [sum(int(r.get(f"{p}_{k}") or 0) for p in ("main", "L3")
                for k in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens"))
            for r in rows]
    def stats(xs):
        return (round(statistics.mean(xs), 3), round(statistics.median(xs), 3), round(max(xs), 3)) if xs else ("", "", "")
    cost_rows = []
    for name, xs in (("cost_usd", costs), ("wall_seconds", walls), ("tokens", toks)):
        mean, med, mx = stats(xs)
        cost_rows.append({"metric": name, "runs": len(xs), "mean": mean, "median": med, "max": mx})
    mean_cost = statistics.mean(costs) if costs else 0
    cost_rows.append({"metric": "projected_main_study_usd", "runs": MAIN_RUNS, "mean": round(mean_cost * MAIN_RUNS, 2)})
    cost_rows.append({"metric": "projected_prompt_study_usd", "runs": PROMPT_RUNS,
                      "mean": round(mean_cost * PROMPT_RUNS, 2)})
    with open(paths.REPORTS / "pilot_cost.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metric", "runs", "mean", "median", "max"])
        w.writeheader()
        w.writerows(cost_rows)

    l1 = next(r for r in exp_rows if r["level"] == "L1" and r["category"] == "ALL")
    l2 = next(r for r in exp_rows if r["level"] == "L2" and r["category"] == "ALL")
    if l1["runs"]:
        chosen = "L1" if l1["rate"] != "" and l1["rate"] >= L1_THRESHOLD else "L2"
        why = (f"L1 first-phase observed exposure was {l1['observed_exposure']}/{l1['runs']} "
               f"({l1['rate']:.0%}); the rule uses L1 only at >= {L1_THRESHOLD:.0%}. "
               f"L2 exposure was {l2['observed_exposure']}/{l2['runs']}.")
    else:
        chosen, why = "undecided", "no L1 runs completed"
    if excluded:
        why += (f" ({excluded} earlier runs on tests no longer selected are excluded here; their cost counts "
                f"against the budget.)")
    (paths.REPORTS / "pilot_decision.md").write_text(f"# Main-study exposure level\n\n**{chosen}**. {why}\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--budget", type=float, default=50.0)
    ap.add_argument("--model")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--est-cost", type=float, default=1.0)
    ap.add_argument("--instances", nargs="*", help="run only these instances")
    args = ap.parse_args()
    if args.plan or not args.run:
        plan(args.model, args.est_cost)
        return
    from .harness import load_api_key
    if not load_api_key():
        raise SystemExit("ANTHROPIC_API_KEY is not set (environment or .env)")
    run_all(args.model, args.budget, args.workers, args.instances)


if __name__ == "__main__":
    main()
