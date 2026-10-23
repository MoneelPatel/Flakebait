"""Per-test JaCoCo coverage of a module's production classes, and the flaky test's target class."""
import csv
import re
import shlex
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .repro import Repro, RunResult


@dataclass
class Coverage:
    # (test, top-level class) -> {method name -> covered lines}
    rows: list[dict]
    suite: RunResult

    def methods_by_test(self, cls: str) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = defaultdict(dict)
        for r in self.rows:
            if r["class"] == cls:
                out[r["test"]][r["method"]] = out[r["test"]].get(r["method"], 0) + int(r["covered_lines"])
        return out

    def classes_of(self, test: str) -> dict[str, int]:
        """Top-level production classes covered by a test, with covered line counts (nested classes folded in)."""
        out: dict[str, int] = defaultdict(int)
        for r in self.rows:
            if r["test"] == test:
                out[r["class"].split("$", 1)[0]] += int(r["covered_lines"])
        return dict(out)


def collect(repro: Repro, tree: str, timeout: float = 900) -> Coverage:
    """Runs the module suite with per-test coverage dumps (victim under the passing configuration)."""
    m = repro.c.module
    execs = f"{paths.C_SRC}/{tree}.cov/execs"
    out_csv = f"{paths.C_SRC}/{tree}.cov/coverage.csv"
    exts = f"{paths.C_JARS}/fb-ext.jar"
    if repro.c.category == "OD":
        exts += f":{paths.C_OD_EXT}"
    repro.box.sh(f"rm -rf {paths.C_SRC}/{tree}.cov && mkdir -p {execs}", timeout=120)
    # OD's mvn already carries -Dmaven.ext.class.path; a later -D on the same command line wins.
    suite = repro.run_suite(tree, timeout=timeout, extra=(
        f"-Dmaven.ext.class.path={exts} -Dfb.coverage={execs} -Dfb.jacoco={paths.C_JARS}/jacocoagent.jar"))
    classes = f"{paths.C_SRC}/{tree}/{m}/target/classes"
    r = repro.box.sh(f"java -jar {paths.C_JARS}/fb-tools.jar coverage --classes {shlex.quote(classes)} "
                     f"--execs {execs} --out {out_csv}", timeout=900)
    host_csv = repro.host_root / f"{tree}.cov" / "coverage.csv"
    rows = list(csv.DictReader(open(host_csv))) if r.rc == 0 and host_csv.exists() else []
    return Coverage(rows, suite)


def _simple(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def target_class(cov: Coverage, victim: str) -> str | None:
    """The production class the flaky test exercises: the class named after the test class if it is
    covered (FooTest, TestFoo, FooTests -> Foo), otherwise the class with the most lines covered."""
    covered = cov.classes_of(victim)
    if not covered:
        return None
    test_simple = _simple(victim.split("#", 1)[0])
    stem = re.sub(r"^(Test)|(Tests?|TestCase|IT)$", "", test_simple)
    named = [c for c in covered if _simple(c) == stem]
    if named:
        return named[0]
    return max(sorted(covered), key=lambda c: covered[c])


def source_file(module_dir: Path, cls: str) -> Path | None:
    rel = Path(*cls.split(".")).with_suffix(".java")
    preferred = module_dir / "src" / "main" / "java" / rel
    if preferred.exists():
        return preferred
    for p in module_dir.rglob(rel.name):
        if "target" not in p.parts and "test" not in p.parts and p.as_posix().endswith(rel.as_posix()):
            return p
    return None
