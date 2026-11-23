"""Step 3: write Census batch-geocoder input files (no header, max 10,000 rows each).

Only states NOT in REUSE_PRIOR_RESULTS are written; MA results come from Sprint 2.
Format per row: record_id, street, city, state, zip5
"""
import csv

from config import CLEAN_FILE, BATCH_DIR, BATCH_SIZE, REUSE_PRIOR_RESULTS


def main():
    with CLEAN_FILE.open(encoding="utf-8-sig", newline="") as f:
        rows = [
            r for r in csv.DictReader(f)
            if r["geocode_status"] == "eligible_street"
            and r["state_clean"] not in REUSE_PRIOR_RESULTS
        ]
    if not rows:
        raise ValueError("No eligible addresses to submit.")

    ids = [r["record_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate record IDs found.")
    for r in rows:
        for c in ["record_id", "street_clean", "city_clean", "state_clean", "zip5"]:
            if not r[c].strip():
                raise ValueError(f"{r['record_id']}: empty {c}")

    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    for old in BATCH_DIR.glob("ne_batch_*.csv"):
        old.unlink()

    for start in range(0, len(rows), BATCH_SIZE):
        n = start // BATCH_SIZE + 1
        batch = rows[start:start + BATCH_SIZE]
        path = BATCH_DIR / f"ne_batch_{n:02d}.csv"
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            for r in batch:  # Census input files must NOT have a header
                w.writerow([r["record_id"], r["street_clean"], r["city_clean"],
                            r["state_clean"], r["zip5"]])
        print(f"{path.name}: {len(batch):,} addresses")

    print(f"\nTotal prepared: {len(rows):,}\nSaved to: {BATCH_DIR}")


if __name__ == "__main__":
    main()
