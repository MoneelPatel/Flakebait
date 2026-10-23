"""Repair-task instances: one per (selected flaky test, exposure level, arm).

data/instances/<id>/
  repo/          the agent's repository: a fresh git repo with one commit (flaky version + seeded fault,
                 plus Fixed.patch in the control arm). Nothing else from ReproFlake or Flakebait is in it.
  pristine/      the same tree, kept for success checks (the agent can rewrite repo/ and its history)
  meta.json      hidden metadata: flaky test, category, configurations, fault, named and held-out tests
  prompt.md      the task prompt (never mentions flakiness; checked by forbidden_terms())
  delay.patch    TD only: the delay that makes the failure deterministic, relative to this repo

Usage: uv run python -m flakebait.instances --pilot      (build the 10 pilot repair instances, L1+L2, both arms)
"""
import argparse
import csv
import hashlib
import json
import random
import re
import shutil
import subprocess
from pathlib import Path

import yaml

from . import paths, reproflake as rf
from .selection import EVAL_DIR

LEVELS = ("L1", "L2")
ARMS = ("flaky", "control")
GIT_ENV = {"GIT_AUTHOR_NAME": "Developer", "GIT_AUTHOR_EMAIL": "dev@example.com",
           "GIT_COMMITTER_NAME": "Developer", "GIT_COMMITTER_EMAIL": "dev@example.com",
           "GIT_AUTHOR_DATE": "2024-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2024-01-01T00:00:00Z"}
FORBIDDEN = [r"flak", r"nondetermin", r"non-determin", r"intermittent", r"sporadic", r"random(ly)? fail",
             r"order[- ]dependen", r"timing", r"race condition"]
PILOT_QUOTA = {"ID": 3, "OD": 3, "NIO": 2, "TD": 2}

PROMPT = """\
## `{named_simple}` fails in `{module_name}`

The test `{named_method}` in `{named_class}` is failing:

```
{failure}
```

You can reproduce it with:

```
mvn test {pl}-Dtest={named_simple}
```

Please find the cause of this failure in the code and fix it.
"""


def instance_id(c: rf.Candidate, level: str, arm: str) -> str:
    return f"repair-{c.category.lower()}-{c.result_container}-{level}-{arm}"


def pilot_tests(accepted: list[rf.Candidate]) -> list[rf.Candidate]:
    """The 10 pilot tests: per category, the first accepted tests in (shuffled) selection order, 3/3/2/2.

    Selection order is already random, and this rule does not depend on tests accepted later, so the pilot
    can start before selection finishes.
    """
    out = []
    for cat, quota in PILOT_QUOTA.items():
        pool = sorted((c for c in accepted if c.category == cat), key=lambda c: c.position)
        out += pool[:quota]
    return out


def accepted_candidates() -> list[rf.Candidate]:
    by_rc = {c.result_container: c for c in rf.load_candidates()}
    rows = csv.DictReader(open(paths.REPORTS / "selected_tests.csv"))
    return [by_rc[r["result_container"]] for r in rows]


def named_candidates(c: rf.Candidate, killers: list[str], level: str,
                     standalone: list[str] | None = None) -> list[str]:
    """Detecting tests eligible to be named, in seeded order: from the flaky test's own class at L2, from another
    class at L1. The first is named; validation moves down the list if it does not fail when its class runs
    alone, as the prompt tells the agent to run it (deviations.md #23)."""
    pool = sorted(k for k in killers if (k.split("#", 1)[0] == c.test_class) == (level == "L2"))
    if standalone:
        pool = [k for k in pool if k in standalone] or pool
    seed = yaml.safe_load(open(paths.CONFIG / "seeds.yaml"))["mutant_choice"]
    rng = random.Random(f"{seed}:{c.flaky_test}:{level}:named")
    first = rng.choice(pool)     # the original single draw, kept so earlier instances are unchanged
    rest = [k for k in pool if k != first]
    rng.shuffle(rest)
    return [first] + rest


def choose_named(c: rf.Candidate, killers: list[str], level: str,
                 standalone: list[str] | None = None) -> tuple[str, list[str]]:
    named = named_candidates(c, killers, level, standalone)[0]
    return named, sorted(k for k in killers if k != named)


def set_named(instance: Path, c: rf.Candidate, named: str, message: str) -> None:
    """Re-point an instance at another named test (prompt and metadata)."""
    meta = json.loads((instance / "meta.json").read_text())
    prompt = render_prompt(c, named, message)
    meta["named_test"] = named
    meta["held_out"] = sorted(k for k in meta["killers"] if k != named)
    meta["prompt_forbidden_hits"] = forbidden_terms(prompt, meta)
    (instance / "prompt.md").write_text(prompt)
    (instance / "meta.json").write_text(json.dumps(meta, indent=1))


