"""Step 1: extract New England filer addresses from the IRS 990 and 990-PF header files.

Same logic as Sprint 2 01_extract_ma_addresses.py, but keeps all six New England states.
record_id is <prefix>_<source_row>, identical to Sprint 2, so MA IDs line up with prior results.
"""
import csv
from collections import Counter

from config import RAW_DIR, OUTPUT_DIR, RAW_FILE, STATES, normalize_state

OUTPUT_COLUMNS = [
    "record_id", "source_file", "source_row", "form_type", "ein", "tax_year",
    "org_name", "address_line1", "address_line2", "city", "state", "zip", "country",
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
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    by_state = Counter()

    with RAW_FILE.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()

        for source in SOURCES:
            input_path = RAW_DIR / source["filename"]
            mapping = source["mapping"]
            rows_read = kept = 0

            with input_path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                required = set(mapping.values()) | set(source["name_columns"])
                missing = required - set(reader.fieldnames or [])
                if missing:
                    raise ValueError(f"{input_path.name}: missing columns {sorted(missing)}")

                # source_row counts data records, excluding the header (same as Sprint 2).
                for source_row, row in enumerate(reader, start=1):
                    rows_read += 1
                    state = normalize_state(row[mapping["state"]])
                    if state not in STATES:
                        continue

                    record = {c: "" for c in OUTPUT_COLUMNS}
                    for target, original in mapping.items():
                        record[target] = row[original]  # strings keep leading zeros
                    record["record_id"] = f"{source['id_prefix']}_{source_row}"
                    record["source_file"] = input_path.name
                    record["source_row"] = source_row
                    record["org_name"] = " ".join(
                        row[c].strip() for c in source["name_columns"] if row[c].strip()
                    )
                    if source["id_prefix"] == "pf":
                        record["form_type"] = "990-PF"

                    writer.writerow(record)
                    kept += 1
                    by_state[state] += 1

            print(f"{input_path.name}: total={rows_read:,}, New England={kept:,}")

    print("\nRecords by state:")
    for s in STATES:
        print(f"  {s}: {by_state[s]:,}")
    print(f"Total: {sum(by_state.values()):,}\nSaved to: {RAW_FILE}")


if __name__ == "__main__":
    main()
