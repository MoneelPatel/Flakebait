"""Flaky-test selection: walk each category's shuffled candidates and accept eligible tests until 10.

Checks run in a fixed order and the first failing one is the rejection reason:
  cap_class                 TD and NIO only, in place of the two caps below: <= 1 per test class (deviations #20)
  cap_module, cap_project   diversity caps (<= 1 per Maven module, <= 2 per upstream project, across
                            categories; config/project_aliases.yaml)
  addressable               the victim is one plain test method (not parameterized), so it can be named
                            to Maven and intercepted by the shim (technical criterion; deviations.md #4)
  a_offline_compile         module and upstream modules install offline from the cached repository
  f_suite_under_10min       the module's suite finishes in under 10 minutes
  e_other_deterministic     the victim's class has another test that passes in two default suite runs
  b_failing_20, b_passing_20
  c_fixed_20                with Fixed.patch, the failing configuration passes 20/20
  d_seedable                a fault can be seeded for the repair task (seeding.py)

Categories are processed in a fixed order, scarcest first (TD, NIO, OD, ID), so the global caps cost the
small strata least. Within a category, candidates are evaluated in parallel but committed strictly in
shuffled order, so the outcome equals a sequential walk.

Usage: uv run python -m flakebait.selection [--workers N] [--categories TD,NIO,OD,ID]
"""
import argparse
import csv
import json
import shutil
import threading
import time
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import paths, reproflake as rf
from .containers import Box, image_for
from .coverage import collect
from .repro import FAILING, PASSING, Repro, patch_stays_in_module
from .seeding import REPEATS, seed_fault

CATEGORY_ORDER = ["TD", "NIO", "OD", "ID"]
TARGET = 10
# TD and NIO cannot reach 10 under the module/project caps (NIO's 125 candidates come from 5 modules, 120 of them
# junit-quickcheck core; TD's 36 from 17 modules in 10 repositories). For them the caps are replaced by at most one
# flaky test per test class (deviations.md #20). ID and OD keep the proposal's caps, counted against all accepted.
CLASS_CAP_ONLY = {"TD", "NIO"}
CHECKS = ["cap_class", "cap_module", "cap_project", "addressable", "a_offline_compile", "f_suite_under_10min",
          "e_other_deterministic", "b_failing_20", "b_passing_20", "c_fixed_20", "d_seedable"]
LOG = paths.REPORTS / "selection_log.csv"
EVAL_DIR = paths.DATA / "evaluations"


