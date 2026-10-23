"""Regenerates reports/milestone1/README.md, the derived CSVs, figures and LaTeX tables from the logs.

Inputs (produced by the pipeline):
  reports/milestone1/category_counts.csv, candidate_order.csv, selection_log.csv, selected_tests.csv
  data/evaluations/*.json              per-candidate check details (config validation, seeding funnel)
  reports/milestone1/instances_manifest.csv, instance_validation.csv, isolation_checks.md, shim_e2e.csv
  reports/milestone1/pilot_runs.csv, pilot_exposure.csv, pilot_cost.csv, pilot_decision.md
  reports/milestone1/deviations.md

Usage: uv run python analysis/build_milestone1_report.py
"""
import csv
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import matplotlib
import pandas as pd
import yaml

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from flakebait.selection import CATEGORY_ORDER, CHECKS  # noqa: E402

R = ROOT / "reports" / "milestone1"
TEX = R / "tex"
EVALS = ROOT / "data" / "evaluations"
CATS = ["ID", "OD", "NIO", "TD"]
CHECK_LABELS = {
    "cap_module": "Diversity cap (module)", "cap_project": "Diversity cap (project)",
    "addressable": "Addressable test method", "a_offline_compile": "(a) Offline compile",
    "f_suite_under_10min": "(f) Suite < 10 min", "e_other_deterministic": "(e) Other test in class",
    "b_failing_20": "(b) Failing config 20/20", "b_passing_20": "(b) Passing config 20/20",
    "c_fixed_20": "(c) Fix passes 20/20", "d_seedable": "(d) Fault seedable", "error": "Infrastructure error",
}


