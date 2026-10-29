import csv
import random
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
INPUT_FILE = DATA_DIR / "outputs" / "ma_addresses_cleaned.csv"

groups = {
    "eligible_street": [],
    "po_box": [],
}

with INPUT_FILE.open(encoding="utf-8-sig", newline="") as file:
    for row in csv.DictReader(file):
        status = row["geocode_status"]
        if status in groups:
            groups[status].append(row)

rng = random.Random(539)

for status, rows in groups.items():
    print(f"\n--- {status}: 10 random samples ---")

    for row in rng.sample(rows, min(10, len(rows))):
        print(
            f"{row['record_id']} | "
            f"L1: {row['address_line1_clean']} | "
            f"L2: {row['address_line2_clean']} | "
            f"{row['city_clean']}, "
            f"{row['state_clean']} {row['zip5']}"
        )