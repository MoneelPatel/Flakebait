"""Realistic faults and issue reports for the repair tasks (deviation #32; replaces PIT mutants).

Following current bug-fixing benchmarks (SWE-bench, Defects4J, GitBug-Java: real bug fixes; SWE-smith, R2E-Gym:
synthetic bugs from reverted fixes or LM rewrites, with a written issue), each selected flaky test gets one fault
in its target class, from the first source that yields one:

  1. revert   a real bug-fix commit from the upstream repository's history before the snapshot ReproFlake built
              (SWE-smith's "PR mirror"): the commit's change to the target source file is reverse-applied to the
              snapshot. Commits are fix-like by message; at most MAX_REVERTS are examined, in seeded random order.
  2. llm      a bug written by the study model (SWE-smith's "LM rewrite"): N_LLM realistic logic errors in the
              methods the flaky test and >= 2 deterministic tests cover, examined in seeded random order; up to
              LLM_ROUNDS rounds, each told why the previous round's bugs were rejected.
  3. mutant   last resort: the PIT mutant selection validated for the test (check (d)).

Every candidate must pass the same filters as the mutants did (seeding.BugContext.check): compiles, killed by >= 2
deterministic tests in and outside the flaky test's class that also fail with their class run alone, flaky test
unchanged 20/20. The chosen fault then gets an issue report written by the model from the fault's diff, the
detecting tests' failures and, for reverts, the original commit message and linked issue: the symptom a user or
developer would report (expected vs. actual, how to trigger it), never the test output, the fix, or the location.

Upstream repositories are cloned (bare, blobless) under data/upstream/ and only read with git. Model calls go
through the meter (llm.Session) and count toward the study budget.

Output: data/bugs/<result_container>.json (+ <result_container>.java, the faulty source file).
Usage: uv run python -m flakebait.bugs [--only <result_container>] [--workers 2] [--usd-cap 3]
"""
import argparse
import hashlib
import json
import random
import re
import subprocess
import tempfile
import threading
import time
import traceback
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from . import paths, reproflake as rf
from .containers import Box, image_for
from .coverage import Coverage
from .instances import FORBIDDEN, accepted_candidates
from .llm import Session
from .repro import Repro, patch_stays_in_module
from .seeding import BugContext
from .selection import EVAL_DIR

BUGS = paths.DATA / "bugs"
UPSTREAM = paths.DATA / "upstream"
MAX_REVERTS = 12          # revert candidates examined per test (each costs Maven runs)
MAX_COMMITS = 400         # history depth searched for the target file
MAX_CHANGED_LINES = 60    # larger fixes are refactorings more often than bug fixes
N_LLM = 8
LLM_ROUNDS = 3
FIX_RE = re.compile(r"\b(fix(e[sd])?|bug|issue|npe|null ?pointer|incorrect|wrong|broken|regression|"
                    r"error|fail(s|ure|ing)?|crash|handle|correct(ly)?)\b|\b[A-Z][A-Z0-9]+-\d+\b|#\d+", re.I)
SKIP_RE = re.compile(r"\b(typo|javadoc|checkstyle|format(ting)?|license|refactor|rename|cleanup|clean up|"
                     r"revert|merge|test(s)?\b only|deprecat|whitespace|import)", re.I)


def bug_seed(test: str) -> int:
    base = yaml.safe_load(open(paths.CONFIG / "seeds.yaml"))["mutant_choice"]
    return int(hashlib.sha256(f"{base}:bug:{test}".encode()).hexdigest()[:16], 16)


# ------------------------------------------------------------------------------------------- upstream history

def upstream(c: rf.Candidate) -> tuple[str, str]:
    """(repository URL, snapshot commit) from the archive's flaky_info.txt."""
    info = (rf.workspace(c).root / "flaky_info.txt").read_text()
    m = re.search(r"(https://github\.com/[\w.-]+/[\w.-]+?)(?:\.git)?\s+at commit\s+([0-9a-f]{7,40})", info)
    if not m:
        raise RuntimeError("no repository/commit in flaky_info.txt")
    return m.group(1), m.group(2)


_CLONE_LOCKS: dict[str, threading.Lock] = {}
_GUARD = threading.Lock()


