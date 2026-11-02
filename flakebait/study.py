"""Main study (RQ1-RQ3) and prompt study (RQ4): Codex CLI on every validated L2 repair instance.

  uv run python -m flakebait.study --plan                       # run plan and cost estimate; runs nothing
  uv run python -m flakebait.study --run [--workers 2]           # main study: neutral prompt, both arms, 3 reps
  uv run python -m flakebait.study --run --variants hint,strict,locked --arms flaky   # prompt study (RQ4)
  uv run python -m flakebait.study --run --name local --model gpt-oss:20b --reps 1 --pilot-tests   # local arm

Per run: harness (main phase + L3 CI phase); task success after each phase on the pristine suite (full result in
check_main.json / check_final.json); exposure (exposure.py); automatic outcome per phase (outcomes.py, with the
flaky-test fix check in the flaky arm); the LLM judge (judge.py, labels in judge.json). One row per run in
reports/milestone2/<study>_runs.csv. Runs go in a fixed, seeded order (seeds.yaml: study_order). No run starts
once the study's spend plus one run's cap per worker would pass caps.study_stop_usd. Finished runs are kept and
skipped (resume), as long as their instance still has the fingerprint they ran with.
"""
import argparse
import csv
import json
import random
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from . import paths
from .evaluation import success_check
from .exposure import analyze
from .harness import CAPS, STUDY, Run, load_api_key, study_spend
from .judge import judge_run
from .llm import Session
from .outcomes import classify
from .pilot import _materialize, fingerprint

OUT = paths.REPORTS2
REPS = 3


def study_instances(arms: list[str]) -> list[str]:
    rows = list(csv.DictReader(open(paths.REPORTS2 / "instance_validation.csv")))
    out = []
    for r in rows:
        meta_p = paths.INSTANCES / r["instance"] / "meta.json"
        if r.get("valid") != "True" or not meta_p.exists():
            continue
        meta = json.loads(meta_p.read_text())
        # Built with an issue-style fault (bugs.py), not a pilot-era mutant prompt.
        if meta["level"] == "L2" and meta["arm"] in arms and (meta.get("fault") or {}).get("issue"):
            out.append(r["instance"])
    return sorted(out)


def plan_runs(instances: list[str], variants: list[str], reps: int = REPS) -> list[tuple[str, str, int]]:
    seed = yaml.safe_load(open(paths.CONFIG / "seeds.yaml"))["study_order"]
    runs = [(i, v, rep) for i in instances for v in variants for rep in range(1, reps + 1)]
    runs.sort()
    random.Random(seed).shuffle(runs)
    return runs


def run_one(instance: str, variant: str, rep: int, judge: Session | None, model: str | None = None) -> dict:
    run = Run(instance, rep=rep, prompt_variant=variant, model=model,
              run_id=None if model in (None, STUDY["model"]) else
              f"{instance}--{STUDY['agent']}-{model.replace(':', '-')}--{variant}--r{rep}")
    rec = run.execute()
    meta, inst = run.meta, paths.INSTANCES / instance
    row = {"run_id": rec["run_id"], "instance": instance, "category": meta["category"], "arm": meta["arm"],
           "level": meta["level"], "variant": variant, "rep": rep, "fault_kind": meta.get("fault", {}).get("kind"),
           "shim": rec.get("shim"), "model": rec["model"], "seed": rec["seed"],
           "instance_fingerprint": fingerprint(inst)}
    checks = {}
    main_repo = run.dir / "work_after_main"
    if (run.dir / "diff_main.patch").exists():
        _materialize(inst / "repo", run.dir / "diff_main.patch", main_repo)
        checks["main"] = success_check(inst, main_repo, run.dir / "check_main")
    checks["final"] = success_check(inst, run.dir / "work", run.dir / "check_final")
    for phase, chk in checks.items():
        (run.dir / f"check_{phase}.json").write_text(json.dumps(chk, indent=1))
        row[f"success_{phase}"] = chk.get("success")
    exp = analyze(run.dir, meta["victim"])
    row.update({k: v for k, v in exp.items() if not isinstance(v, list)})
    row["main_draws"] = json.dumps(exp["main_draws"])
    row["shim_discovery"] = " ".join(sorted(set(exp["main_shim_discovery"] + exp["L3_shim_discovery"])))
    outcome = {}
    for phase, tree in (("main", main_repo), ("final", run.dir / "work")):
        if phase in checks:
            outcome[phase] = classify(run.dir, meta, phase, checks[phase], tree,
                                      solved_before=phase == "final" and bool(checks.get("main", {}).get("success")))
            row[f"{phase}_auto_outcome"] = outcome[phase]["auto_outcome"]
            row[f"{phase}_masking"] = " ".join(outcome[phase]["masking"])
            row[f"{phase}_regressions"] = len(outcome[phase]["regressions"])
            row[f"{phase}_test_files"] = len(outcome[phase]["test_files"])
            fc = outcome[phase]["flaky_fix_check"]
            row[f"{phase}_flaky_fixed"] = None if fc is None else fc["fixed"]
            row[f"{phase}_damaging"] = outcome[phase]["damaging"]
            row[f"{phase}_task_undone"] = outcome[phase].get("task_undone", False)
    (run.dir / "outcome.json").write_text(json.dumps(outcome, indent=1))
    if judge is not None:
        try:
            labels = judge_run(judge, run.dir)
            row.update({f"judge_{k}": v for k, v in labels.items() if k not in ("evidence", "explanation")})
        except Exception as e:
            row["judge_error"] = f"{type(e).__name__}: {e}"
    for phase in ("main", "L3"):
        ph = rec["phases"].get(phase, {})
        for k in ("turns", "refused", "commands", "cost_usd", "wall_seconds", "timed_out", "is_error"):
            row[f"{phase}_{k}"] = ph.get(k)
    row["cost_usd"] = sum(float(rec["phases"].get(p, {}).get("cost_usd") or 0) for p in ("main", "L3"))
    row["turn_cap_hit"] = bool(sum(int(rec["phases"].get(p, {}).get("refused") or 0) for p in ("main", "L3")))
    row["time_cap_hit"] = any(rec["phases"].get(p, {}).get("timed_out") for p in ("main", "L3"))
    (run.dir / "study_row.json").write_text(json.dumps(row, indent=1, default=str))
    return row


