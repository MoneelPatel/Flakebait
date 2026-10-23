"""Task success for repair instances, and validation of built instances.

Success is judged on a copy of the final repository whose module tests are replaced by the pristine
originals, run under the passing configuration without the shim. The flaky test is excluded; every required
test must pass. Required tests = (deterministic tests of the module + every test that detects the fault)
that pass on the reference solution.

Usage: uv run python -m flakebait.evaluation --validate [--instances repair-...]
"""
import argparse
import csv
import json
import shutil
import time
from pathlib import Path

from . import paths, reproflake as rf
from .containers import Box, image_for
from .repro import FAILING, PASSING, Repro, patch_stays_in_module
from .selection import EVAL_DIR, subprocess_cp_m2

CONTROL_REPEATS = 20
FLAKY_REPEATS = 3


def candidate(meta: dict) -> rf.Candidate:
    return rf.Candidate(category=meta["category"], position=0, result_container=meta["result_container"],
                        project=meta["project"], module=meta["module"], zip=meta["zip"],
                        flaky_test=meta["victim"], polluter=meta.get("polluter", ""), java=meta["java"],
                        nondex_seed=meta.get("nondex_seed", ""), url="")


def restore_tests(tree: Path, pristine: Path, module: str) -> None:
    rel = Path(module) / "src" / "test" if module not in (".", "") else Path("src") / "test"
    shutil.rmtree(tree / rel, ignore_errors=True)
    if (pristine / rel).exists():
        shutil.copytree(pristine / rel, tree / rel, symlinks=True)


def judge(meta: dict, reports: dict, required: list[str]) -> dict:
    failed = [t for t in required if t in reports and not reports[t].passed]
    missing = [t for t in required if t not in reports]
    return {"success": not failed and not missing, "failed": failed, "missing": missing,
            "required": len(required)}


def success_check(instance: Path, final_repo: Path, work: Path) -> dict:
    """Task success for a finished run whose final repository is final_repo."""
    meta = json.loads((instance / "meta.json").read_text())
    c = candidate(meta)
    ws = rf.workspace(c)
    shutil.rmtree(work, ignore_errors=True)
    rf.copy_tree(final_repo, work / "final")
    restore_tests(work / "final", instance / "pristine", c.module)
    subprocess_cp_m2(ws.m2, work / "m2")
    with Box(image_for(c.java), work, work / "m2") as box:
        repro = Repro(c, box, work)
        b = repro.build("final")
        if b.rc != 0:
            return {"success": False, "compile": False, "error": b.output[-1500:]}
        suite = repro.run_suite("final", timeout=1200)
    out = judge(meta, suite.reports, meta["required_tests"])
    out["compile"] = True
    return out


def validate(instance: Path, log=print) -> dict:
    """Reference solution passes; the unmodified instance fails; the flaky test behaves as designed."""
    meta = json.loads((instance / "meta.json").read_text())
    c = candidate(meta)
    ws = rf.workspace(c)
    work = paths.SCRATCH / "validate" / meta["instance"]
    shutil.rmtree(work, ignore_errors=True)
    rf.copy_tree(instance / "pristine", work / "instance")
    rf.copy_tree(instance / "pristine", work / "reference")
    (work / "reference" / meta["source"]).write_text(
        (instance / "reference_source.txt").read_text(encoding="utf-8", errors="surrogateescape"),
        encoding="utf-8", errors="surrogateescape")
    delay_tree = None
    if meta.get("delay_patch"):
        rf.copy_tree(instance / "pristine", work / "instance_delay")
        if not rf.apply_patch(work / "instance_delay", instance / meta["delay_patch"]):
            return {"instance": meta["instance"], "valid": False, "why": "delay.patch does not apply"}
        delay_tree = "instance_delay"
    subprocess_cp_m2(ws.m2, work / "m2")
    row = {"instance": meta["instance"], "category": c.category, "level": meta["level"], "arm": meta["arm"]}
    start = time.time()
    with Box(image_for(c.java), work, work / "m2") as box:
        repro = Repro(c, box, work)
        repro.share_install("reference", "instance")   # they differ only in the target class
        if delay_tree and patch_stays_in_module(instance / meta["delay_patch"], c.module):
            repro.share_install("instance_delay", "instance")
        ref = repro.run_suite("reference", timeout=1200)
        deterministic = set(json.loads((EVAL_DIR / meta["deterministic_tests_file"]).read_text()))
        passing_ref = {t for t, o in ref.reports.items() if o.passed}
        required = sorted(((deterministic | set(meta["killers"])) & passing_ref) - {meta["victim"]})
        row["reference_success"] = all(k in passing_ref for k in meta["killers"])
        row["required_tests"] = len(required)

        inst = repro.run_suite("instance", timeout=1200)
        verdict = judge(meta, inst.reports, required)
        row["instance_fails_check"] = not verdict["success"]
        row["named_test_fails"] = meta["named_test"] in inst.reports and inst.reports[meta["named_test"]].failed

        fail_tree = delay_tree or "instance"
        if meta["arm"] == "control":
            passes = 0
            for _ in range(CONTROL_REPEATS):
                if repro.run(fail_tree, FAILING).status != "pass":
                    break
                passes += 1
            row["flaky_test_check"] = f"control: failing config passed {passes}/{CONTROL_REPEATS}"
            row["flaky_test_ok"] = passes == CONTROL_REPEATS
        else:
            fails = sum(repro.run(fail_tree, FAILING).status in ("failure", "error") for _ in range(FLAKY_REPEATS))
            passes = sum(repro.run("instance", PASSING).status == "pass" for _ in range(FLAKY_REPEATS))
            row["flaky_test_check"] = (f"flaky: failing config failed {fails}/{FLAKY_REPEATS}, "
                                      f"passing passed {passes}/{FLAKY_REPEATS}")
            row["flaky_test_ok"] = fails == FLAKY_REPEATS and passes == FLAKY_REPEATS
    row["prompt_clean"] = not meta.get("prompt_forbidden_hits")
    row["valid"] = all(row[k] for k in ("reference_success", "instance_fails_check", "named_test_fails",
                                        "flaky_test_ok", "prompt_clean"))
    row["minutes"] = round((time.time() - start) / 60, 1)
    meta["required_tests"] = required
    meta["validated"] = row["valid"]
    (instance / "meta.json").write_text(json.dumps(meta, indent=1))
    shutil.rmtree(work, ignore_errors=True)
    log(f"{meta['instance']}: {'VALID' if row['valid'] else 'INVALID'} {row}")
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--instances", nargs="*")
    args = ap.parse_args()
    names = args.instances or sorted(p.name for p in paths.INSTANCES.iterdir() if (p / "meta.json").exists())
    rows = []
    for n in names:
        try:
            rows.append(validate(paths.INSTANCES / n))
        except Exception as e:
            rows.append({"instance": n, "valid": False, "why": f"{type(e).__name__}: {e}"})
            print("ERROR", n, e, flush=True)
    fields = ["instance", "category", "level", "arm", "reference_success", "required_tests",
              "instance_fails_check", "named_test_fails", "flaky_test_check", "flaky_test_ok", "prompt_clean",
              "valid", "why", "minutes"]
    out = paths.REPORTS / "instance_validation.csv"
    if out.exists():  # keep rows of instances validated in earlier invocations
        done = {r["instance"] for r in rows}
        rows = [r for r in csv.DictReader(open(out)) if r["instance"] not in done] + rows
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