def clone(url: str) -> Path:
    name = "__".join(url.rstrip("/").split("/")[-2:]) + ".git"
    dest = UPSTREAM / name
    with _GUARD:
        lock = _CLONE_LOCKS.setdefault(name, threading.Lock())
    with lock:
        if not (dest / "HEAD").exists():
            UPSTREAM.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", "-q", "--bare", "--filter=blob:none", url, str(dest)], check=True,
                           capture_output=True, timeout=3600)
    return dest


def git(repo: Path, *args: str, timeout: int = 600) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, errors="replace",
                          timeout=timeout).stdout


def changed_code_lines(diff: str) -> int:
    n = 0
    for line in diff.splitlines():
        if line[:1] in "+-" and not line.startswith(("+++", "---")):
            body = line[1:].strip()
            if body and not body.startswith(("//", "*", "/*", "import ", "@Override")):
                n += 1
    return n


def hunks(diff: str) -> list[str]:
    """Each hunk of a one-file diff, with the file header, as a diff of its own."""
    lines = diff.splitlines()
    header = [l for l in lines[:6] if l.startswith(("---", "+++"))]
    out, cur = [], []
    for l in lines:
        if l.startswith("@@"):
            if cur:
                out.append(cur)
            cur = [l]
        elif cur:
            cur.append(l)
    if cur:
        out.append(cur)
    return ["\n".join(header + h) + "\n" for h in out]


def reverse_apply(original: str, diff: str) -> str | None:
    """The snapshot file with the commit's change undone, or None if it does not apply (fuzz <= 2)."""
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "F.java"
        f.write_text(original, encoding="utf-8", errors="surrogateescape")
        body = "".join(l + "\n" for l in diff.splitlines() if not l.startswith(("diff --git", "index ")))
        r = subprocess.run(["patch", "-R", "-s", "-f", "-F2", "--no-backup-if-mismatch", str(f)],
                           input=body.encode("utf-8", "surrogateescape"), capture_output=True)
        if r.returncode != 0:
            return None
        text = f.read_text(encoding="utf-8", errors="surrogateescape")
        return text if text != original else None


def mined_candidates(c: rf.Candidate, source: str, original: str, seed: int, log) -> list[dict]:
    url, sha = upstream(c)
    repo = clone(url)
    if git(repo, "cat-file", "-t", f"{sha}:{source}").strip() != "blob":
        log(f"  {source} not at {sha[:10]} in {url}")
        return []
    raw = git(repo, "log", "--no-merges", f"-n{MAX_COMMITS}", "--format=%H%x1f%s%x1f%b%x1e", sha, "--", source)
    out = []
    for rec in raw.split("\x1e"):
        parts = rec.strip().split("\x1f")
        if len(parts) < 3:
            continue
        h, subject, body = parts[0], parts[1], parts[2]
        if not FIX_RE.search(subject + " " + body[:500]) or SKIP_RE.search(subject):
            continue
        diff = git(repo, "diff", "--no-color", "-U3", f"{h}^", h, "--", source)
        n = changed_code_lines(diff)
        if not diff or n == 0 or n > MAX_CHANGED_LINES:
            continue
        # The whole change first; if it no longer applies to the snapshot, each hunk on its own (a partial
        # revert of a real fix is still a real past bug).
        pieces = [("", diff)]
        if reverse_apply(original, diff) is None:
            pieces = [(f"-h{i}", hk) for i, hk in enumerate(hunks(diff)) if changed_code_lines(hk)]
        for suffix, part in pieces:
            text = reverse_apply(original, part)
            if text is None:
                continue
            out.append({"id": f"rev-{h[:10]}{suffix}", "kind": "revert", "commit": h, "repository": url,
                        "subject": subject, "message": body.strip()[:3000], "fix_diff": part,
                        "partial": bool(suffix), "text": text})
    log(f"  history: {len(out)} reverts of fix-like commits (or their hunks) apply to the snapshot")
    random.Random(seed).shuffle(out)
    return out[:MAX_REVERTS]


