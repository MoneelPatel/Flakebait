"""Load the ReproFlake index, assign categories, and write the seeded candidate order.

Outputs:
  reports/milestone1/category_counts.csv   index counts vs. the proposal's expected counts
  reports/milestone1/candidate_order.csv   every candidate per category, in shuffled order
"""
import csv
import hashlib
import random
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data/reproflake/meta/test_config.csv"
OUT = ROOT / "reports/milestone1"

# The index labels one OD-style test "britle"; the paper's 126 OD count includes it.
CATEGORY_MAP = {"id": "ID", "od": "OD", "britle": "OD", "nio": "NIO", "td": "TD"}
EXPECTED = {"ID": 819, "OD": 126, "NIO": 125, "TD": 36}
CATEGORIES = ["ID", "OD", "NIO", "TD"]


def load_index():
    with open(INDEX, newline="") as f:
        return list(csv.DictReader(f))


def category_seed(base, category):
    digest = hashlib.sha256(f"{base}:{category}".encode()).hexdigest()
    return int(digest[:16], 16)


def main():
    seeds = yaml.safe_load(open(ROOT / "config/seeds.yaml"))
    base = seeds["selection_shuffle"]
    rows = load_index()

    by_cat = {c: [] for c in CATEGORIES}
    excluded = 0
    for r in rows:
        cat = CATEGORY_MAP.get(r["test_type"].strip().lower())
        if cat is None:
            excluded += 1
            continue
        by_cat[cat].append(r)

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "category_counts.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["category", "index_count", "expected", "match"])
        for c in CATEGORIES:
            n = len(by_cat[c])
            w.writerow([c, n, EXPECTED[c], n == EXPECTED[c]])
        w.writerow(["unclassified (excluded)", excluded, 9, excluded == 9])

    with open(OUT / "candidate_order.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["category", "position", "seed", "result_container", "project", "module",
                    "zip", "flaky_test", "polluter", "java", "nondex_seed", "url"])
        for c in CATEGORIES:
            seed = category_seed(base, c)
            # Sort first so the shuffle depends only on the seed, not on index row order.
            cands = sorted(by_cat[c], key=lambda r: r["result_container"])
            random.Random(seed).shuffle(cands)
            for i, r in enumerate(cands, 1):
                w.writerow([c, i, seed, r["result_container"], r["zip"].split("=")[0], r["module"],
                            r["zip"], r["flaky_test"], r["polluter/state setter"], r["java"],
                            r["nondexSeed"], r["url"]])

    for c in CATEGORIES:
        print(f"{c}: {len(by_cat[c])} candidates (seed {category_seed(base, c)})")
    print(f"excluded unclassified: {excluded}")


if __name__ == "__main__":
    main()
