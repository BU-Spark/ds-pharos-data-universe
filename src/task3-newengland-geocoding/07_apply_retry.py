"""Step 7: apply retry results (rounds 1 and 2) to the geocoded file, with strict checks.

A retry Match is accepted only if ALL of these hold:
  1. Census status is Match and the tract code is valid
  2. Matched ZIP == filing ZIP, and matched state == filing state
  3. House number is the same
  4. First street-name word is the same (directions normalized: WEST -> W, etc.)
  5. If both sides have a street type (ST, RD, AVE...), it is the same type
Checks 3-5 stop Census from moving an address to a look-alike street
(e.g. "6 GREENWICH PARK" -> "6 GREENWICH HILLS DR").

Every retried record is logged in outputs/retry/ne_retry_log.csv with the reason.
Records that are still not placed keep needs_zip_fallback = true.

Outputs (outputs/):
  ne_geocoded_final.csv, ne_tract_ready_final.csv, ne_zip_fallback_final.csv,
  ne_geocoding_final_summary.json
New column: geocode_method = tract_direct | tract_retry | (blank = needs ZIP fallback)
"""
import csv
import json
import re
from collections import Counter
from datetime import datetime

from config import OUTPUT_DIR, STATES, ABBR_TO_FIPS

RETRY_DIR = OUTPUT_DIR / "retry"
ALL_FILE = OUTPUT_DIR / "ne_geocoded_all.csv"
CANDIDATES_FILE = RETRY_DIR / "ne_retry_candidates.csv"
RESULT_FILES = [(1, RETRY_DIR / "ne_retry_batch_result.csv"),
                (2, RETRY_DIR / "ne_retry2_batch_result.csv")]

