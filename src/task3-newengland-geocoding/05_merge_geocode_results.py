"""Step 5: merge Census results back onto every New England filing record.

- MA: Census columns are copied from Sprint 2 ma_geocoded_all.csv by record_id
  (same source files and row numbering, so IDs match; this is checked).
- CT/RI/NH/VT/ME: parsed from outputs/census_results/ne_batch_XX_result.csv.
Every filing is kept. Records without a valid in-state tract are flagged for ZIP fallback.
"""
import csv
import json
import re
from collections import Counter
from datetime import datetime

from config import (CLEAN_FILE, OUTPUT_DIR, RESULT_DIR, MA_PRIOR_GEOCODED, STATES,
                    ABBR_TO_FIPS, REUSE_PRIOR_RESULTS, CENSUS_BENCHMARK, CENSUS_VINTAGE)

NEW_COLUMNS = [
    "census_batch", "census_match_status", "census_match_type", "census_matched_address",
    "longitude", "latitude", "census_state_fips", "census_county_fips", "census_tract",
    "tract_geoid", "census_block", "needs_zip_fallback", "fallback_reason",
    "census_benchmark", "census_vintage", "geocode_source",
]
CARRY = [c for c in NEW_COLUMNS if c not in ("needs_zip_fallback", "fallback_reason", "geocode_source")]


def parse_result_row(row, batch_label):
    if len(row) < 3:
        raise ValueError(f"Malformed row in {batch_label}: {row}")
    record_id, status = row[0], row[2]
    if status not in {"Match", "No_Match", "Tie"}:
        raise ValueError(f"Unexpected status for {record_id}: {status}")

    r = {c: "" for c in NEW_COLUMNS}
    r.update(census_batch=batch_label, census_match_status=status,
             census_benchmark=CENSUS_BENCHMARK, census_vintage=CENSUS_VINTAGE)
    if status == "Match":
        if len(row) < 12:
            raise ValueError(f"Incomplete matched result: {record_id}")
        r["census_match_type"], r["census_matched_address"] = row[3], row[4]
        lon, lat = [v.strip() for v in row[5].split(",")]
        float(lon), float(lat)
        r["longitude"], r["latitude"] = lon, lat
        st, co, tr = [v.strip() for v in row[8:11]]
        r.update(census_state_fips=st, census_county_fips=co, census_tract=tr, census_block=row[11])
        if re.fullmatch(r"\d{2}", st) and re.fullmatch(r"\d{3}", co) and re.fullmatch(r"\d{6}", tr):
            r["tract_geoid"] = st + co + tr
    return record_id, r


