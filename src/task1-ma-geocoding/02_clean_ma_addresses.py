import csv
import re
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
INPUT_FILE = DATA_DIR / "outputs" / "ma_addresses_raw.csv"
OUTPUT_FILE = DATA_DIR / "outputs" / "ma_addresses_cleaned.csv"

# Detect common PO Box spellings in either address line.
PO_BOX_PATTERN = re.compile(
    r"\b(?:P\s*\.?\s*O\s*\.?\s*BOX|"
    r"POST\s+OFFICE\s+BOX|"
    r"P\s*\.?\s*O\s*\.?\s*B\.?(?=\s*\d))"
    r"\s*#?\s*\w+",
    re.IGNORECASE,
)

NEW_COLUMNS = [
    "address_line1_clean",
    "address_line2_clean",
    "street_clean",
    "city_clean",
    "state_clean",
    "zip5",
    "is_po_box",
    "missing_fields",
    "zip_issue",
    "geocode_status",
]


def clean_text(value):
    # Standardize capitalization and whitespace; retain punctuation.
    return re.sub(r"\s+", " ", value or "").strip().upper()


def clean_zip(value):
    value = (value or "").strip()

    if not value:
        return "", "missing"

    # Accept five digits, nine digits, or ZIP+4.
    if re.fullmatch(r"\d{5}", value):
        return value, ""

    if re.fullmatch(r"\d{9}|\d{5}-\d{4}", value):
        return value[:5], ""

    # Preserve the original ZIP in the input column for review.
    return "", "invalid_format"


def main():
    counts = Counter()
    total = 0

    with INPUT_FILE.open(
        "r", encoding="utf-8-sig", newline=""
    ) as input_file:
        reader = csv.DictReader(input_file)

        required = {
            "record_id",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "zip",
        }
        missing_columns = required - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(
                f"Missing columns: {sorted(missing_columns)}"
            )

        columns = list(reader.fieldnames) + NEW_COLUMNS

        with OUTPUT_FILE.open(
            "w", encoding="utf-8", newline=""
        ) as output_file:
            writer = csv.DictWriter(output_file, fieldnames=columns)
            writer.writeheader()

            for row in reader:
                line1 = clean_text(row["address_line1"])
                line2 = clean_text(row["address_line2"])
                city = clean_text(row["city"])
                state = clean_text(row["state"])

                if state == "MASSACHUSETTS":
                    state = "MA"

                street = " ".join(
                    part for part in (line1, line2) if part
                )
                zip5, zip_issue = clean_zip(row["zip"])

                is_po_box = bool(PO_BOX_PATTERN.search(street))

                # Missing ZIP is distinguished from malformed ZIP.
                missing = []
                for field, value in [
                    ("street", street),
                    ("city", city),
                    ("state", state),
                    ("zip", row["zip"].strip()),
                ]:
                    if not value:
                        missing.append(field)

                # Assign one primary category to every record.
                if is_po_box:
                    status = "po_box"
                elif missing:
                    status = "missing_fields"
                elif zip_issue:
                    status = "invalid_zip"
                elif state != "MA":
                    status = "review_state"
                else:
                    status = "eligible_street"

                row.update({
                    "address_line1_clean": line1,
                    "address_line2_clean": line2,
                    "street_clean": street,
                    "city_clean": city,
                    "state_clean": state,
                    "zip5": zip5,
                    "is_po_box": str(is_po_box).lower(),
                    "missing_fields": ";".join(missing),
                    "zip_issue": zip_issue,
                    "geocode_status": status,
                })

                writer.writerow(row)
                counts[status] += 1
                total += 1

    print(f"Total records: {total:,}")
    print("\nAddress classification:")

    for status in [
        "eligible_street",
        "po_box",
        "missing_fields",
        "invalid_zip",
        "review_state",
    ]:
        count = counts[status]
        percentage = count / total * 100 if total else 0
        print(f"  {status}: {count:,} ({percentage:.2f}%)")

    print(f"\nSaved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()