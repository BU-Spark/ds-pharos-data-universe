"""Step 2: clean addresses, flag PO boxes, classify each record for geocoding.

Same rules as Sprint 2 02_clean_ma_addresses.py; the state check now accepts any New England state.
"""
import csv
import re
from collections import Counter

from config import RAW_FILE, CLEAN_FILE, STATES, normalize_state

PO_BOX_PATTERN = re.compile(
    r"\b(?:P\s*\.?\s*O\s*\.?\s*BOX|"
    r"POST\s+OFFICE\s+BOX|"
    r"P\s*\.?\s*O\s*\.?\s*B\.?(?=\s*\d))"
    r"\s*#?\s*\w+",
    re.IGNORECASE,
)

NEW_COLUMNS = [
    "address_line1_clean", "address_line2_clean", "street_clean", "city_clean",
    "state_clean", "zip5", "is_po_box", "missing_fields", "zip_issue", "geocode_status",
]
STATUSES = ["eligible_street", "po_box", "missing_fields", "invalid_zip", "review_state"]


def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip().upper()


def clean_zip(value):
    value = (value or "").strip()
    if not value:
        return "", "missing"
    if re.fullmatch(r"\d{5}", value):
        return value, ""
    if re.fullmatch(r"\d{9}|\d{5}-\d{4}", value):
        return value[:5], ""
    return "", "invalid_format"


def main():
    counts = Counter()
    by_state = Counter()

    with RAW_FILE.open("r", encoding="utf-8-sig", newline="") as f_in:
        reader = csv.DictReader(f_in)
        columns = list(reader.fieldnames) + NEW_COLUMNS

        with CLEAN_FILE.open("w", encoding="utf-8", newline="") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=columns)
            writer.writeheader()

            for row in reader:
                line1 = clean_text(row["address_line1"])
                line2 = clean_text(row["address_line2"])
                city = clean_text(row["city"])
                state = normalize_state(row["state"])
                street = " ".join(p for p in (line1, line2) if p)
                zip5, zip_issue = clean_zip(row["zip"])
                is_po_box = bool(PO_BOX_PATTERN.search(street))

                missing = [
                    field for field, value in [
                        ("street", street), ("city", city),
                        ("state", state), ("zip", row["zip"].strip()),
                    ] if not value
                ]

                if is_po_box:
                    status = "po_box"
                elif missing:
                    status = "missing_fields"
                elif zip_issue:
                    status = "invalid_zip"
                elif state not in STATES:
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
                by_state[(state, status)] += 1

    total = sum(counts.values())
    print(f"Total records: {total:,}\n\nAddress classification:")
    for s in STATUSES:
        print(f"  {s}: {counts[s]:,} ({counts[s] / total * 100:.2f}%)")

    print("\nBy state (eligible_street / po_box / other):")
    for st in STATES:
        e = by_state[(st, "eligible_street")]
        p = by_state[(st, "po_box")]
        o = sum(v for (s2, k), v in by_state.items() if s2 == st) - e - p
        print(f"  {st}: {e:,} / {p:,} / {o:,}")
    print(f"\nSaved to: {CLEAN_FILE}")


if __name__ == "__main__":
    main()