@dataclass
class Evaluation:
    candidate: str
    checks: dict = field(default_factory=dict)       # check -> "pass" | "fail" | detail
    reason: str = ""
    details: dict = field(default_factory=dict)
    started: str = ""
    finished: str = ""

    @property
    def eligible(self) -> bool:
        return not self.reason


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def evaluate(c: rf.Candidate, log) -> Evaluation:
    """All non-cap checks for one candidate, stopping at the first failure. Saved to data/evaluations/."""
    ev = Evaluation(c.result_container, started=now())
    cached = EVAL_DIR / f"{c.result_container}.json"
    if cached.exists():
        prev = Evaluation(**json.loads(cached.read_text()))
        if prev.reason != "error":
            return prev

    box_ref: list[Box] = []

    def fail(check: str, why: str) -> Evaluation:
        # A container killed under us (e.g. Docker restarted) must not count as a failed check.
        if box_ref and not box_ref[0].alive():
            raise RuntimeError(f"build container died during check {check}")
        ev.checks[check] = "fail"
        ev.reason = check
        ev.details[f"{check}_why"] = why
        return ev

    try:
        if not c.test_method or "[" in c.test_method or "(" in c.test_method:
            fail("addressable", "parameterized or unnamed test method")
            return _save(ev)
        ev.checks["addressable"] = "pass"

        with _zip_lock(c.zip):
            ws = rf.workspace(c)
        host = paths.SCRATCH / c.result_container
        shutil.rmtree(host, ignore_errors=True)
        rf.copy_tree(ws.flaky, host / "flaky")
        subprocess_cp_m2(ws.m2, host / "m2")
        delay = None
        if c.category == "TD":
            if not ws.delay_patch.exists():
                fail("b_failing_20", "no FlakyCodeChange.patch for TD test")
                return _save(ev)
            rf.copy_tree(ws.flaky, host / "flaky_delay")
            if not rf.apply_patch(host / "flaky_delay", ws.delay_patch):
                fail("b_failing_20", "delay patch does not apply")
                return _save(ev)
            delay = "flaky_delay"

        with Box(image_for(c.java), host, host / "m2") as box:
            box_ref.append(box)
            repro = Repro(c, box, host)
            if delay and patch_stays_in_module(ws.delay_patch, c.module):
                repro.share_install(delay, "flaky")

            # (a) offline compile
            b = repro.build("flaky")
            ev.details["build_seconds"] = round(b.seconds, 1)
            if b.rc != 0:
                _keep_log(host, "build.log", b.output)
                fail("a_offline_compile", _last_error(b.output))
                return _save(ev)
            ev.checks["a_offline_compile"] = "pass"

            # (f) suite time; also the first default run of every test
            suite = repro.run_suite("flaky", timeout=600)
            ev.details["suite_seconds"] = round(suite.result.seconds, 1)
            if suite.result.timed_out:
                fail("f_suite_under_10min", "suite exceeded 10 minutes")
                return _save(ev)
            if suite.result.rc != 0 or not suite.reports:
                _keep_log(host, "suite.log", suite.result.output)
                fail("f_suite_under_10min", "suite did not run: " + _last_error(suite.result.output))
                return _save(ev)
            ev.checks["f_suite_under_10min"] = "pass"

            # (e) needs a second default run; the coverage run is that run (and feeds seeding)
            cov = collect(repro, "flaky", timeout=900)
            passed1 = {t for t, o in suite.reports.items() if o.passed}
            passed2 = {t for t, o in cov.suite.reports.items() if o.passed}
            deterministic = (passed1 & passed2) - {c.flaky_test}
            ev.details["tests_in_module"] = len(suite.reports)
            ev.details["deterministic_tests"] = len(deterministic)
            ev.details["coverage_rows"] = len(cov.rows)
            same_class = sorted(t for t in deterministic if t.split("#", 1)[0] == c.test_class)
            if not same_class:
                fail("e_other_deterministic", "no other deterministic test in the flaky test's class")
                return _save(ev)
            ev.checks["e_other_deterministic"] = "pass"
            EVAL_DIR.mkdir(parents=True, exist_ok=True)
            (EVAL_DIR / f"{c.result_container}.deterministic.json").write_text(
                json.dumps(sorted(deterministic), indent=1))

            # (b) both configurations deterministic, 20/20 each; stop at the first deviation
            fail_tree = delay or "flaky"
            n_fail = _count(repro, fail_tree, FAILING, want_fail=True)
            ev.details["b_failing_failed"] = n_fail
            if n_fail < REPEATS:
                fail("b_failing_20", f"failing configuration failed {n_fail}/{n_fail + 1}")
                return _save(ev)
            ev.checks["b_failing_20"] = "pass"
            n_pass = _count(repro, "flaky", PASSING, want_fail=False)
            ev.details["b_passing_passed"] = n_pass
            if n_pass < REPEATS:
                fail("b_passing_20", f"passing configuration passed {n_pass}/{n_pass + 1}")
                return _save(ev)
            ev.checks["b_passing_20"] = "pass"

            # (c) the developer fix makes the failing configuration pass 20/20
            fixed_tree = "fixed_delay" if delay else "fixed"
            fixed_patch = ws.root / "FixedCodeChange.patch" if delay else ws.fixed_patch
            rf.copy_tree(ws.flaky, host / fixed_tree)
            if not fixed_patch.exists() or not rf.apply_patch(host / fixed_tree, fixed_patch):
                fail("c_fixed_20", f"{fixed_patch.name} missing or does not apply")
                return _save(ev)
            if patch_stays_in_module(fixed_patch, c.module):
                repro.share_install(fixed_tree, "flaky")
            n_fixed = _count(repro, fixed_tree, FAILING, want_fail=False)
            ev.details["c_fixed_passed"] = n_fixed
            if n_fixed < REPEATS:
                fail("c_fixed_20", f"fixed version passed {n_fixed}/{n_fixed + 1} under the failing configuration")
                return _save(ev)
            ev.checks["c_fixed_20"] = "pass"

            # (d) a seedable fault
            if repro.installed != repro.install_key.get("flaky", "flaky"):
                repro.build("flaky")
            seed = seed_fault(repro, cov, deterministic, delay, log=log)
            ev.details["seeding"] = asdict(seed)
            if not seed.ok:
                fail("d_seedable", seed.reason)
                return _save(ev)
            ev.checks["d_seedable"] = "pass"
            return _save(ev)
    except Exception as e:  # infrastructure errors are recorded, not hidden
        ev.reason = "error"
        ev.details["error"] = f"{type(e).__name__}: {e}"
        ev.details["traceback"] = traceback.format_exc()[-3000:]
        return _save(ev)


