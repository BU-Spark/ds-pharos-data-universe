import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
INPUT_FILE = DATA_DIR / "outputs" / "ma_addresses_cleaned.csv"
OUTPUT_DIR = DATA_DIR / "outputs" / "census_batches"

BATCH_SIZE = 10_000


def main():
    with INPUT_FILE.open(
        encoding="utf-8-sig", newline=""
    ) as input_file:
        reader = csv.DictReader(input_file)
        rows = [
            row
            for row in reader
            if row["geocode_status"] == "eligible_street"
        ]

    if not rows:
        raise ValueError("No eligible addresses found.")

    ids = [row["record_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate record IDs found.")

    # Validate all rows before creating batch files.
    for row in rows:
        for column in [
            "record_id",
            "street_clean",
            "city_clean",
            "state_clean",
            "zip5",
        ]:
            if not row[column].strip():
                raise ValueError(
                    f"{row['record_id']}: empty {column}"
                )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total_written = 0

    for start in range(0, len(rows), BATCH_SIZE):
        batch_number = start // BATCH_SIZE + 1
        batch = rows[start:start + BATCH_SIZE]
        output_file = (
            OUTPUT_DIR / f"ma_batch_{batch_number:02d}.csv"
        )

        with output_file.open(
            "w", encoding="utf-8", newline=""
        ) as file:
            writer = csv.writer(file)

            # Census input files must NOT have a header.
            for row in batch:
                writer.writerow([
                    row["record_id"],
                    row["street_clean"],
                    row["city_clean"],
                    row["state_clean"],
                    row["zip5"],
                ])

        total_written += len(batch)
        print(f"{output_file.name}: {len(batch):,} addresses")

    print(f"\nTotal prepared: {total_written:,}")
    print(f"Saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()