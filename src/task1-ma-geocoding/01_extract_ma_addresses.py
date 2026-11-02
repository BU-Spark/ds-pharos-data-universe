import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = DATA_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "ma_addresses_raw.csv"

OUTPUT_COLUMNS = [
    "record_id",
    "source_file",
    "source_row",
    "form_type",
    "ein",
    "tax_year",
    "org_name",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "zip",
    "country",
]

SOURCES = [
    {
        "filename": "irs990_f9_p00_t00_header_2024_2025.csv",
        "mapping": {
            "form_type": "f9_00_return_type",
            "ein": "f9_00_org_ein",
            "tax_year": "f9_00_tax_year",
            "address_line1": "f9_00_org_addr_l1",
            "address_line2": "f9_00_org_addr_l2",
            "city": "f9_00_org_addr_city",
            "state": "f9_00_org_addr_state",
            "zip": "f9_00_org_addr_zip",
            "country": "f9_00_org_addr_cntr",
        },
        "name_columns": ["f9_00_org_name_l1", "f9_00_org_name_l2"],
        "id_prefix": "f9",
    },
    {
        "filename": "irs990pf_pf_p00_t00_header_2024_2025.csv",
        "mapping": {
            "ein": "ein",
            "tax_year": "taxyear",
            "address_line1": "numberandstreet",
            "city": "cityortown",
            "state": "stateorprovince",
            "zip": "zipcode",
            "country": "country",
        },
        "name_columns": ["nameoffoundation"],
        "id_prefix": "pf",
    },
]


def main():
    total_ma = 0

    with OUTPUT_FILE.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()

        for source in SOURCES:
            input_path = DATA_DIR / source["filename"]
            mapping = source["mapping"]
            rows_read = 0
            ma_rows = 0

            with input_path.open(
                "r", encoding="utf-8-sig", newline=""
            ) as input_file:
                reader = csv.DictReader(input_file)

                required = set(mapping.values()) | set(source["name_columns"])
                missing = required - set(reader.fieldnames or [])
                if missing:
                    raise ValueError(
                        f"{input_path.name}: missing columns {sorted(missing)}"
                    )

                # source_row counts data records, excluding the header.
                for source_row, row in enumerate(reader, start=1):
                    rows_read += 1
                    state = row[mapping["state"]].strip().upper()

                    if state not in {"MA", "MASSACHUSETTS"}:
                        continue

                    record = {column: "" for column in OUTPUT_COLUMNS}

                    # Read and write strings to preserve leading zeros.
                    for target, original in mapping.items():
                        record[target] = row[original]

                    record["record_id"] = (
                        f"{source['id_prefix']}_{source_row}"
                    )
                    record["source_file"] = input_path.name
                    record["source_row"] = source_row
                    record["org_name"] = " ".join(
                        row[column].strip()
                        for column in source["name_columns"]
                        if row[column].strip()
                    )

                    if source["id_prefix"] == "pf":
                        record["form_type"] = "990-PF"

                    writer.writerow(record)
                    ma_rows += 1

            total_ma += ma_rows
            print(
                f"{input_path.name}: "
                f"total={rows_read:,}, MA={ma_rows:,}"
            )

    print(f"\nTotal MA records: {total_ma:,}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
