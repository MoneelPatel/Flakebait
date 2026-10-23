"""ReproFlake records and module workspaces.

A workspace is one extracted zip under data/work/<zip>/ with:
  Flaky/            the module's project at the flaky version (pristine; never modified)
  Flakym2/.m2       the cached Maven repository for offline builds
  Fixed.patch       the developer fix
  FlakyCodeChange.patch   TD only: the delay injection that makes the failure deterministic
"""
import csv
import functools
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import paths

# Build-noise switches ReproFlake passes to every Maven call.
MVN_SKIPS = (
    "-Ddependency-check.skip=true -Dgpg.skip=true -DfailIfNoTests=false "
    "-Dskip.installnodenpm -Dskip.npm -Dskip.yarn -Dlicense.skip -Dcheckstyle.skip "
    "-Drat.skip -Denforcer.skip -Danimal.sniffer.skip -Dmaven.javadoc.skip "
    "-Dfindbugs.skip -Dwarbucks.skip -Dmodernizer.skip -Dimpsort.skip "
    "-Dmdep.analyze.skip -Dpgpverify.skip -Dxml.skip -Dcobertura.skip=true "
    "-Dspotless.skip=true -Dspotless.check.skip=true -Dossindex.skip=true "
    "-Dmaven.bundle.plugin.skip=true -Dmaven.parallel.force=false "
    "-Djacoco.skip=true -Dspotbugs.skip=true -Dpmd.skip=true -Dcpd.skip=true "
    "-Drevapi.skip=true -Djapicmp.skip=true -Dbuildnumber.skip=true"
).split()


@dataclass(frozen=True)
class Candidate:
    category: str
    position: int
    result_container: str
    project: str
    module: str
    zip: str
    flaky_test: str      # Class#method
    polluter: str        # OD only
    java: str
    nondex_seed: str     # ID only
    url: str

    @property
    def test_class(self) -> str:
        return self.flaky_test.split("#", 1)[0]

    @property
    def test_method(self) -> str:
        return self.flaky_test.split("#", 1)[1] if "#" in self.flaky_test else ""

    @property
    def upstream(self) -> str:
        """The upstream repository, which the diversity caps count (config/project_aliases.yaml)."""
        return upstream_project(self.project)

    @property
    def module_key(self) -> tuple[str, str]:
        return (self.upstream, self.module)


@functools.lru_cache(maxsize=None)
def _aliases() -> tuple[tuple[str, str], ...]:
    import yaml   # not installed in the oracle's container, which never needs the aliases
    data = yaml.safe_load(open(paths.ROOT / "config" / "project_aliases.yaml"))
    return tuple(sorted(data["prefixes"].items(), key=lambda kv: -len(kv[0])))


def upstream_project(project: str) -> str:
    for prefix, repo in _aliases():
        if project.startswith(prefix):
            return repo
    return project


def load_candidates() -> list[Candidate]:
    rows = csv.DictReader(open(paths.REPORTS / "candidate_order.csv", newline=""))
    out = []
    for r in rows:
        out.append(Candidate(
            category=r["category"], position=int(r["position"]), result_container=r["result_container"],
            project=r["project"], module=r["module"], zip=r["zip"], flaky_test=r["flaky_test"].strip(),
            polluter=r["polluter"].strip(), java=r["java"].strip() or "8", nondex_seed=r["nondex_seed"].strip(),
            url=r["url"]))
    return out


@dataclass(frozen=True)
class Workspace:
    root: Path

    @property
    def flaky(self) -> Path:
        return self.root / "Flaky"

    @property
    def m2(self) -> Path:
        return self.root / "Flakym2" / ".m2"

    @property
    def fixed_patch(self) -> Path:
        return self.root / "Fixed.patch"

    @property
    def delay_patch(self) -> Path:
        return self.root / "FlakyCodeChange.patch"


def ensure_zip(c: Candidate) -> Path:
    z = paths.ZIPS / f"{c.zip}.zip"
    ok = paths.ZIPS / f"{c.zip}.zip.ok"
    if not ok.exists():
        paths.ZIPS.mkdir(parents=True, exist_ok=True)
        subprocess.run(["curl", "-sfL", "--retry", "3", "-C", "-", "-o", str(z), c.url], check=True)
        ok.touch()
    return z


def workspace(c: Candidate) -> Workspace:
    """Extract the candidate's zip once. Archives are untrusted: entries escaping the target are refused."""
    root = paths.WORK / c.zip
    done = root / ".extracted"
    if not done.exists():
        z = ensure_zip(c)
        tmp = paths.WORK / f".{c.zip}.tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        with zipfile.ZipFile(z) as zf:
            for info in zf.infolist():
                target = (tmp / info.filename).resolve()
                if not str(target).startswith(str(tmp.resolve())):
                    raise ValueError(f"unsafe path in {z}: {info.filename}")
            zf.extractall(tmp)
            _restore_modes(zf, tmp)
        inner = tmp / c.zip
        src = inner if inner.is_dir() else tmp
        shutil.rmtree(root, ignore_errors=True)
        shutil.move(str(src), str(root))
        shutil.rmtree(tmp, ignore_errors=True)
        done.touch()
    return Workspace(root)


def _restore_modes(zf: zipfile.ZipFile, dest: Path) -> None:
    """zipfile drops Unix permissions; restore the executable bits (e.g. mvnw, scripts)."""
    for info in zf.infolist():
        mode = (info.external_attr >> 16) & 0o777
        if mode & 0o111:
            p = dest / info.filename
            if p.is_file():
                p.chmod(p.stat().st_mode | 0o111)


def copy_tree(src: Path, dest: Path) -> None:
    """Fast copy (APFS clone on macOS), without build outputs or VCS data."""
    shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cp", "-cR", str(src), str(dest)], check=True)
    for junk in ("target", ".nondex", ".dtfixingtools", "flaky-result", ".git"):
        subprocess.run(["find", str(dest), "-name", junk, "-prune", "-exec", "rm", "-rf", "{}", "+"],
                       check=False, capture_output=True)


def apply_patch(tree: Path, patch: Path) -> bool:
    r = subprocess.run(["patch", "-p1", "-s", "-f", "-d", str(tree), "-i", str(patch)],
                       capture_output=True, text=True)
    return r.returncode == 0