def linked_issue(cand: dict) -> str:
    """Title and description of the issue a reverted commit references (Apache JIRA or GitHub), if any."""
    text = cand["subject"] + " " + cand["message"]
    try:
        m = re.search(r"\b([A-Z][A-Z0-9]+-\d+)\b", text)
        if m:
            u = f"https://issues.apache.org/jira/rest/api/2/issue/{m.group(1)}?fields=summary,description"
            j = json.loads(urllib.request.urlopen(u, timeout=30).read())
            return f"{m.group(1)}: {j['fields']['summary']}\n\n{(j['fields'].get('description') or '')[:4000]}"
        m = re.search(r"(?:#|issues/|pull/)(\d+)\b", text)
        if m:
            owner_repo = "/".join(cand["repository"].rstrip("/").split("/")[-2:])
            r = subprocess.run(["gh", "api", f"repos/{owner_repo}/issues/{m.group(1)}", "--jq",
                                '.title + "\\n\\n" + (.body // "")'], capture_output=True, text=True, timeout=60)
            if r.returncode == 0 and r.stdout.strip():
                return f"#{m.group(1)}: {r.stdout[:4000]}"
    except Exception:
        pass
    return ""


# ------------------------------------------------------------------------------------------- LLM-written bugs

BUG_SYSTEM = """You create realistic bugs for a software-engineering benchmark, in the style of SWE-smith.
A bug must look like a plausible mistake a developer could make and a reviewer could miss: a wrong boundary or
comparison, a missed case, a wrong default, an inverted condition, a misused API, a wrong variable, an incorrect
calculation, a dropped update. It must compile, change observable behavior of the class's public API, and must not
add comments, TODOs, logging, or anything that points to the change. Do not touch tests. Each bug changes one
contiguous snippet inside ONE of the listed methods; `original` must be copied exactly from the file (whitespace
included) and must occur exactly once in it."""

BUG_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["bugs"],
    "properties": {"bugs": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["method", "description", "original", "replacement"],
        "properties": {"method": {"type": "string"}, "description": {"type": "string"},
                       "original": {"type": "string"}, "replacement": {"type": "string"}}}}}}


def llm_candidates(session: Session, target: str, original: str, methods: list[str], victim_class: str,
                   others: dict, seed: int, log, check) -> tuple[list[dict], dict | None]:
    """Up to LLM_ROUNDS rounds of N_LLM bugs; each round is told how the previous round's bugs fared. Returns the
    examined candidates and the first that passes the filters (check(cand) -> found or None)."""
    def covering(m: str, inside: bool) -> list[str]:
        return sorted(t.split("#", 1)[1] for t, ms in others.items()
                      if m in ms and (t.split("#", 1)[0] == victim_class) == inside)
    # A bug must be detected by a test in the flaky test's class (the named test at L2).
    both = [m for m in methods if covering(m, True)]
    if not both:
        log("  llm: no method covered by another test in the flaky test's class")
        return [], None
    hints = "\n".join(f"- {m}: exercised by {', '.join((covering(m, True) + covering(m, False))[:8])}"
                      for m in both)
    user = (f"Class `{target}`. Methods you may change, and test methods that exercise them:\n{hints}\n\n"
            f"Write {N_LLM} different bugs. Prefer the main code path of a method (what most callers rely on) "
            f"over rare corner cases, so that the change is noticeable.\n\n```java\n{original[:120_000]}\n```")
    examined, rng = [], random.Random(seed)
    for rnd in range(LLM_ROUNDS):
        try:
            bugs = session.ask_json(BUG_SYSTEM, user, BUG_SCHEMA)["bugs"]
        except Exception as e:
            log(f"  llm bug writer failed: {e}")
            return examined, None
        cands = []
        for i, b in enumerate(bugs):
            cid = f"llm-r{rnd}-{i}"
            if not b["original"] or b["original"] == b["replacement"] or original.count(b["original"]) != 1:
                log(f"  {cid}: snippet not found exactly once; skipped")
                continue
            cands.append({"id": cid, "kind": "llm", "method": b["method"], "description": b["description"],
                          "original_snippet": b["original"], "replacement": b["replacement"],
                          "text": original.replace(b["original"], b["replacement"], 1)})
        rng.shuffle(cands)
        feedback = []
        for cand in cands:
            found = check(cand)
            examined.append(cand | {"passed": bool(found)})
            if found:
                return examined, cand | {"found": found}
            feedback.append(f"- {cand['method']}: {cand['description'][:120]} -> {cand.get('why', 'rejected')}")
        user += (f"\n\nNone of these bugs was usable (each must compile and make at least two of the listed "
                 f"test methods fail, at least one of them in {victim_class.rsplit('.', 1)[-1]}):\n" + "\n".join(feedback) + "\nWrite different ones.")
    return examined, None


# ------------------------------------------------------------------------------------------- issue reports

