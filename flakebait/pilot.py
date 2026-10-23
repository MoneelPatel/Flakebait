"""Pilot: Codex CLI (config/study.yaml) on the 10 pilot repair instances at L1 and L2, flaky and control arms.

  uv run python -m flakebait.pilot --plan            # print the run plan and a cost estimate; runs nothing
  uv run python -m flakebait.pilot --run [--workers 1]

Each run: harness (main phase + L3 CI phase), task success after each phase, exposure analysis.
Runs go in a fixed, seeded order (seeds.yaml: pilot_order). No run starts once the study's spend reaches
caps.study_stop_usd minus one run's cap, so the total stays under the stop.
Writes reports/milestone1/pilot_runs.csv, pilot_exposure.csv, pilot_cost.csv, pilot_decision.md.
The 25 exploratory Claude Code runs made before the rescope are in pilot_runs_claude_exploratory.csv.
"""
import argparse
import csv
import hashlib
import json
import random
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import paths
from .evaluation import success_check
from .exposure import analyze
from .harness import CAPS, STUDY, Run, study_spend

import yaml

MAIN_RUNS = 40 * 2 * 3          # 40 instances x flaky/control x 3 repetitions
PROMPT_RUNS = 40 * 2 * 3        # 40 flaky-arm instances x hint/strict x 3 repetitions
L1_THRESHOLD = 0.70
CONTROL_SOLVE_MIN = 1 / 3       # below this, revisit the model choice (proposal, Notes)


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
           "arm": meta["arm"], "agent": rec["agent"], "model": rec["model"], "codex_version": rec["codex_version"],
           "reasoning_effort": rec["reasoning_effort"], "rep": rep, "seed": rec["seed"],
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
        for k in ("turns", "refused", "commands", "cost_usd", "input_tokens", "cached_input_tokens",
                  "output_tokens", "reasoning_tokens", "wall_seconds", "timed_out", "is_error"):
            row[f"{phase}_{k}"] = ph.get(k)
    row["cost_usd"] = sum(float(rec["phases"].get(p, {}).get("cost_usd") or 0) for p in ("main", "L3"))
    row["turn_cap_hit"] = bool(sum(int(rec["phases"].get(p, {}).get("refused") or 0) for p in ("main", "L3")))
    row["time_cap_hit"] = any(rec["phases"].get(p, {}).get("timed_out") for p in ("main", "L3"))
    row["l3_ran"] = "L3" in rec["phases"]
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


def run_order(instances: list[str]) -> list[str]:
    """Fixed, seeded order, so stopping early still leaves a mix of categories, levels and arms."""
    seed = yaml.safe_load(open(paths.CONFIG / "seeds.yaml"))["pilot_order"]
    order = sorted(instances)
    random.Random(seed).shuffle(order)
    return order


def plan(est_cost: float) -> None:
    inst = run_order(pilot_instances())
    print(f"{len(inst)} validated pilot instances x 1 repetition = {len(inst)} runs "
          f"(Codex CLI {STUDY['codex_version']}, {STUDY['model']}, effort {STUDY['reasoning_effort']})")
    for i in inst:
        print("  ", i)
    print(f"estimated cost at ${est_cost:.2f}/run: ${est_cost * len(inst):.2f}")


def run_all(model: str | None, budget: float, workers: int, only: list[str] | None = None) -> list[dict]:
    out = paths.REPORTS / "pilot_runs.csv"
    # Resume: keep finished runs, skip their instances, count their cost against the budget.
    rows = list(csv.DictReader(open(out))) if out.exists() else []
    done = {r["instance"] for r in rows if current(r)}
    lock = threading.Lock()

    def job(instance: str):
        with lock:
            # The meter stops a run at its per-run cap, so reserving one cap keeps the total under the stop.
            spent = study_spend()
            if spent + CAPS["usd_per_run"] * workers > budget:
                print(f"budget: skipping {instance} (study spend ${spent:.2f}, stop at ${budget:.2f})", flush=True)
                return
        row = run_one(instance, model, 1)
        with lock:
            rows.append(row)
            _write(rows, out)
            print(f"done {instance}: success_main={row.get('success_main')} exposed="
                  f"{row.get('main_observed_exposure')} cost=${row['cost_usd']:.4f} "
                  f"(study ${study_spend():.2f})", flush=True)

    todo = [i for i in run_order(only or pilot_instances()) if i not in done]
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
                for k in ("input_tokens", "output_tokens"))
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
    cost_rows.append({"metric": "study_spend_so_far_usd", "runs": "", "mean": study_spend()})
    for name, key in (("turn_cap_hit", "turn_cap_hit"), ("time_cap_hit", "time_cap_hit")):
        cost_rows.append({"metric": name, "runs": len(rows),
                          "mean": sum(1 for r in rows if r.get(key) in (True, "True"))})
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
    control = [r for r in rows if r["arm"] == "control"]
    solved = sum(1 for r in control if r.get("success_main") in (True, "True"))
    rate = solved / len(control) if control else None
    model_ok = "undecided" if rate is None else ("keep" if rate >= CONTROL_SOLVE_MIN else "revisit")
    projected = round(mean_cost * (MAIN_RUNS + PROMPT_RUNS), 2)
    (paths.REPORTS / "pilot_decision.md").write_text(
        f"# Pilot decisions\n\n## Main-study exposure level\n\n**{chosen}**. {why}\n\n"
        f"## Model ({STUDY['model']}, effort {STUDY['reasoning_effort']})\n\n**{model_ok}**. "
        + (f"Control-arm task success after the first phase: {solved}/{len(control)} ({rate:.0%}); the rule "
           f"revisits the model below {CONTROL_SOLVE_MIN:.0%}.\n\n" if control else "No control runs yet.\n\n")
        + f"## Budget\n\nMean cost per run ${mean_cost:.4f}; the {MAIN_RUNS + PROMPT_RUNS} remaining runs would "
          f"cost about ${projected:.2f}. Study spend so far ${study_spend():.2f}; runs stop at "
          f"${CAPS['study_stop_usd']:.0f} of the ${CAPS['study_budget_usd']:.0f} budget.\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--budget", type=float, default=CAPS["study_stop_usd"],
                    help="stop for the study's total spend; never above caps.study_stop_usd")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--est-cost", type=float, default=0.10)
    ap.add_argument("--instances", nargs="*", help="run only these instances")
    args = ap.parse_args()
    if args.plan or not args.run:
        plan(args.est_cost)
        return
    from .harness import load_api_key
    if not load_api_key():
        raise SystemExit("OPENAI_API_KEY is not set (environment or .env)")
    from .harness import api_ready
    ok, why = api_ready()
    if not ok:
        raise SystemExit(f"model API not ready: {why}")
    run_all(None, min(args.budget, CAPS["study_stop_usd"]), args.workers, args.instances)


if __name__ == "__main__":
    main()
