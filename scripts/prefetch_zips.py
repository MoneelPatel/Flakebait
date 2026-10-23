"""Download ReproFlake zips for the first N distinct zips per category, in shuffled order.

Usage: uv run python scripts/prefetch_zips.py [N]   (default 15; TD takes all of its zips)
Zips land in data/reproflake/zips/; existing complete files are skipped.
"""
import csv
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORDER = ROOT / "reports/milestone1/candidate_order.csv"
DEST = ROOT / "data/reproflake/zips"


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    DEST.mkdir(parents=True, exist_ok=True)
    wanted, seen = [], set()
    per_cat = {}
    for r in csv.DictReader(open(ORDER)):
        cap = 10**6 if r["category"] == "TD" else n
        if r["zip"] in seen or per_cat.get(r["category"], 0) >= cap:
            continue
        seen.add(r["zip"])
        per_cat[r["category"]] = per_cat.get(r["category"], 0) + 1
        wanted.append((r["category"], r["zip"], r["url"]))

    print(f"prefetching {len(wanted)} zips: {per_cat}", flush=True)

    def fetch(item):
        i, (cat, name, url) = item
        out = DEST / f"{name}.zip"
        done = DEST / f"{name}.zip.ok"
        if done.exists():
            return
        rc = subprocess.run(["curl", "-sfL", "--retry", "3", "-C", "-", "-o", str(out), url]).returncode
        if rc == 0:
            done.touch()
        print(f"[{i}/{len(wanted)}] {cat} {name} rc={rc} size={out.stat().st_size if out.exists() else 0}",
              flush=True)

    # Zenodo throttles per connection, so a few parallel downloads help.
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch, enumerate(wanted, 1)))


if __name__ == "__main__":
    main()