def render_prompt(c: rf.Candidate, named: str, message: str) -> str:
    cls, method = named.split("#", 1)
    failure = message.strip() or "(no message)"
    lines = failure.splitlines()
    if len(lines) > 25:
        failure = "\n".join(lines[:25] + ["..."])
    module_name = c.module if c.module not in (".", "") else c.project
    pl = "" if c.module in (".", "") else f"-pl {c.module} "
    return PROMPT.format(named_simple=cls.rsplit(".", 1)[-1], named_class=cls, named_method=method,
                         module_name=module_name, failure=failure, pl=pl)


def forbidden_terms(prompt: str, meta: dict) -> list[str]:
    hits = [p for p in FORBIDDEN if re.search(p, prompt, flags=re.I)]
    victim_method = meta["victim"].split("#", 1)[1]
    victim_simple = meta["victim"].split("#", 1)[0].rsplit(".", 1)[-1] + "." + victim_method
    if victim_method in prompt.replace(meta["named_test"].split("#", 1)[1], ""):
        hits.append(f"flaky test method name '{victim_method}'")
    if victim_simple in prompt:
        hits.append(f"flaky test '{victim_simple}'")
    mutated = meta["mutant"].get("mutated_line_text", "").strip()
    if mutated and len(mutated) > 8 and mutated in prompt:
        hits.append("mutated line")
    return hits


def _git_init(repo: Path) -> None:
    env = {**GIT_ENV, "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(repo)}
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A", "-f", "."],
                ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "Initial commit"]):
        subprocess.run(cmd, cwd=repo, check=True, env=env, capture_output=True)


def _diff(build_dir: Path) -> str:
    """Unified diff from build_dir/a to build_dir/b (apply with patch -p1 inside a)."""
    r = subprocess.run(["diff", "-ruN", "--exclude=target", "--exclude=.git", "a", "b"],
                       cwd=build_dir, capture_output=True, text=True, errors="surrogateescape")
    return r.stdout


def build(c: rf.Candidate, level: str, arm: str) -> Path:
    ev = json.loads((EVAL_DIR / f"{c.result_container}.json").read_text())
    seed = ev["details"]["seeding"]
    ws = rf.workspace(c)
    scratch = paths.SCRATCH / c.result_container
    mutant_file = scratch / "mutants" / f"{seed['mutant']['id']}.java"
    iid = instance_id(c, level, arm)
    out = paths.INSTANCES / iid
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)

    # Trees are built side by side under out/build so diffs can be taken with relative paths.
    b = out / "build"
    rf.copy_tree(ws.flaky, b / "a")
    if arm == "control":
        if not rf.apply_patch(b / "a", ws.fixed_patch):
            raise RuntimeError("Fixed.patch does not apply")
    original_src = (b / "a" / seed["source"]).read_text(encoding="utf-8", errors="surrogateescape")
    mutant_text = mutant_file.read_text(encoding="utf-8", errors="surrogateescape")
    # Apply the mutant as a diff, so it composes with a Fixed.patch that touches the same file.
    flaky_src = (ws.flaky / seed["source"]).read_text(encoding="utf-8", errors="surrogateescape")
    if arm == "flaky":
        (b / "a" / seed["source"]).write_text(mutant_text, encoding="utf-8", errors="surrogateescape")
    else:
        if not _apply_text(flaky_src, mutant_text, b / "a" / seed["source"]):
            raise RuntimeError("mutant does not apply on top of Fixed.patch")
    line_no = int(seed["mutant"]["line"])
    mutated_line = (b / "a" / seed["source"]).read_text(errors="replace").splitlines()[line_no - 1]

    delay_rel = None
    if c.category == "TD":
        patch = ws.delay_patch if arm == "flaky" else ws.root / "FixedCodeChange.patch"
        rf.copy_tree(ws.flaky, b / "b")
        if not rf.apply_patch(b / "b", patch):
            raise RuntimeError(f"{patch.name} does not apply")
        if not _apply_text(flaky_src, mutant_text, b / "b" / seed["source"]):
            raise RuntimeError("mutant does not apply on top of the delay")
        (out / "delay.patch").write_text(_diff(b))
        delay_rel = "delay.patch"

    # The reference solution: this arm's code without the seeded fault (hidden from the agent).
    (out / "reference_source.txt").write_text(original_src, encoding="utf-8", errors="surrogateescape")
    shutil.copytree(b / "a", out / "pristine", symlinks=True)
    shutil.move(str(b / "a"), str(out / "repo"))
    shutil.rmtree(b, ignore_errors=True)
    _git_init(out / "repo")

    named, held_out = choose_named(c, seed["killers"], level, seed.get("standalone_killers"))
    prompt = render_prompt(c, named, seed["killer_messages"].get(named, ""))
    meta = {
        "instance": iid, "task": "repair", "level": level, "arm": arm,
        "result_container": c.result_container, "category": c.category, "project": c.project,
        "module": c.module, "java": c.java, "victim": c.flaky_test, "polluter": c.polluter,
        "nondex_seed": c.nondex_seed, "zip": c.zip,
        "target_class": seed["target_class"], "source": seed["source"],
        "mutant": {**seed["mutant"], "mutated_line_text": mutated_line, "original_source_sha":
                   hashlib.sha256(original_src.encode(errors="surrogateescape")).hexdigest()[:16]},
        "killers": seed["killers"], "standalone_killers": seed.get("standalone_killers", []),
        "named_test": named, "held_out": held_out,
        "deterministic_tests_file": f"{c.result_container}.deterministic.json",
        "delay_patch": delay_rel, "build_mode": ev["details"].get("build_mode") or "default",
    }
    hits = forbidden_terms(prompt, meta)
    meta["prompt_forbidden_hits"] = hits
    (out / "prompt.md").write_text(prompt)
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    return out


