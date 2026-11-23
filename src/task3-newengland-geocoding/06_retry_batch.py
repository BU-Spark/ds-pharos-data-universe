"""Step 6: build one Census retry batch for addresses that failed the first pass (No_Match / Tie).

For each failed record:
  - Missed PO boxes (e.g. "BOX 806") are not retried; they stay in ZIP fallback.
  - Otherwise the street is cleaned with simple rules (spelled numbers, unit/floor words,
    trailing unit numbers, C/O / ATTN prefixes, leading building names), and the city is
    left blank so Census matches on street + state + ZIP only.
The original street is never overwritten; the cleaned version goes in street_retry.

Outputs (outputs/retry/):
  ne_retry_batch.csv       - upload this to the Census batch geocoder (no header)
  ne_retry_candidates.csv  - before/after for every failed record, with the rules applied
"""
import csv
import re
from collections import Counter

from config import OUTPUT_DIR

FALLBACK_FILE = OUTPUT_DIR / "ne_zip_fallback.csv"
RETRY_DIR = OUTPUT_DIR / "retry"
BATCH_FILE = RETRY_DIR / "ne_retry_batch.csv"
CANDIDATES_FILE = RETRY_DIR / "ne_retry_candidates.csv"

SPELLED = {"ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE": "5",
           "SIX": "6", "SEVEN": "7", "EIGHT": "8", "NINE": "9", "TEN": "10"}
SUFFIX = (r"(?:STREET|ST|ROAD|RD|AVENUE|AVE|DRIVE|DR|LANE|LN|WAY|PLACE|PL|SQUARE|SQ|"
          r"BLVD|BOULEVARD|COURT|CT|CIRCLE|CIR|PARKWAY|PKWY|PLAZA|TERRACE|TER|HWY|"
          r"HIGHWAY|ROW|PARK|TURNPIKE|TPKE)")

RE_BOX = re.compile(r"\b(?:B[O0]\s+|P\s*O\s+)?BOX\s*#?\s*\d+\b")
RE_CARE_OF = re.compile(r"\b(?:C/O|C O|CO|ATTN|ATTENTION|CARE OF)\b")
RE_ORDINAL_FLOOR = re.compile(r"\b\d+(?:ST|ND|RD|TH)?\s*(?:FLOOR|FLR|FL)\b")
RE_UNIT = re.compile(
    r"(?:#\s*[A-Z0-9-]+|\b(?:SUITE|STE|UNIT|APT|APARTMENT|FLOOR|FLR|FL|ROOM|RM|"
    r"BLDG|BUILDING|DEPT|PMB|OFFICE|OFC)\b\.?(?:\s*#?\s*[A-Z]?\d+[A-Z]?(?:-\d+)?)?)"
)
RE_TRAILING_NUM = re.compile(rf"(\b{SUFFIX})\s+\d+[A-Z]?(?:-\d+)?$")
RE_FIRST_HOUSE_NUM = re.compile(r"\b\d+[A-Z]?\s+[A-Z]")


def squash(s):
    return re.sub(r"\s+", " ", s).strip()


def clean_street(street):
    """Return (cleaned_street, rules_applied, is_missed_po_box)."""
    s, rules = street, []

    # A. Spelled-out house number at the start.
    first = s.split(" ", 1)[0]
    if first in SPELLED:
        s = SPELLED[first] + s[len(first):]
        rules.append("spelled_number")

    # F. Missed PO box: strip "BOX 123"; if nothing street-like is left, it is a PO box.
    if RE_BOX.search(s):
        s = squash(RE_BOX.sub(" ", s))
        rules.append("box_removed")
        if not re.search(r"\d", s):
            return "", rules, True

    # D/E. C/O, ATTN or a leading name: start from the first "number + word".
    if RE_CARE_OF.search(s) or not s[:1].isdigit():
        m = RE_FIRST_HOUSE_NUM.search(s)
        if m and m.start() > 0:
            s = s[m.start():]
            rules.append("prefix_removed")

    # B. Unit, suite and floor information.
    new = squash(RE_UNIT.sub(" ", RE_ORDINAL_FLOOR.sub(" ", s)))
    if new != s:
        s = new
        rules.append("unit_removed")

    # C. Number left after the street suffix (e.g. "2 LIBERTY SQUARE 500").
    new = RE_TRAILING_NUM.sub(r"\1", s)
    if new != s:
        s = new
        rules.append("trailing_number_removed")

    return squash(s), rules, False


def main():
    RETRY_DIR.mkdir(parents=True, exist_ok=True)
    with FALLBACK_FILE.open(encoding="utf-8-sig", newline="") as f:
        failed = [r for r in csv.DictReader(f) if r["fallback_reason"] in ("No_Match", "Tie")]

    counts, rule_counts = Counter(), Counter()
    candidates, batch = [], []
    for r in failed:
        street_retry, rules, missed_po = clean_street(r["street_clean"])
        if missed_po:
            action = "missed_po_box"
        elif not street_retry or not street_retry[:1].isdigit():
            action = "skip_no_house_number"
        else:
            action = "retry"
            batch.append([r["record_id"], street_retry, "", r["state_clean"], r["zip5"]])
        counts[action] += 1
        for rule in rules:
            rule_counts[rule] += 1
        candidates.append({
            "record_id": r["record_id"], "ein": r["ein"], "tax_year": r["tax_year"],
            "state_clean": r["state_clean"], "zip5": r["zip5"],
            "first_pass_status": r["fallback_reason"],
            "street_clean": r["street_clean"], "city_clean": r["city_clean"],
            "street_retry": street_retry, "rules_applied": ";".join(rules),
            "retry_action": action,
        })

    with CANDIDATES_FILE.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(candidates[0]))
        w.writeheader()
        w.writerows(candidates)
    with BATCH_FILE.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(batch)  # Census input: no header

    print(f"Failed first-pass records: {len(failed):,}")
    for k in ("retry", "missed_po_box", "skip_no_house_number"):
        print(f"  {k}: {counts[k]:,}")
    print("\nRules applied (a record can have several):")
    for k, v in rule_counts.most_common():
        print(f"  {k}: {v:,}")
    print(f"\nRetry batch: {BATCH_FILE} ({len(batch):,} rows)")
    print(f"Before/after: {CANDIDATES_FILE}")


if __name__ == "__main__":
    main()
