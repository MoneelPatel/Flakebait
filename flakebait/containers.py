"""Long-lived build containers: one per working tree, offline, with commands run through docker exec."""
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import paths


def image_for(java: str) -> str:
    v = {"1.8": "8", "8": "8", "11": "11", "17": "17"}.get(str(java).strip(), "8")
    return f"fb-base:{v}"


@dataclass
class Result:
    rc: int
    output: str
    seconds: float
    timed_out: bool = False


@dataclass
class Box:
    """A running container with the tree at /app/source and the module's Maven repo at /root/.m2."""
    image: str
    source: Path
    m2: Path
    extra_mounts: list[tuple[Path, str, bool]] = field(default_factory=list)
    network: str = "none"
    name: str = field(default_factory=lambda: f"fb-{uuid.uuid4().hex[:10]}")

    def __enter__(self):
        mounts = [(self.source, paths.C_SRC, False), (self.m2, paths.C_M2, False), (paths.JARS, paths.C_JARS, True)]
        args = ["docker", "run", "-d", "--rm", "--name", self.name, "--network", self.network,
                "-w", paths.C_SRC, "--memory", os.environ.get("FB_MEM", "3g")]
        for host, target, ro in mounts + self.extra_mounts:
            args += ["--mount", f"type=bind,source={host},target={target}" + (",readonly" if ro else "")]
        args += [self.image, "sleep", "infinity"]
        subprocess.run(args, check=True, capture_output=True)
        # ReproFlake's tooling (NonDex, custom Surefire) is merged into the module's repo without overwriting.
        self.sh(f"cp -rn {paths.C_TOOLS_M2}/. {paths.C_M2}/repository/ 2>/dev/null; true", timeout=600)
        return self

    def __exit__(self, *exc):
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)

    def alive(self) -> bool:
        r = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", self.name], capture_output=True, text=True)
        return r.stdout.strip() == "true"

    def sh(self, command: str, timeout: float = 1800) -> Result:
        start = time.time()
        try:
            p = subprocess.run(["docker", "exec", self.name, "bash", "-lc", command],
                               capture_output=True, text=True, timeout=timeout, errors="replace")
            return Result(p.returncode, p.stdout + p.stderr, time.time() - start)
        except subprocess.TimeoutExpired as e:
            # Kill whatever Maven left running so the next command starts clean.
            subprocess.run(["docker", "exec", self.name, "pkill", "-9", "java"], capture_output=True)
            out = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            return Result(-1, out, time.time() - start, timed_out=True)


class LocalBox:
    """Same interface as Box, for code that already runs inside a container (the oracle)."""

    def sh(self, command: str, timeout: float = 1800) -> Result:
        start = time.time()
        try:
            p = subprocess.run(["bash", "-lc", command], capture_output=True, text=True, timeout=timeout,
                               errors="replace")
            return Result(p.returncode, p.stdout + p.stderr, time.time() - start)
        except subprocess.TimeoutExpired as e:
            out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            return Result(-1, out, time.time() - start, timed_out=True)