def main():
    with CLEAN_FILE.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        original_columns = list(reader.fieldnames)
        addresses = list(reader)

    # 1) New Census results (non-MA states)
    results = {}
    result_files = sorted(RESULT_DIR.glob("ne_batch_*_result.csv"))
    for path in result_files:
        label = path.stem.replace("_result", "")
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.reader(f):
                if not row:
                    continue
                rid, r = parse_result_row(row, label)
                if rid in results:
                    raise ValueError(f"Duplicate result ID: {rid}")
                r["geocode_source"] = "census_batch_m4"
                results[rid] = r

    expected = {a["record_id"] for a in addresses
                if a["geocode_status"] == "eligible_street"
                and a["state_clean"] not in REUSE_PRIOR_RESULTS}
    if set(results) != expected:
        raise ValueError(f"ID mismatch: missing={len(expected - set(results))}, "
                         f"unexpected={len(set(results) - expected)}")

    # 2) Prior MA results, checked against the re-extracted addresses
    prior = {}
    with MA_PRIOR_GEOCODED.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            prior[row["record_id"]] = row
    mismatched = 0
    for a in addresses:
        if a["state_clean"] in REUSE_PRIOR_RESULTS:
            p = prior.get(a["record_id"])
            if p is None or p["street_clean"] != a["street_clean"] or p["ein"] != a["ein"]:
                mismatched += 1
                continue
            if p["census_match_status"] in ("Match", "No_Match", "Tie"):
                r = {c: p.get(c, "") for c in CARRY}
                r["geocode_source"] = "census_batch_sprint2"
                results[a["record_id"]] = r
    if mismatched:
        raise ValueError(f"{mismatched} MA records do not line up with Sprint 2 output")

    # 3) Merge and flag fallback
    merged, statuses, reasons = [], Counter(), Counter()
    per_state = {s: Counter() for s in STATES}
    for a in addresses:
        row = dict(a)
        r = results.get(a["record_id"])
        if r is None:
            r = {c: "" for c in NEW_COLUMNS}
            r["census_match_status"] = "Not_Submitted"
            reason = a["geocode_status"]
        elif r["census_match_status"] != "Match":
            reason = r["census_match_status"]
        elif not r["tract_geoid"]:
            reason = "matched_without_tract"
        elif r["census_state_fips"] != ABBR_TO_FIPS.get(a["state_clean"]):
            reason = "matched_outside_state"
        else:
            reason = ""
        r["needs_zip_fallback"] = str(bool(reason)).lower()
        r["fallback_reason"] = reason
        row.update(r)
        merged.append(row)

        statuses[r["census_match_status"]] += 1
        if reason:
            reasons[reason] += 1
        ps = per_state.get(a["state_clean"])
        if ps is not None:
            ps["total"] += 1
            ps["submitted"] += r["census_match_status"] in ("Match", "No_Match", "Tie")
            ps["matched"] += r["census_match_status"] == "Match"
            ps["tract_ready"] += not reason

    columns = original_columns + NEW_COLUMNS

    def save(name, rows):
        path = OUTPUT_DIR / name
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=columns)
            w.writeheader()
            w.writerows(rows)
        return path

    save("ne_geocoded_all.csv", merged)
    ready = [r for r in merged if r["needs_zip_fallback"] == "false"]
    fallback = [r for r in merged if r["needs_zip_fallback"] == "true"]
    save("ne_tract_ready.csv", ready)
    save("ne_zip_fallback.csv", fallback)

    def pct(a, b):
        return round(a / b * 100, 2) if b else None

    state_table = {
        s: {**c, "submitted_match_rate_pct": pct(c["matched"], c["submitted"]),
            "tract_coverage_pct": pct(c["tract_ready"], c["total"])}
        for s, c in per_state.items()
    }
    submitted = sum(c["submitted"] for c in per_state.values())
    summary = {
        "summary_created_at": datetime.now().astimezone().isoformat(),
        "benchmark": CENSUS_BENCHMARK, "vintage": CENSUS_VINTAGE,
        "unit": "filing record; not unique organization",
        "total_records": len(merged),
        "submitted_records": submitted,
        "matched_records": statuses["Match"],
        "no_match_records": statuses["No_Match"],
        "tie_records": statuses["Tie"],
        "not_submitted_records": statuses["Not_Submitted"],
        "tract_ready_records": len(ready),
        "zip_fallback_records": len(fallback),
        "fallback_reasons": dict(reasons),
        "submitted_match_rate_pct": pct(statuses["Match"], submitted),
        "overall_tract_coverage_pct": pct(len(ready), len(merged)),
        "by_state": state_table,
        "result_files": [str(p) for p in result_files],
        "ma_reused_from": str(MA_PRIOR_GEOCODED),
    }
    with (OUTPUT_DIR / "ne_geocoding_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Total records: {len(merged):,} | tract ready: {len(ready):,} | ZIP fallback: {len(fallback):,}")
    print(f"{'state':<6}{'total':>8}{'submitted':>11}{'matched':>9}{'match%':>8}{'coverage%':>11}")
    for s, c in state_table.items():
        print(f"{s:<6}{c['total']:>8,}{c['submitted']:>11,}{c['matched']:>9,}"
              f"{c['submitted_match_rate_pct'] or 0:>8}{c['tract_coverage_pct'] or 0:>11}")
    print(f"\nFallback reasons: {dict(reasons)}")


if __name__ == "__main__":
    main()