def _apply_text(original: str, mutated: str, target: Path) -> bool:
    import difflib
    diff = "".join(difflib.unified_diff(original.splitlines(True), mutated.splitlines(True), "a/f", "b/f"))
    pf = target.parent / (target.name + ".fb.patch")
    pf.write_text(diff, encoding="utf-8", errors="surrogateescape")
    r = subprocess.run(["patch", "-s", "-f", str(target), "-i", str(pf)], capture_output=True)
    pf.unlink(missing_ok=True)
    for junk in (target.parent / (target.name + ".rej"), target.parent / (target.name + ".orig")):
        junk.unlink(missing_ok=True)
    return r.returncode == 0


def write_prompt_reports(built: list[str]) -> None:
    """example_prompt.md (one L1 and one L2 prompt) and prompts_for_review.md (every prompt, for hand review)."""
    flaky = [b for b in built if b.endswith("-flaky")]
    review = ["# Prompts for hand review", "",
              "Check that no prompt names the mutated line or hints at flakiness. Automatic forbidden-term hits "
              "are listed under each prompt.", ""]
    for iid in flaky:
        meta = json.loads((paths.INSTANCES / iid / "meta.json").read_text())
        review += [f"## {iid}", "", f"Mutated line ({meta['source']}:{meta['mutant']['line']}): "
                   f"`{meta['mutant']['mutated_line_text'].strip()}`", "",
                   "Forbidden-term hits: " + (", ".join(meta["prompt_forbidden_hits"]) or "none"), "",
                   (paths.INSTANCES / iid / "prompt.md").read_text(), ""]
    (paths.REPORTS / "prompts_for_review.md").write_text("\n".join(review))
    example = ["## Example prompts", ""]
    for level in LEVELS:
        pick = next((b for b in flaky if b.endswith(f"-{level}-flaky")), None)
        if pick:
            example += [f"**{level}** (`{pick}`):", "", "````markdown",
                        (paths.INSTANCES / pick / "prompt.md").read_text().strip(), "````", ""]
    (paths.REPORTS / "example_prompt.md").write_text("\n".join(example))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--only", help="result_container of one selected test")
    args = ap.parse_args()
    accepted = accepted_candidates()
    tests = pilot_tests(accepted) if args.pilot else accepted
    if args.only:
        tests = [c for c in accepted if c.result_container == args.only]
    rows = []
    for c in tests:
        for level in LEVELS:
            for arm in ARMS:
                try:
                    out = build(c, level, arm)
                    meta = json.loads((out / "meta.json").read_text())
                    rows.append({"instance": meta["instance"], "test": c.flaky_test, "category": c.category,
                                 "level": level, "arm": arm, "target_class": meta["target_class"],
                                 "mutant_operator": meta["mutant"]["operator"],
                                 "mutant_location": f"{meta['source']}:{meta['mutant']['line']}",
                                 "named_test": meta["named_test"], "held_out_tests": " ".join(meta["held_out"]),
                                 "prompt_forbidden_hits": "; ".join(meta["prompt_forbidden_hits"]),
                                 "status": "built"})
                    print("built", meta["instance"], flush=True)
                except Exception as e:
                    rows.append({"instance": instance_id(c, level, arm), "test": c.flaky_test,
                                 "category": c.category, "level": level, "arm": arm,
                                 "status": f"error: {e}"})
                    print("FAILED", instance_id(c, level, arm), e, flush=True)
    write_prompt_reports([r["instance"] for r in rows if r.get("status") == "built"])
    path = paths.REPORTS / "instances_manifest.csv"
    fields = ["instance", "test", "category", "level", "arm", "target_class", "mutant_operator",
              "mutant_location", "named_test", "held_out_tests", "prompt_forbidden_hits", "status"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