ISSUE_SYSTEM = """You write the GitHub issue a user or developer would file for a bug, for a bug-fixing benchmark.
You see the bug (as a diff from correct to buggy code; the reporter never saw it) and how tests fail on it.
Write what the reporter observed: what they did with the library's API, what they expected, and what happened
instead, with a short code example if natural. Rules:
- Do not quote or paraphrase the diff, name the faulty line, file location, or suggest a fix.
- Do not paste test output, stack traces, or test names; do not mention tests at all.
- Do not mention flaky, intermittent, nondeterministic, random, timing, ordering, or concurrency issues.
- Only state concrete values (results, outputs) if they appear in the failure messages for that exact input;
  otherwise describe the wrong behavior in words. Never invent numbers.
- Plain, concise developer prose, 80-250 words, like a real issue. Title under 80 characters."""

ISSUE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["title", "body"],
                "properties": {"title": {"type": "string"}, "body": {"type": "string"}}}


def write_issue(session: Session, c: rf.Candidate, target: str, bug: dict, original: str,
                killer_messages: dict) -> dict:
    import difflib
    diff = "".join(difflib.unified_diff(original.splitlines(True), bug["text"].splitlines(True),
                                        "correct", "buggy", n=4))
    fails = "\n".join(f"- {k.split('#', 1)[1]}: {(m or '').strip().splitlines()[0][:300] if m else '(no message)'}"
                      for k, m in list(killer_messages.items())[:6])
    extra = ""
    if bug["kind"] == "revert":
        extra = (f"\n\nThe bug is real: it existed before commit {bug['commit'][:10]} fixed it.\n"
                 f"Commit message: {bug['subject']}\n{bug['message'][:1500]}")
        if bug.get("issue"):
            extra += f"\n\nOriginal issue (for context; reword, do not copy):\n{bug['issue'][:3000]}"
    user = (f"Project: {c.project} (module {c.module}). Class: `{target}`.\n\nBug:\n```diff\n{diff[:20_000]}\n```\n\n"
            f"How tests fail on the buggy code (for your understanding only):\n{fails}{extra}")
    for _ in range(3):
        issue = session.ask_json(ISSUE_SYSTEM, user, ISSUE_SCHEMA)
        problems = issue_problems(issue, c, bug, original)
        if not problems:
            return issue
        user += f"\n\nYour previous draft broke the rules ({'; '.join(problems)}). Write it again."
    issue["problems"] = problems
    return issue


def issue_problems(issue: dict, c: rf.Candidate, bug: dict, original: str) -> list[str]:
    text = issue["title"] + "\n" + issue["body"]
    hits = [p for p in FORBIDDEN if re.search(p, text, flags=re.I)]
    if re.search(r"\b(test|junit|assert)\w*", text, flags=re.I):
        hits.append("mentions tests")
    if c.flaky_test.split("#", 1)[1] in text:
        hits.append("names the flaky test")
    # Changed lines of the fault, on either side, must not be quoted.
    import difflib
    for line in difflib.unified_diff(original.splitlines(), bug["text"].splitlines(), n=0, lineterm=""):
        body = line[1:].strip()
        if line[:1] in "+-" and not line.startswith(("+++", "---")) and len(body) > 12 and body in text:
            hits.append("quotes a changed line")
            break
    return hits


# ------------------------------------------------------------------------------------------- driver

