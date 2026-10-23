"""Reading Surefire XML reports and the failure traces they contain."""
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Frame:
    loader: str
    module: str
    module_version: str
    cls: str
    method: str
    file: str
    line: int

    def spec(self) -> str:
        return "|".join([self.loader, self.module, self.module_version, self.cls, self.method, self.file,
                         str(self.line)])


@dataclass
class Thrown:
    type: str
    message: str | None
    frames: list[Frame] = field(default_factory=list)


@dataclass
class TestOutcome:
    test: str            # Class#method
    status: str          # pass | failure | error | skipped
    time: float = 0.0
    message: str | None = None
    exc_type: str | None = None
    trace: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    @property
    def failed(self) -> bool:
        return self.status in ("failure", "error")


def read_reports(report_dirs: list[Path]) -> dict[str, TestOutcome]:
    """All test outcomes in TEST-*.xml files under the given directories, keyed by Class#method.

    When a test appears more than once (reruns, repeated suites), the last report read wins for pass but
    a failure is never overwritten by a later pass of the same name in the same set of reports.
    """
    out: dict[str, TestOutcome] = {}
    for d in report_dirs:
        if not d.exists():
            continue
        for f in sorted(d.rglob("TEST-*.xml")):
            for o in parse_report(f):
                prev = out.get(o.test)
                if prev is None or not prev.failed:
                    out[o.test] = o
    return out


def parse_report(path: Path) -> list[TestOutcome]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    outs = []
    for tc in root.iter("testcase"):
        cls = tc.get("classname") or ""
        name = tc.get("name") or ""
        status, message, exc_type, trace = "pass", None, None, ""
        for tag in ("failure", "error"):
            el = tc.find(tag)
            if el is not None:
                status = tag
                message = el.get("message")
                exc_type = el.get("type")
                trace = (el.text or "").strip()
                break
        if tc.find("skipped") is not None:
            status = "skipped"
        try:
            t = float(tc.get("time") or 0)
        except ValueError:
            t = 0.0
        outs.append(TestOutcome(f"{cls}#{name}", status, t, message, exc_type, trace))
    return outs


_FRAME = re.compile(r"^\s*at\s+(?P<body>.+?)\((?P<src>[^()]*)\)\s*$")
_MORE = re.compile(r"^\s*\.\.\.\s+(\d+)\s+more\s*$")
_TYPE = re.compile(r"^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$")


def parse_trace(trace: str, fallback_type: str | None = None, fallback_message: str | None = None) -> list[Thrown]:
    """Parses a printed stack trace into throwables, outermost first.

    Each block is a header (``type: message``, possibly over several lines) followed by ``at`` frames; a
    new block starts at ``Caused by:``. ``... N more`` copies the enclosing block's last N frames.
    Suppressed sections (indented two tabs) are dropped.
    """
    blocks: list[tuple[list[str], list[str]]] = []
    for line in trace.splitlines():
        if line.startswith("\t\t") or line.lstrip().startswith("Suppressed:"):
            continue
        stripped = line.strip()
        if stripped.startswith("Caused by:"):
            blocks.append(([stripped[len("Caused by:"):].strip()], []))
        elif not blocks:
            if stripped:
                blocks.append(([line], []))
        elif _FRAME.match(line) or _MORE.match(line):
            blocks[-1][1].append(line)
        elif not blocks[-1][1]:
            blocks[-1][0].append(line)

    chain: list[Thrown] = []
    for header, frame_lines in blocks:
        text = "\n".join(header)
        head, sep, rest = text.partition(":")
        if sep and _TYPE.match(head.strip()):
            thrown = Thrown(head.strip(), rest[1:] if rest.startswith(" ") else rest)
        elif _TYPE.match(text.strip()):
            thrown = Thrown(text.strip(), None)
        else:
            thrown = Thrown(fallback_type or "java.lang.AssertionError", text)
        for line in frame_lines:
            m = _FRAME.match(line)
            if m:
                thrown.frames.append(_frame(m.group("body"), m.group("src")))
            elif chain:
                n = int(_MORE.match(line).group(1))
                thrown.frames.extend(chain[-1].frames[-n:] if n else [])
        chain.append(thrown)

    if not chain:
        return [Thrown(fallback_type or "java.lang.AssertionError", fallback_message)]
    if fallback_message is not None and chain[0].type == fallback_type:
        # The report's message attribute is authoritative for the outermost throwable.
        chain[0].message = fallback_message
    return chain


def _frame(body: str, src: str) -> Frame:
    loader = module = version = ""
    if "/" in body:
        prefix, _, qualified = body.rpartition("/")
        parts = prefix.split("/")
        if len(parts) == 2:
            loader, module = parts
        elif len(parts) == 1:
            # "java.base/..." is a module; "app//..." leaves an empty module after a loader.
            module = parts[0]
        if body.startswith(prefix + "//"):
            loader, module = prefix.rstrip("/"), ""
        body = qualified
        if "@" in module:
            module, version = module.split("@", 1)
    cls, _, method = body.rpartition(".")
    file, line = "", -1
    if src == "Native Method":
        line = -2
    elif src == "Unknown Source":
        pass
    elif ":" in src:
        file, ln = src.rsplit(":", 1)
        line = int(ln) if ln.isdigit() else -1
    else:
        file = src
    return Frame(loader, module, version, cls, method, file, line)
