"""Seeding one fault in the target class for the repair task (eligibility check (d)).

1. Candidate methods: target-class methods covered by the flaky test and by >= 2 deterministic tests.
2. Mutants of those methods from fb-tools (PIT default operators, source-level).
3. In seeded random order, keep the first mutant that
     compiles,
     is killed by >= 2 deterministic tests, with >= 1 killer in the flaky test's class (named test at L2)
       and >= 1 killer in another class (named test at L1),
     and those killers also fail when their class runs alone, as the prompt tells the agent to run the named
       test (deviations.md #23),
     leaves the flaky test unchanged: passing configuration passes, failing configuration fails,
     and still does so 20/20.
   Taking the first survivor of a uniform random permutation is a uniform choice among survivors.
"""
import csv
import difflib
import hashlib
import random
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import paths, reproflake as rf
from .coverage import Coverage, source_file, target_class
from .repro import FAILING, PASSING, Repro

REPEATS = 20


@dataclass
class SeedResult:
    ok: bool
    reason: str = ""
    target_class: str | None = None
    source: str | None = None             # path relative to the project root
    methods: list[str] = field(default_factory=list)
    mutant: dict | None = None
    killers: list[str] = field(default_factory=list)
    killer_messages: dict = field(default_factory=dict)
    standalone_killers: list[str] = field(default_factory=list)   # fail with their class run alone
    funnel: dict = field(default_factory=dict)
    seed: int = 0


def mutant_seed(test: str) -> int:
    base = yaml.safe_load(open(paths.CONFIG / "seeds.yaml"))["mutant_choice"]
    return int(hashlib.sha256(f"{base}:{test}".encode()).hexdigest()[:16], 16)


def seed_fault(repro: Repro, cov: Coverage, deterministic: set[str], delay_tree: str | None,
               log=print) -> SeedResult:
    c = repro.c
    res = SeedResult(ok=False, seed=mutant_seed(c.flaky_test))
    funnel = res.funnel = {"candidate_methods": 0, "generated": 0, "examined": 0, "compiled": 0,
                           "killed_2plus": 0, "killed_l1_l2": 0, "killed_alone": 0,
                           "flaky_unchanged": 0, "recheck_20": 0}

    target = target_class(cov, c.flaky_test)
    if target is None:
        res.reason = "flaky test covers no production class"
        return res
    res.target_class = target
    module_dir = repro.host_root / "flaky" / c.module
    src = source_file(module_dir, target)
    if src is None:
        res.reason = f"no source file for {target}"
        return res
    project_root = repro.host_root / "flaky"
    res.source = src.relative_to(project_root).as_posix()

    by_test = cov.methods_by_test(target)
    victim_methods = set(by_test.get(c.flaky_test, {}))
    others = {t: ms for t, ms in by_test.items() if t != c.flaky_test and t in deterministic}
    methods = sorted(m for m in victim_methods if m != "<clinit>"
                     and sum(1 for ms in others.values() if m in ms) >= 2)
    res.methods = methods
    funnel["candidate_methods"] = len(methods)
    if not methods:
        res.reason = "no target method covered by the flaky test and >= 2 deterministic tests"
        return res

    work = repro.host_root / "mutants"
    shutil.rmtree(work, ignore_errors=True)
    rel_src = f"{paths.C_SRC}/flaky/{res.source}"
    r = repro.box.sh(f"java -jar {paths.C_JARS}/fb-tools.jar mutate --src {shlex.quote(rel_src)} "
                     f"--class {shlex.quote(target)} --methods {shlex.quote(','.join(methods))} "
                     f"--out {paths.C_SRC}/mutants", timeout=600)
    if r.rc != 0:
        res.reason = "mutator failed: " + r.output[-300:]
        return res
    mutants = list(csv.DictReader(open(work / "mutants.tsv"), delimiter="\t"))
    funnel["generated"] = len(mutants)
    order = list(range(len(mutants)))
    random.Random(res.seed).shuffle(order)

    original = src.read_text(encoding="utf-8", errors="surrogateescape")
    victim_class = c.test_class
    # Test classes whose tests cover any candidate method: running them finds every possible killer.
    covering = sorted({t for t, ms in others.items() if any(m in ms for m in methods)})
    test_classes = sorted({t.split("#", 1)[0] for t in covering})

    rf.copy_tree(repro.host_root / "flaky", repro.host_root / "mutant")
    if delay_tree:
        rf.copy_tree(repro.host_root / delay_tree, repro.host_root / "mutant_delay")
    mutant_src = repro.host_root / "mutant" / res.source
    # Mutants change only the module, so the mutant trees reuse the flaky tree's upstream install.
    repro.share_install("mutant", "flaky")
    if delay_tree:
        repro.share_install("mutant_delay", delay_tree)
    try:
        for idx in order:
            m = mutants[idx]
            funnel["examined"] += 1
            text = (work / f"{m['id']}.java").read_text(encoding="utf-8", errors="surrogateescape")
            mutant_src.write_text(text, encoding="utf-8", errors="surrogateescape")
            run = repro.run_suite("mutant", extra="-Dtest=" + shlex.quote(",".join(test_classes)))
            if run.result.rc != 0 or not run.reports:
                log(f"  {m['id']} {m['operator']} L{m['line']}: does not compile")
                continue
            funnel["compiled"] += 1
            killers = sorted(t for t in covering if t in run.reports and run.reports[t].failed)
            if len(killers) < 2:
                log(f"  {m['id']} {m['operator']} L{m['line']}: killed by {len(killers)}")
                continue
            funnel["killed_2plus"] += 1
            in_class = [k for k in killers if k.split("#", 1)[0] == victim_class]
            outside = [k for k in killers if k.split("#", 1)[0] != victim_class]
            if not in_class or not outside:
                log(f"  {m['id']}: killers not in both the flaky test's class and another class")
                continue
            funnel["killed_l1_l2"] += 1
            alone_in = _fail_alone(repro, in_class)
            alone_out = _fail_alone(repro, outside) if alone_in else []
            if not alone_in or not alone_out:
                log(f"  {m['id']}: killers do not fail with their class run alone")
                continue
            funnel["killed_alone"] += 1

            if delay_tree and not _apply_text_patch(original, text, repro.host_root / "mutant_delay" / res.source):
                log(f"  {m['id']}: conflicts with the delay patch")
                continue
            fail_tree = "mutant_delay" if delay_tree else "mutant"
            if not _behaves(repro, "mutant", fail_tree, 1):
                log(f"  {m['id']}: changes the flaky test's behavior")
                _restore_delay(repro, delay_tree, res.source)
                continue
            funnel["flaky_unchanged"] += 1
            if not _behaves(repro, "mutant", fail_tree, REPEATS):
                log(f"  {m['id']}: flaky test not deterministic on the mutant (20/20)")
                _restore_delay(repro, delay_tree, res.source)
                continue
            funnel["recheck_20"] += 1
            res.ok = True
            res.mutant = m
            res.killers = killers
            res.killer_messages = {k: (run.reports[k].message or "")[:2000] for k in killers}
            res.standalone_killers = sorted(alone_in + alone_out)
            log(f"  chose {m['id']} {m['operator']} {m['method']} L{m['line']}: killed by {len(killers)}")
            return res
        res.reason = "no mutant survives the filters"
        return res
    finally:
        mutant_src.write_text(original, encoding="utf-8", errors="surrogateescape")


