"""The two deterministic configurations of a flaky test, run inside a build container.

passing  default Maven run of the victim alone: default order, no NonDex, one run, no delay.
failing  ReproFlake's reproduction:
           ID   NonDex with the stored seed, victim only (nondex-maven-plugin 2.1.1, one run)
           OD   custom Surefire runs the polluter, then the victim, in one JVM (runOrder=testorder)
           NIO  the victim runs twice in one JVM; the second run is the one reported (fb-ext repeat mode)
           TD   the victim alone on a copy of the tree with ReproFlake's delay patch applied

Trees live side by side under /app/source/<name> in one container. They share the module's Maven
repository, so `mvn install -am` is rerun whenever the active tree changes.
"""
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .containers import Box, Result
from .reproflake import MVN_SKIPS, Candidate
from .surefire import TestOutcome, read_reports

PASSING, FAILING = "passing", "failing"
MVN = "mvn -o -B -Dstyle.color=never"


@dataclass
class RunResult:
    victim: TestOutcome | None
    result: Result
    reports: dict[str, TestOutcome]

    @property
    def status(self) -> str:
        if self.result.timed_out:
            return "timeout"
        return self.victim.status if self.victim else "missing"


def patch_stays_in_module(patch: Path, module: str) -> bool:
    """True when every file the patch touches lies inside the module (upstream modules unchanged)."""
    prefix = "" if module in (".", "") else module.rstrip("/") + "/"
    files = re.findall(r"^\+\+\+ (?:b/)?(\S+)", patch.read_text(errors="replace"), flags=re.M)
    return all(f == "/dev/null" or f.startswith(prefix) for f in files) if prefix else True


class Repro:
    def __init__(self, cand: Candidate, box: Box, host_root: Path, src_root: str = paths.C_SRC):
        self.c = cand
        self.box = box
        self.host_root = host_root    # host directory mounted at src_root (the same directory when run locally)
        self.src_root = src_root
        self.installed: str | None = None
        # Trees that differ only inside the module can share one install of the upstream modules.
        self.install_key: dict[str, str] = {}

    @property
    def mvn(self) -> str:
        """ReproFlake's OD image loads the custom-Surefire extension for every Maven call; some modules only
        build offline with it (it disables plugins such as the enforcer)."""
        if self.c.category == "OD":
            return f"{MVN} -Dmaven.ext.class.path={paths.C_OD_EXT}"
        return MVN

    def _cd(self, tree: str) -> str:
        return f"cd {self.src_root}/{shlex.quote(tree)}"

    def skips(self) -> str:
        return " ".join(MVN_SKIPS)

    def build(self, tree: str, timeout: float = 1800) -> Result:
        """Offline install of the module and its upstream modules (tests compiled, not run)."""
        r = self.box.sh(f"{self._cd(tree)} && {self.mvn} install -DskipTests -pl {shlex.quote(self.c.module)} -am "
                        f"{self.skips()}", timeout=timeout)
        self.installed = self.install_key.get(tree, tree) if r.rc == 0 else None
        return r

    def ensure_built(self, tree: str) -> Result | None:
        if self.installed != self.install_key.get(tree, tree):
            r = self.build(tree)
            if r.rc != 0:
                return r
        return None

    def share_install(self, tree: str, with_tree: str) -> None:
        self.install_key[tree] = self.install_key.get(with_tree, with_tree)

    def _clean_reports(self, tree: str) -> None:
        m = shlex.quote(self.c.module)
        self.box.sh(f"{self._cd(tree)} && rm -rf {m}/target/surefire-reports {m}/.nondex", timeout=120)

    def module_dir(self, tree: str) -> Path:
        return self.host_root / tree / self.c.module

    def run(self, tree: str, config: str, timeout: float = 900) -> RunResult:
        """One execution of the victim under a configuration. For TD failing, `tree` must carry the delay."""
        err = self.ensure_built(tree)
        if err is not None:
            return RunResult(None, err, {})
        self._clean_reports(tree)
        m = shlex.quote(self.c.module)
        victim = shlex.quote(self.c.flaky_test)
        base = f"{self._cd(tree)} && {self.mvn} -pl {m}"
        report_dirs = [self.module_dir(tree) / "target" / "surefire-reports"]

        if config == PASSING or self.c.category == "TD":
            cmd = f"{base} test -Dtest={victim} {self.skips()}"
        elif self.c.category == "ID":
            seed = f"-DnondexSeed={self.c.nondex_seed}" if self.c.nondex_seed else ""
            cmd = (f"{base} edu.illinois:nondex-maven-plugin:2.1.1:nondex {seed} -DnondexRuns=1 "
                   f"-Dtest={victim} {self.skips()}")
        elif self.c.category == "OD":
            order = shlex.quote(f"{self.c.polluter},{self.c.flaky_test}")
            cmd = (f"{base} test -Dsurefire.runOrder=testorder -Dtest={order} {self.skips()}")
        elif self.c.category == "NIO":
            cmd = (f"{base} -Dmaven.ext.class.path={paths.C_JARS}/fb-ext.jar "
                   f"-Dfb.repeat={victim} test -Dtest={victim} {self.skips()}")
        else:
            raise ValueError(self.c.category)

        r = self.box.sh(cmd, timeout=timeout)
        if config == FAILING and self.c.category == "ID":
            report_dirs = self._nondex_dirs(tree, r.output)
        reports = read_reports(report_dirs)
        return RunResult(self._victim(reports), r, reports)

    def run_suite(self, tree: str, timeout: float = 600, extra: str = "") -> RunResult:
        """The module's whole test suite in default order (passing configuration for the victim)."""
        err = self.ensure_built(tree)
        if err is not None:
            return RunResult(None, err, {})
        self._clean_reports(tree)
        m = shlex.quote(self.c.module)
        r = self.box.sh(f"{self._cd(tree)} && {self.mvn} -pl {m} test -Dmaven.test.failure.ignore=true "
                        f"{extra} {self.skips()}", timeout=timeout)
        reports = read_reports([self.module_dir(tree) / "target" / "surefire-reports"])
        return RunResult(self._victim(reports), r, reports)

    def _nondex_dirs(self, tree: str, output: str) -> list[Path]:
        ids = [i for i in re.findall(r"nondexExecid=(\S+)", output) if not i.startswith("clean_")]
        base = self.module_dir(tree) / ".nondex"
        return [base / i for i in dict.fromkeys(ids)]

    def _victim(self, reports: dict[str, TestOutcome]) -> TestOutcome | None:
        return reports.get(self.c.flaky_test)
