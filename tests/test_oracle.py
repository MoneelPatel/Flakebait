"""Draw rules of the oracle (no containers needed): first-edit rule, seed reproducibility, p=0 and p=1."""
import json
import subprocess
from pathlib import Path

import pytest

from flakebait.oracle import Oracle
from flakebait.repro import FAILING, PASSING


def make(tmp_path: Path, p: float, seed: int = 7, mode: str = "agent", tag: str = "") -> tuple[Oracle, Path]:
    work = tmp_path / f"work-{p}-{seed}-{mode}{tag}"
    (work / "src").mkdir(parents=True)
    (work / "src" / "A.java").write_text("class A {}\n")
    (work / ".gitignore").write_text("target/\n")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=work, check=True)
    state = tmp_path / f"state-{p}-{seed}-{mode}{tag}"
    state.mkdir()
    (state / "config.json").write_text(json.dumps({
        "instance": "t", "category": "ID", "module": ".", "victim": "a.BTest#m", "seed": seed, "p": p,
        "mode": mode, "work": str(work)}))
    return Oracle(state), work


def edit(work: Path, n: int) -> None:
    (work / "src" / "A.java").write_text(f"class A {{ int x = {n}; }}\n")


def configs(o: Oracle, work: Path, invocations: int) -> list[str]:
    out = []
    for i in range(invocations):
        edit(work, i)
        out.append(o.decide(f"inv{i}", o.tree_hash())["config"])
    return out


def test_pre_edit_always_passes(tmp_path):
    o, work = make(tmp_path, p=1.0)
    for i in range(5):
        d = o.decide(f"inv{i}", o.tree_hash())
        assert d["config"] == PASSING and d["rule"] == "pre_edit"


def test_build_outputs_are_not_edits(tmp_path):
    o, work = make(tmp_path, p=1.0)
    (work / "target").mkdir()
    (work / "target" / "A.class").write_text("x")
    assert o.decide("inv", o.tree_hash())["rule"] == "pre_edit"


def test_first_post_edit_always_fails(tmp_path):
    o, work = make(tmp_path, p=0.0)
    edit(work, 1)
    d = o.decide("first", o.tree_hash())
    assert d["config"] == FAILING and d["rule"] == "first_post_edit"


def test_one_draw_per_invocation(tmp_path):
    o, work = make(tmp_path, p=0.5)
    edit(work, 1)
    first = o.decide("same", o.tree_hash())
    edit(work, 2)
    assert o.decide("same", o.tree_hash()) is first


def test_p_zero_and_one(tmp_path):
    o0, w0 = make(tmp_path, p=0.0)
    assert configs(o0, w0, 20) == [FAILING] + [PASSING] * 19
    o1, w1 = make(tmp_path, p=1.0)
    assert configs(o1, w1, 20) == [FAILING] * 20


def test_same_seed_same_draws(tmp_path):
    a, wa = make(tmp_path, p=0.5, seed=11)
    b, wb = make(tmp_path, p=0.5, seed=11, tag="b")
    c, wc = make(tmp_path, p=0.5, seed=12)
    seq_a = configs(a, wa, 40)
    assert seq_a == configs(b, wb, 40)
    assert seq_a != configs(c, wc, 40)  # equal by chance with probability 2^-39


def test_rate_close_to_p(tmp_path):
    o, work = make(tmp_path, p=0.5, seed=3)
    seq = configs(o, work, 401)[1:]
    assert 0.4 < seq.count(FAILING) / len(seq) < 0.6


@pytest.mark.parametrize("mode,expected", [("force_failing", FAILING), ("force_passing", PASSING)])
def test_forced_modes(tmp_path, mode, expected):
    o, work = make(tmp_path, p=0.5, mode=mode)
    assert configs(o, work, 5) == [expected] * 5