DIRECTIONS = {"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}
STREET_TYPES = {
    "STREET": "ST", "ST": "ST", "ROAD": "RD", "RD": "RD", "AVENUE": "AVE", "AVE": "AVE",
    "DRIVE": "DR", "DR": "DR", "LANE": "LN", "LN": "LN", "WAY": "WAY", "PLACE": "PL",
    "PL": "PL", "SQUARE": "SQ", "SQ": "SQ", "BOULEVARD": "BLVD", "BLVD": "BLVD",
    "COURT": "CT", "CT": "CT", "CIRCLE": "CIR", "CIR": "CIR", "PARKWAY": "PKWY",
    "PKWY": "PKWY", "PLAZA": "PLZ", "PLZ": "PLZ", "TERRACE": "TER", "TER": "TER",
    "HIGHWAY": "HWY", "HWY": "HWY", "PARK": "PARK", "PK": "PARK", "RIDGE": "RDG",
    "RDG": "RDG", "ROW": "ROW", "TURNPIKE": "TPKE", "TPKE": "TPKE",
}


def tokens(street):
    return [DIRECTIONS.get(t, t) for t in re.sub(r"[^A-Z0-9 ]", " ", street.upper()).split()]


def street_type(toks):
    found = [STREET_TYPES[t] for t in toks[1:] if t in STREET_TYPES]
    return found[-1] if found else None


def check(submitted, matched_address, zip5, state):
    """Return '' if accepted, otherwise the rejection reason."""
    parts = [p.strip() for p in matched_address.split(",")]
    if len(parts) < 4:
        return "bad_matched_address"
    m_street, m_state, m_zip = parts[0], parts[-2], parts[-1][:5]
    if m_zip != zip5:
        return "zip_differs"
    if m_state != state:
        return "state_differs"
    s, m = tokens(submitted), tokens(m_street)
    if len(s) < 2 or len(m) < 2 or s[0] != m[0]:
        return "house_number_differs"
    if s[1] != m[1]:
        return "street_name_differs"
    st, mt = street_type(s), street_type(m)
    if st and mt and st != mt:
        return "street_type_differs"
    return ""


def main():
    with CANDIDATES_FILE.open(encoding="utf-8-sig", newline="") as f:
        cands = {c["record_id"]: c for c in csv.DictReader(f)}

    accepted, log = {}, []
    for rnd, path in RESULT_FILES:
        with path.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.reader(f):
                if not r or r[0] in accepted:
                    continue
                c = cands[r[0]]
                status, reason = r[2], ""
                if status == "Match":
                    st, co, tr = [v.strip() for v in r[8:11]]
                    if not (re.fullmatch(r"\d{2}", st) and re.fullmatch(r"\d{3}", co)
                            and re.fullmatch(r"\d{6}", tr)):
                        reason = "invalid_tract"
                    elif st != ABBR_TO_FIPS[c["state_clean"]]:
                        reason = "state_fips_differs"
                    else:
                        reason = check(c["street_retry"], r[4], c["zip5"], c["state_clean"])
                    if not reason:
                        lon, lat = [v.strip() for v in r[5].split(",")]
                        accepted[r[0]] = {
                            "census_batch": f"retry_round{rnd}", "census_match_status": "Match",
                            "census_match_type": r[3], "census_matched_address": r[4],
                            "longitude": lon, "latitude": lat, "census_state_fips": st,
                            "census_county_fips": co, "census_tract": tr,
                            "tract_geoid": st + co + tr, "census_block": r[11],
                            "geocode_source": f"census_retry_round{rnd}",
                        }
                log.append({"record_id": r[0], "round": rnd, "state_clean": c["state_clean"],
                            "street_clean": c["street_clean"], "street_retry": c["street_retry"],
                            "census_status": status, "matched_address": r[4] if status == "Match" else "",
                            "decision": "accepted" if status == "Match" and not reason else
                                        ("rejected_" + reason if status == "Match" else "not_matched")})

    with (RETRY_DIR / "ne_retry_log.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(log[0]))
        w.writeheader()
        w.writerows(log)

    # Apply to the full file
    with ALL_FILE.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames) + ["geocode_method"]
        rows = list(reader)

    per_state = {s: Counter() for s in STATES}
    reasons = Counter()
    for row in rows:
        rid = row["record_id"]
        if rid in accepted:
            row.update(accepted[rid])
            row["needs_zip_fallback"], row["fallback_reason"] = "false", ""
            row["geocode_method"] = "tract_retry"
        elif row["needs_zip_fallback"] == "false":
            row["geocode_method"] = "tract_direct"
        else:
            row["geocode_method"] = ""
            action = cands.get(rid, {}).get("retry_action")
            if action == "missed_po_box":
                row["fallback_reason"] = "po_box"
            elif action == "skip_no_house_number":
                row["fallback_reason"] = "no_house_number"
            reasons[row["fallback_reason"]] += 1
        ps = per_state[row["state_clean"]]
        ps["total"] += 1
        ps[row["geocode_method"] or "needs_zip_fallback"] += 1

    def save(name, subset):
        with (OUTPUT_DIR / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=columns)
            w.writeheader()
            w.writerows(subset)

    ready = [r for r in rows if r["needs_zip_fallback"] == "false"]
    fallback = [r for r in rows if r["needs_zip_fallback"] == "true"]
    save("ne_geocoded_final.csv", rows)
    save("ne_tract_ready_final.csv", ready)
    save("ne_zip_fallback_final.csv", fallback)

    decisions = Counter(l["decision"] for l in log)
    summary = {
        "summary_created_at": datetime.now().astimezone().isoformat(),
        "unit": "filing record; not unique organization",
        "total_records": len(rows), "tract_ready_records": len(ready),
        "zip_fallback_records": len(fallback),
        "overall_tract_coverage_pct": round(len(ready) / len(rows) * 100, 2),
        "retry_decisions": dict(decisions), "fallback_reasons": dict(reasons),
        "by_state": {s: {"total": c["total"], "tract_direct": c["tract_direct"], "tract_retry": c["tract_retry"], "needs_zip_fallback": c["needs_zip_fallback"], "tract_coverage_pct": round((c["tract_direct"] + c["tract_retry"]) / c["total"] * 100, 2)}
                     for s, c in per_state.items()},
    }
    with (OUTPUT_DIR / "ne_geocoding_final_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("Retry decisions:")
    for k, v in decisions.most_common():
        print(f"  {k}: {v:,}")
    print(f"\nAccepted retry matches: {len(accepted):,}")
    print(f"Tract ready: {len(ready):,} / {len(rows):,} ({summary['overall_tract_coverage_pct']}%)")
    print(f"Needs ZIP fallback: {len(fallback):,} {dict(reasons)}")
    print(f"\n{'state':<6}{'total':>8}{'direct':>8}{'retry':>7}{'coverage%':>11}")
    for s, c in summary["by_state"].items():
        print(f"{s:<6}{c['total']:>8,}{c['tract_direct']:>8,}{c['tract_retry']:>7,}{c['tract_coverage_pct']:>11}")


if __name__ == "__main__":
    main()