def seed_bug(c: rf.Candidate, session: Session, log) -> dict:
    ev = json.loads((EVAL_DIR / f"{c.result_container}.json").read_text())
    seed_info = ev["details"]["seeding"]
    target, source, methods = seed_info["target_class"], seed_info["source"], seed_info["methods"]
    deterministic = set(json.loads((EVAL_DIR / f"{c.result_container}.deterministic.json").read_text()))
    host = paths.SCRATCH / c.result_container
    cov_rows = list(__import__("csv").DictReader(open(host / "flaky.cov" / "coverage.csv")))
    cov = Coverage(cov_rows, None)
    by_test = cov.methods_by_test(target)
    others = {t: ms for t, ms in by_test.items() if t != c.flaky_test and t in deterministic}
    original = (host / "flaky" / source).read_text(encoding="utf-8", errors="surrogateescape")
    seed = bug_seed(c.flaky_test)
    result = {"result_container": c.result_container, "category": c.category, "target_class": target,
              "source": source, "methods": methods, "seed": seed, "examined": [], "ok": False}

    ws = rf.workspace(c)
    delay = "flaky_delay" if c.category == "TD" else None
    with Box(image_for(c.java), host, host / "m2") as box:
        repro = Repro(c, box, host, build_mode=ev["details"].get("build_mode"))
        if delay and patch_stays_in_module(ws.delay_patch, c.module):
            repro.share_install(delay, "flaky")
        b = repro.build("flaky")
        if b.rc != 0:
            raise RuntimeError("flaky tree does not build: " + b.output[-300:])
        ctx = BugContext.create(repro, source, others, methods, delay, require_outside=False)
        funnel: dict = {}
        try:
            def check(cand: dict):
                kind = cand["kind"]
                funnel[f"{kind}_examined"] = funnel.get(f"{kind}_examined", 0) + 1
                msgs: list[str] = []
                found = ctx.check(cand["text"], cand["id"], funnel, lambda m: (msgs.append(m), log(m)))
                cand["why"] = "" if found else (msgs[-1].split(": ", 1)[-1] if msgs else "rejected")
                result["examined"].append({k: v for k, v in cand.items() if k not in ("text", "fix_diff")}
                                          | {"passed": bool(found)})
                return found

            chosen, found = None, None
            reverts = mined_candidates(c, source, original, seed, log)
            funnel["revert_candidates"] = len(reverts)
            for cand in reverts:
                if (found := check(cand)):
                    chosen = cand
                    break
            if not chosen:
                _, hit = llm_candidates(session, target, original, methods, c.test_class, others, seed, log, check)
                if hit:
                    found = hit.pop("found")
                    chosen = hit
            if not chosen and seed_info.get("mutant"):
                # Last resort: the PIT mutant selection validated for this test, still with an issue report.
                m = seed_info["mutant"]
                mfile = host / "mutants" / f"{m['id']}.java"
                if mfile.exists():
                    cand = {"id": m["id"], "kind": "mutant", "operator": m["operator"], "method": m["method"],
                            "line": m["line"], "text": mfile.read_text(encoding="utf-8", errors="surrogateescape")}
                    if (found := check(cand)):
                        chosen = cand
            if not chosen:
                result["reason"] = "no reverted fix, LLM-written bug or mutant survives the filters"
                return result | {"funnel": funnel}
            killers, messages, standalone = found
            if chosen["kind"] == "revert":
                chosen["issue"] = linked_issue(chosen)
            issue = write_issue(session, c, target, chosen, original, messages)
            (BUGS / f"{c.result_container}.java").write_text(chosen["text"], encoding="utf-8",
                                                             errors="surrogateescape")
            result.update(ok=True, bug={k: v for k, v in chosen.items() if k != "text"}, killers=killers,
                          killer_messages=messages, standalone_killers=standalone, issue=issue)
            log(f"  chose {chosen['id']} ({chosen['kind']}): killed by {len(killers)}; issue: {issue['title']}")
            return result | {"funnel": funnel}
        finally:
            ctx.restore()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--usd-cap", type=float, default=3.0)
    ap.add_argument("--redo", action="store_true", help="redo tests that already have a bug")
    args = ap.parse_args()
    BUGS.mkdir(parents=True, exist_ok=True)
    tests = [c for c in accepted_candidates() if not args.only or c.result_container in args.only]
    if not args.redo:
        tests = [c for c in tests if not (BUGS / f"{c.result_container}.json").exists()]

    with Session("bugs", usd_cap=args.usd_cap) as session:
        def one(c: rf.Candidate) -> None:
            def log(m: str) -> None:
                print(f"[{c.category}] {c.result_container}{m if m.startswith(' ') else ' ' + m}", flush=True)
            start = time.time()
            try:
                res = seed_bug(c, session, log)
            except Exception as e:
                res = {"result_container": c.result_container, "category": c.category, "ok": False,
                       "reason": f"error: {type(e).__name__}: {e}", "traceback": traceback.format_exc()[-3000:]}
            res["minutes"] = round((time.time() - start) / 60, 1)
            (BUGS / f"{c.result_container}.json").write_text(json.dumps(res, indent=1))
            log(f"DONE ok={res['ok']} {res.get('reason', '')} ({res['minutes']} min)")

        with ThreadPoolExecutor(args.workers) as pool:
            list(pool.map(one, tests))


if __name__ == "__main__":
    main()