_ZIP_LOCKS: dict[str, threading.Lock] = {}
_ZIP_LOCKS_GUARD = threading.Lock()


def _zip_lock(name: str) -> threading.Lock:
    with _ZIP_LOCKS_GUARD:
        return _ZIP_LOCKS.setdefault(name, threading.Lock())


def subprocess_cp_m2(src: Path, dest: Path) -> None:
    import subprocess
    shutil.rmtree(dest, ignore_errors=True)
    subprocess.run(["cp", "-cR", str(src), str(dest)], check=True)


def _count(repro: Repro, tree: str, config: str, want_fail: bool) -> int:
    """Number of consecutive runs (up to REPEATS) with the wanted outcome."""
    for i in range(REPEATS):
        status = repro.run(tree, config).status
        ok = status in ("failure", "error") if want_fail else status == "pass"
        if not ok:
            return i
    return REPEATS


def _last_error(output: str) -> str:
    errs = [l for l in output.splitlines() if l.startswith("[ERROR]") and len(l) > 10]
    return (errs[0] if errs else output.strip().splitlines()[-1] if output.strip() else "")[:300]


def _keep_log(host: Path, name: str, text: str) -> None:
    (host / name).write_text(text[-200_000:])


def _save(ev: Evaluation) -> Evaluation:
    ev.finished = now()
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    (EVAL_DIR / f"{ev.candidate}.json").write_text(json.dumps(asdict(ev), indent=1))
    return ev


# ----------------------------------------------------------------------------------------------- walk