def read_csv(name: str) -> pd.DataFrame | None:
    p = R / name
    if not p.exists() or p.stat().st_size == 0:
        return None
    try:
        return pd.read_csv(p, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError:
        return None


def md_table(df: pd.DataFrame, max_rows: int = 200) -> str:
    df = df.head(max_rows)
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, row in df.iterrows():
        out.append("| " + " | ".join(str(row[c]).replace("|", "\\|").replace("\n", " ") for c in cols) + " |")
    return "\n".join(out)


def tex_table(df: pd.DataFrame, name: str, caption: str) -> None:
    TEX.mkdir(parents=True, exist_ok=True)
    def esc(s):
        s = str(s)
        for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
                     ("_", r"\_"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\^{}")):
            s = s.replace(a, b)
        return s
    cols = list(df.columns)
    lines = [r"\begin{table}[t]", r"\centering\small", rf"\caption{{{esc(caption)}}}", rf"\label{{tab:{name}}}",
             r"\begin{tabular}{" + "l" * len(cols) + "}", r"\toprule",
             " & ".join(rf"\textbf{{{esc(c)}}}" for c in cols) + r" \\", r"\midrule"]
    for _, row in df.iterrows():
        lines.append(" & ".join(esc(row[c]) for c in cols) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (TEX / f"{name}.tex").write_text("\n".join(lines) + "\n")


# --------------------------------------------------------------------------------------------- derived

def selection_funnel(log: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cat in CATS:
        sel = log[log["category"] == cat]
        row = {"category": cat, "examined": len(sel)}
        remaining = len(sel)
        for check in CHECKS + ["error"]:
            rejected = int((sel["rejection_reason"] == check).sum())
            if check == "error" and not rejected:
                continue
            remaining -= rejected
            row[CHECK_LABELS[check]] = remaining
        row["accepted"] = int((sel["rejection_reason"] == "").sum())
        rows.append(row)
    return pd.DataFrame(rows)


def funnel_figure(funnel: pd.DataFrame) -> None:
    stages = [c for c in funnel.columns if c not in ("category",)]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    colors = {"ID": "#4C72B0", "OD": "#DD8452", "NIO": "#55A868", "TD": "#C44E52"}
    for _, row in funnel.iterrows():
        ax.plot(range(len(stages)), [int(row[s]) for s in stages], marker="o", label=row["category"],
                color=colors[row["category"]])
    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels([s.replace(" config", "").replace("Diversity cap", "Cap") for s in stages],
                       rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("Candidates remaining")
    ax.set_title("Flaky-test selection funnel (candidates examined in shuffled order)")
    ax.axhline(10, color="grey", lw=0.8, ls="--")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(R / "selection_funnel.png", dpi=200)
    plt.close(fig)


def evaluations() -> dict[str, dict]:
    out = {}
    for p in EVALS.glob("*.json"):
        if p.name.endswith(".deterministic.json"):
            continue
        ev = json.loads(p.read_text())
        out[ev["candidate"]] = ev
    return out


def config_validation(selected: pd.DataFrame, evs: dict) -> pd.DataFrame:
    rows = []
    for _, s in selected.iterrows():
        d = evs.get(s["result_container"], {}).get("details", {})
        rows.append({"category": s["category"], "test": s["test"].rsplit(".", 1)[-1],
                     "failing config: failed": f"{d.get('b_failing_failed', '')}/20",
                     "passing config: passed": f"{d.get('b_passing_passed', '')}/20",
                     "Fixed.patch under failing: passed": f"{d.get('c_fixed_passed', '')}/20"})
    return pd.DataFrame(rows)


def mutant_funnel(log: pd.DataFrame, evs: dict) -> pd.DataFrame:
    rows = []
    for _, r in log.iterrows():
        ev = evs.get(r["result_container"])
        seed = (ev or {}).get("details", {}).get("seeding")
        if not seed:
            continue
        f = seed["funnel"]
        rows.append({"category": r["category"], "test": r["test"].rsplit(".", 1)[-1],
                     "target class": (seed.get("target_class") or "").rsplit(".", 1)[-1],
                     "candidate methods": f["candidate_methods"], "mutants generated": f["generated"],
                     "examined": f["examined"], "compiled": f["compiled"], "killed by >=2": f["killed_2plus"],
                     "killers in L1+L2 classes": f["killed_l1_l2"], "flaky test unchanged": f["flaky_unchanged"],
                     "20/20 recheck": f["recheck_20"],
                     "chosen": (f"{seed['mutant']['operator']} L{seed['mutant']['line']}" if seed.get("mutant") else
                                "none: " + seed.get("reason", ""))})
    return pd.DataFrame(rows)


def shim_unit_tests() -> pd.DataFrame:
    xml = R / ".pytest_shim.xml"
    subprocess.run([sys.executable, "-m", "pytest", "-q", "tests", f"--junitxml={xml}"], cwd=ROOT,
                   capture_output=True)
    rows = []
    if xml.exists():
        for tc in ET.parse(xml).getroot().iter("testcase"):
            failed = tc.find("failure") is not None or tc.find("error") is not None
            rows.append({"test": f"{tc.get('classname').rsplit('.', 1)[-1]}::{tc.get('name')}",
                         "result": "FAIL" if failed else "pass"})
        xml.unlink()
    return pd.DataFrame(rows)


def exposure_figure(exp: pd.DataFrame) -> None:
    sub = exp[exp["category"] != "ALL"]
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    width = 0.38
    for i, level in enumerate(("L1", "L2")):
        part = sub[sub["level"] == level].set_index("category").reindex(CATS)
        vals = [float(v) if v not in ("", None) and v == v else 0 for v in part["rate"]]
        ax.bar([x + (i - 0.5) * width for x in range(len(CATS))], vals, width, label=level,
               color="#9DB4D3" if level == "L1" else "#2F5D8C")
    ax.axhline(0.7, color="grey", lw=0.8, ls="--")
    ax.set_xticks(range(len(CATS)))
    ax.set_xticklabels(CATS)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Observed exposure (first phase)")
    ax.set_title("Pilot: observed exposure by level and category (flaky arm)")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(R / "pilot_exposure.png", dpi=200)
    plt.close(fig)


# --------------------------------------------------------------------------------------------- report

def main() -> None:
    seeds = yaml.safe_load(open(ROOT / "config" / "seeds.yaml"))
    counts = read_csv("category_counts.csv")
    log = read_csv("selection_log.csv")
    selected = read_csv("selected_tests.csv")
    evs = evaluations()
    manifest = read_csv("instances_manifest.csv")
    validation = read_csv("instance_validation.csv")
    shim_e2e = read_csv("shim_e2e.csv")
    pilot = read_csv("pilot_runs.csv")
    exposure = read_csv("pilot_exposure.csv")
    cost = read_csv("pilot_cost.csv")

    status = {}
    md = ["# Milestone 1: Infrastructure and Pilot", "",
          "_Generated by `analysis/build_milestone1_report.py` from the logs in this directory. Do not edit by hand._",
          ""]

    # Selection
    sel_md = ["## 2. Selection", ""]
    if counts is not None:
        sel_md += ["Candidate pools in the ReproFlake index:", "", md_table(counts), ""]
        tex_table(counts, "category_counts", "ReproFlake candidate pools by category")
    sel_md += ["Seeds (`config/seeds.yaml`): " + ", ".join(f"`{k}={v}`" for k, v in seeds.items()) + ".", "",
               "Categories are processed scarcest first (" + ", ".join(CATEGORY_ORDER) + ") because the diversity "
               "caps are global. Within a category, candidates are examined strictly in shuffled order.", ""]
    n_acc = {c: 0 for c in CATS}
    if log is not None and len(log):
        funnel = selection_funnel(log)
        funnel.to_csv(R / "selection_funnel.csv", index=False)
        funnel_figure(funnel)
        tex_table(funnel, "selection_funnel", "Selection funnel per category")
        n_acc = {c: int((log[(log["category"] == c)]["rejection_reason"] == "").sum()) for c in CATS}
        sel_md += ["![Selection funnel](selection_funnel.png)", "", md_table(funnel), ""]
        reasons = log[log["rejection_reason"] != ""].groupby(["category", "rejection_reason"]).size()
        sel_md += ["Rejections by first failing check:", "",
                   md_table(reasons.reset_index().rename(columns={0: "count"})), ""]
        short = [c for c in CATS if n_acc[c] < 10]
        if short:
            pools = dict(zip(counts["category"], counts["index_count"])) if counts is not None else {}
            notes = []
            for c in short:
                exhausted = c in pools and int((log["category"] == c).sum()) >= int(pools[c])
                notes.append(f"{c} {n_acc[c]}/10" + (" (pool exhausted: shortfall)" if exhausted
                                                     else " (selection still in progress)"))
            sel_md += ["**Below 10:** " + ", ".join(notes), ""]
    else:
        sel_md += ["_No candidates examined yet._", ""]
    total_acc = sum(n_acc.values())
    status["Selection procedure run for all four categories, with the selection log"] = (
        "done" if log is not None and all((log["category"] == c).any() for c in CATS) and total_acc >= 36
        else "partial" if log is not None and len(log) else "not done")

    # Selected tests + configuration validation
    st_md = ["## 3. Selected tests", ""]
    cv_md = ["## 4. Configuration validation", ""]
    if selected is not None and len(selected):
        cols = ["category", "project", "module", "test", "java", "target_class", "mutant"]
        st_md += [md_table(selected[cols]), ""]
        tex_table(selected[["category", "project", "test"]].assign(test=lambda d: d["test"].str.rsplit(".", n=1).str[-1]),
                  "selected_tests", "Selected flaky tests")
        cv = config_validation(selected, evs)
        cv.to_csv(R / "config_validation.csv", index=False)
        tex_table(cv, "config_validation", "Determinism of the failing and passing configurations (20 runs each)")
        bad = cv[(cv["failing config: failed"] != "20/20") | (cv["passing config: passed"] != "20/20") |
                 (cv["Fixed.patch under failing: passed"] != "20/20")]
        cv_md += ["Every selected test was run 20 times under each configuration in our containers "
                  "(checks (b) and (c)); the seeded-fault version was rechecked 20/20 (seeding).", "",
                  md_table(cv), "", f"Failures: {len(bad)}." if len(bad) else "No failures.", ""]
    else:
        st_md += ["_No tests accepted yet._", ""]
        cv_md += ["_No tests accepted yet._", ""]
    status["40 tests selected; passing and failing configurations validated (20/20)"] = (
        "done" if total_acc >= 36 else "partial" if total_acc else "not done")

    # Shim
    sh_md = ["## 5. Shim design and tests", "",
             "How a flaky failure reaches the agent: `fb-ext` (a Maven core extension in the agent's `lib/ext`) "
             "attaches itself as a Java agent to every Surefire fork. The agent replaces the flaky test's body "
             "with a call to the oracle sidecar, which draws the configuration (once per Maven invocation), "
             "reproduces it on a private copy of the agent's current tree, and relays the outcome: a pass, or the "
             "exact Surefire-reported failure (exception type, message, frames, causes).", "",
             "| Category | Failing configuration (reproduced by the oracle) |", "|---|---|",
             "| ID | NonDex 2.1.1 with ReproFlake's stored seed, victim only |",
             "| OD | ReproFlake's custom Surefire (`runOrder=testorder`): polluter, then victim, same JVM |",
             "| NIO | Victim run twice in one JVM (fb-ext repeat mode); second run reported |",
             "| TD | ReproFlake's delay patch applied to the oracle's copy only; frame line numbers mapped back |",
             "", "Draw rules: no edit yet → passing; first invocation after the first edit → failing; afterwards "
             "failing with probability p = 0.5 from a per-run seeded RNG. Every draw is logged.", ""]
    unit = shim_unit_tests()
    if len(unit):
        sh_md += ["Unit tests (draw rules, trace parsing):", "", md_table(unit), ""]
    if shim_e2e is not None and len(shim_e2e):
        sh_md += ["End-to-end through the real path, per category:", "",
                  md_table(shim_e2e[["category", "arm", "step", "expected", "observed", "ok"]]), ""]
        tex_table(shim_e2e[["category", "arm", "step", "expected", "observed", "ok"]], "shim_e2e",
                  "End-to-end shim checks")
    unit_ok = len(unit) and (unit["result"] == "pass").all()
    e2e_cats = set(shim_e2e["category"]) if shim_e2e is not None else set()
    e2e_ok = shim_e2e is not None and (shim_e2e["ok"] == "True").all()
    status["Test shim with controlled failure rate, all four categories"] = (
        "done" if unit_ok and e2e_ok and e2e_cats >= set(CATS) else "partial" if unit_ok else "not done")
    (R / "shim_tests.md").write_text("\n".join(sh_md[2:]) + "\n")

    # Seeding
    sd_md = ["## 6. Fault seeding", ""]
    if log is not None:
        mf = mutant_funnel(log, evs)
        if len(mf):
            mf.to_csv(R / "mutant_funnel.csv", index=False)
            tex_table(mf.drop(columns=["chosen"]), "mutant_funnel", "Fault seeding funnel per flaky test")
            chosen = [c.split()[0] for c in mf["chosen"] if not c.startswith("none")]
            sd_md += ["Mutants are examined in seeded random order until the first one passes every filter, so "
                      "'examined' counts stop at the chosen mutant.", "", md_table(mf), "",
                      "Operators of chosen mutants: " + ", ".join(f"{k} {v}" for k, v in Counter(chosen).most_common())
                      + ".", ""]
    # Instances
    in_md = ["## 7. Pilot instances", ""]
    if manifest is not None and len(manifest):
        in_md += [md_table(manifest[["instance", "category", "level", "arm", "mutant_operator", "named_test",
                                     "status"]]), ""]
        ex = R / "example_prompt.md"
        if ex.exists():
            in_md += [ex.read_text(), ""]
    if validation is not None and len(validation):
        in_md += ["Validation:", "", md_table(validation), ""]
        tex_table(validation[["instance", "reference_success", "instance_fails_check", "flaky_test_ok", "valid"]],
                  "instance_validation", "Validation of pilot instances")
    n_valid = int((validation["valid"] == "True").sum()) if validation is not None else 0
    status["Fault-seeding pipeline and 10 repair instances with control twins at L1 and L2"] = (
        "done" if n_valid >= 40 else "partial" if (manifest is not None and len(manifest)) or total_acc else "not done")

    # Harness
    hz_md = ["## 8. Harness and isolation", ""]
    iso = R / "isolation_checks.md"
    if iso.exists():
        hz_md += [iso.read_text().split("\n", 1)[1], ""]
    status["Harness: headless agent in an offline container, full trajectory and final diff"] = (
        "done" if iso.exists() and "| FAIL |" not in iso.read_text() and pilot is not None else
        "partial" if iso.exists() else "not done")

    # Pilot
    pl_md = ["## 9. Pilot results", ""]
    if pilot is not None and len(pilot):
        if exposure is not None:
            exposure_figure(exposure)
            pl_md += ["![Observed exposure](pilot_exposure.png)", "", md_table(exposure), ""]
            tex_table(exposure, "pilot_exposure", "Pilot: observed exposure (first phase, flaky arm)")
        dec = R / "pilot_decision.md"
        if dec.exists():
            pl_md += [dec.read_text().split("\n", 1)[1].strip(), ""]
        if cost is not None:
            pl_md += ["Cost and time per run:", "", md_table(cost), ""]
            tex_table(cost, "pilot_cost", "Pilot cost per run and projections")
        obs = R / "pilot_observations.md"
        if obs.exists():
            pl_md += [obs.read_text(), ""]
        status["Pilot with one agent: exposure at L1 and L2, main-study level, per-run cost"] = "done"
    else:
        pl_md += ["_Pilot not run yet._", ""]
        status["Pilot with one agent: exposure at L1 and L2, main-study level, per-run cost"] = "not done"

    dv_md = ["## 10. Deviations and open issues", ""]
    dev = R / "deviations.md"
    if dev.exists():
        dv_md += [dev.read_text().split("\n", 1)[1].strip(), ""]

    summary = ["## 1. Summary", "", "| Deliverable | Status |", "|---|---|"]
    for k, v in status.items():
        summary.append(f"| {k} | {v} |")
    summary.append("")
    out = md + summary + sel_md + st_md + cv_md + sh_md + sd_md + in_md + hz_md + pl_md + dv_md
    (R / "README.md").write_text("\n".join(out) + "\n")
    print("wrote", R / "README.md")


if __name__ == "__main__":
    main()
