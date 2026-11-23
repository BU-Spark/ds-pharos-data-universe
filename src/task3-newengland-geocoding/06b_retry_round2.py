"""Step 6b: second retry round, WITH the city.

Round 1 (06_retry_batch.py) sent cleaned streets with a blank city. Census matched only
74 of 2,826, and addresses left unchanged (city blank only) matched 0, so the batch
geocoder needs the city. Round 2 resends only addresses whose street was cleaned and
that did not match in round 1, this time with the original city.

Input:  outputs/retry/ne_retry_candidates.csv, outputs/retry/ne_retry_batch_result.csv
Output: outputs/retry/ne_retry2_batch.csv  (upload to Census; no header)
"""
import csv

from config import OUTPUT_DIR

RETRY_DIR = OUTPUT_DIR / "retry"
CANDIDATES_FILE = RETRY_DIR / "ne_retry_candidates.csv"
ROUND1_RESULT = RETRY_DIR / "ne_retry_batch_result.csv"
BATCH_FILE = RETRY_DIR / "ne_retry2_batch.csv"


def main():
    with ROUND1_RESULT.open(encoding="utf-8-sig", newline="") as f:
        round1 = {r[0]: r[2] for r in csv.reader(f) if r}

    batch = []
    with CANDIDATES_FILE.open(encoding="utf-8-sig", newline="") as f:
        for c in csv.DictReader(f):
            if c["retry_action"] != "retry":
                continue
            if c["street_retry"] == c["street_clean"]:
                continue  # nothing was cleaned; resending would repeat the first pass
            if round1.get(c["record_id"]) == "Match":
                continue  # already matched in round 1
            batch.append([c["record_id"], c["street_retry"], c["city_clean"],
                          c["state_clean"], c["zip5"]])

    with BATCH_FILE.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(batch)
    print(f"Round 2 batch: {len(batch):,} rows -> {BATCH_FILE}")


if __name__ == "__main__":
    main()