def row_id(t: tuple[str, str, int], model: str | None) -> str:
    agent = STUDY["agent"] if model in (None, STUDY["model"]) else f"{STUDY['agent']}-{model.replace(':', '-')}"
    return f"{t[0]}--{agent}--{t[1]}--r{t[2]}"


def pilot_set():
    """The 9 tests of the Milestone 1 pilot (pilot_runs.csv), for the local-model arm."""
    from .instances import accepted_candidates
    ran = {r["instance"] for r in csv.DictReader(open(paths.REPORTS / "pilot_runs.csv"))}
    return [c for c in accepted_candidates() if any(f"-{c.result_container}-" in i for i in ran)]


def write(rows: list[dict], path: Path) -> None:
    fields = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("run_id", "instance"), k))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def run_all(name: str, variants: list[str], arms: list[str], workers: int, limit: int | None,
            model: str | None = None, reps: int = REPS, pilot_only: bool = False) -> None:
    out = OUT / f"{name}_runs.csv"
    csv.field_size_limit(10**9)
    rows = list(csv.DictReader(open(out))) if out.exists() else []
    done = {r["run_id"] for r in rows
            if (paths.INSTANCES / r["instance"] / "meta.json").exists()
            and r.get("instance_fingerprint") == fingerprint(paths.INSTANCES / r["instance"])}
    rows = [r for r in rows if r["run_id"] in done]
    instances = study_instances(arms)
    if pilot_only:
        instances = [i for i in instances if any(i.startswith(f"repair-{c.category.lower()}-{c.result_container}-")
                                                 for c in pilot_set())]
    todo = [t for t in plan_runs(instances, variants, reps) if row_id(t, model) not in done]
    if limit:
        todo = todo[:limit]
    lock = threading.Lock()
    print(f"{len(done)} runs done, {len(todo)} to run", flush=True)
    with Session("judge", usd_cap=min(5.0, CAPS["study_stop_usd"] - study_spend() - 1)) as judge:
        def job(t: tuple[str, str, int]) -> None:
            with lock:
                spent = study_spend()
                if spent + CAPS["usd_per_run"] * workers > CAPS["study_stop_usd"]:
                    print(f"budget: skipping {t} (study spend ${spent:.2f})", flush=True)
                    return
            try:
                row = run_one(*t, judge, model)
            except Exception as e:
                print(f"ERROR {t}: {type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}", flush=True)
                return
            with lock:
                rows.append(row)
                write(rows, out)
                print(f"done {row['run_id']}: success={row.get('success_main')}/{row.get('success_final')} "
                      f"exposed={row.get('main_observed_exposure')}/{row.get('L3_observed_exposure')} "
                      f"outcome={row.get('final_auto_outcome')} cost=${row['cost_usd']:.4f} "
                      f"(study ${study_spend():.2f})", flush=True)

        with ThreadPoolExecutor(workers) as pool:
            list(pool.map(job, todo))


def rejudge(name: str) -> None:
    """Judge again the runs whose judge call failed (judge_error), and update their rows."""
    out = OUT / f"{name}_runs.csv"
    csv.field_size_limit(10**9)
    rows = list(csv.DictReader(open(out)))
    todo = [r for r in rows if r.get("judge_error")]
    print(f"{len(todo)} runs to judge again", flush=True)
    with Session("judge", usd_cap=1.0) as judge:
        for r in todo:
            try:
                labels = judge_run(judge, paths.RUNS / r["run_id"])
                r.update({f"judge_{k}": v for k, v in labels.items() if k not in ("evidence", "explanation")})
                r["judge_error"] = ""
            except Exception as e:
                r["judge_error"] = f"{type(e).__name__}: {e}"
            write(rows, out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--name", default="main")
    ap.add_argument("--variants", default="neutral")
    ap.add_argument("--arms", default="flaky,control")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--limit", type=int, help="run at most this many (smoke test)")
    ap.add_argument("--model", help="agent model (default: config/study.yaml; e.g. the local arm's gpt-oss:20b)")
    ap.add_argument("--reps", type=int, default=REPS)
    ap.add_argument("--pilot-tests", action="store_true", help="only the 9 tests of the Milestone 1 pilot")
    ap.add_argument("--rejudge", action="store_true", help="judge again the runs whose judge call failed")
    args = ap.parse_args()
    if args.rejudge:
        load_api_key()
        rejudge(args.name)
        return
    variants, arms = args.variants.split(","), args.arms.split(",")
    runs = plan_runs(study_instances(arms), variants, args.reps)
    if args.plan or not args.run:
        print(f"{len(runs)} runs ({len(set(r[0] for r in runs))} instances x {variants} x {REPS} reps); "
              f"study spend so far ${study_spend():.2f}")
        return
    if not load_api_key():
        raise SystemExit("OPENAI_API_KEY is not set (environment or .env)")
    run_all(args.name, variants, arms, args.workers, args.limit, args.model, args.reps, args.pilot_tests)


if __name__ == "__main__":
    main()