class Walk:
    def __init__(self, workers: int):
        self.workers = workers
        self.accepted: list[rf.Candidate] = []
        self.rows: list[dict] = []
        self.lock = threading.Lock()

    def caps(self, c: rf.Candidate) -> str | None:
        if c.category in CLASS_CAP_ONLY:
            if any(a.test_class == c.test_class for a in self.accepted):
                return "cap_class"
            return None
        if any(a.module_key == c.module_key for a in self.accepted):
            return "cap_module"
        if sum(1 for a in self.accepted if a.upstream == c.upstream) >= 2:
            return "cap_project"
        return None

    def category(self, cat: str, candidates: list[rf.Candidate]) -> None:
        cands = [c for c in candidates if c.category == cat]
        futures: dict[int, Future] = {}
        accepted_here = 0

        def log(msg: str) -> None:
            print(f"[{cat}] {msg}", flush=True)

        with ThreadPoolExecutor(self.workers) as pool:
            submitted: set[int] = set()
            for i, c in enumerate(cands):
                if accepted_here >= TARGET:
                    break
                # Speculatively evaluate the next few candidates; results are committed in order below.
                for j in range(i, min(i + self.workers, len(cands))):
                    if j not in submitted:
                        submitted.add(j)
                        cj = cands[j]
                        if self.caps(cj) is None:
                            futures[j] = pool.submit(evaluate, cj, lambda m, cj=cj: log(f"{cj.result_container}{m}"))
                capped = self.caps(c)
                row = {"category": cat, "shuffle_position": c.position, "result_container": c.result_container,
                       "project": c.project, "upstream": c.upstream, "module": c.module, "test": c.flaky_test,
                       "java": c.java}
                if capped:
                    row.update({"rejection_reason": capped, capped: "fail", "started": now(), "finished": now()})
                    futures.pop(i, None)
                    log(f"#{c.position} {c.result_container}: rejected ({capped})")
                else:
                    fut = futures.pop(i, None) or pool.submit(evaluate, c, lambda m: log(f"{c.result_container}{m}"))
                    ev = fut.result()
                    row.update({"rejection_reason": ev.reason or "", "started": ev.started, "finished": ev.finished})
                    row.update({k: v for k, v in ev.checks.items()})
                    row["detail"] = ev.details.get(f"{ev.reason}_why", ev.details.get("error", ""))
                    if not ev.eligible:
                        shutil.rmtree(paths.SCRATCH / c.result_container, ignore_errors=True)
                    if ev.eligible:
                        self.accepted.append(c)
                        accepted_here += 1
                        log(f"#{c.position} {c.result_container}: ACCEPTED ({accepted_here}/{TARGET})")
                    else:
                        log(f"#{c.position} {c.result_container}: rejected ({ev.reason}) {row['detail'][:120]}")
                self.rows.append(row)
                self.write()
            for f in futures.values():
                f.cancel()
        if accepted_here < TARGET:
            log(f"shortfall: {accepted_here}/{TARGET} eligible after examining all {len(cands)} candidates")

    def write(self) -> None:
        fields = ["category", "shuffle_position", "result_container", "project", "upstream", "module", "test", "java",
                  *CHECKS, "rejection_reason", "detail", "started", "finished"]
        with open(LOG, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(self.rows)
        with open(paths.REPORTS / "selected_tests.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["category", "shuffle_position", "result_container", "project", "module", "test", "java",
                        "polluter", "nondex_seed", "target_class", "mutant", "failing_configuration",
                        "passing_configuration"])
            for c in self.accepted:
                ev = json.loads((EVAL_DIR / f"{c.result_container}.json").read_text())
                seed = ev["details"].get("seeding") or {}
                m = seed.get("mutant") or {}
                w.writerow([c.category, c.position, c.result_container, c.project, c.module, c.flaky_test, c.java,
                            c.polluter, c.nondex_seed, seed.get("target_class", ""),
                            f"{m.get('operator', '')} {m.get('method', '')} L{m.get('line', '')}".strip(),
                            failing_description(c), "mvn test -Dtest=<victim> (default order, one run)"])


def failing_description(c: rf.Candidate) -> str:
    return {
        "ID": f"NonDex 2.1.1, seed {c.nondex_seed}, victim only",
        "OD": f"polluter {c.polluter} runs first in the same JVM",
        "NIO": "victim runs twice in one JVM; second run reported",
        "TD": "ReproFlake delay patch (FlakyCodeChange.patch)",
    }[c.category]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--categories", default=",".join(CATEGORY_ORDER))
    args = ap.parse_args()
    cands = rf.load_candidates()
    walk = Walk(args.workers)
    start = time.time()
    for cat in args.categories.split(","):
        walk.category(cat, cands)
    print(f"done in {(time.time() - start) / 3600:.1f} h; accepted {len(walk.accepted)}", flush=True)


if __name__ == "__main__":
    main()