def _fail_alone(repro: Repro, killers: list[str], max_classes: int = 3) -> list[str]:
    """Killers that also fail when their test class runs alone (`-Dtest=<SimpleClass>`, as in the prompt).
    Tries up to `max_classes` classes, in sorted order, and stops at the first that has any."""
    by_class: dict[str, list[str]] = {}
    for k in killers:
        by_class.setdefault(k.split("#", 1)[0], []).append(k)
    for cls in sorted(by_class)[:max_classes]:
        run = repro.run_suite("mutant", extra="-Dtest=" + shlex.quote(cls.rsplit(".", 1)[-1]))
        alone = [k for k in by_class[cls] if k in run.reports and run.reports[k].failed]
        if alone:
            return alone
    return []


def _behaves(repro: Repro, pass_tree: str, fail_tree: str, n: int) -> bool:
    for _ in range(n):
        if repro.run(pass_tree, PASSING).status != "pass":
            return False
        if not _failed(repro.run(fail_tree, FAILING).status):
            return False
    return True


def _failed(status: str) -> bool:
    return status in ("failure", "error")


def _apply_text_patch(original: str, mutated: str, target: Path) -> bool:
    """Applies the mutant's change to a file that also carries the delay patch."""
    diff = "".join(difflib.unified_diff(original.splitlines(True), mutated.splitlines(True), "a/f", "b/f"))
    patch_file = target.with_suffix(".mutant.patch")
    patch_file.write_text(diff, encoding="utf-8", errors="surrogateescape")
    backup = target.with_suffix(".orig-delay")
    shutil.copy2(target, backup)
    r = subprocess.run(["patch", "-s", "-f", str(target), "-i", str(patch_file)], capture_output=True)
    patch_file.unlink(missing_ok=True)
    if r.returncode != 0:
        shutil.copy2(backup, target)
    target.with_suffix(".java.rej").unlink(missing_ok=True)
    return r.returncode == 0


def _restore_delay(repro: Repro, delay_tree: str | None, source: str) -> None:
    if not delay_tree:
        return
    target = repro.host_root / "mutant_delay" / source
    backup = target.with_suffix(".orig-delay")
    if backup.exists():
        shutil.copy2(backup, target)
        backup.unlink()
