import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = DATA_DIR / "outputs"
DOWNLOADS = Path.home() / "Downloads"

CLEANED_FILE = OUTPUT_DIR / "ma_addresses_cleaned.csv"

RESULT_FILES = [
    DOWNLOADS / f"ma_batch_{i:02d}_result.csv"
    for i in range(1, 4)
]

NEW_COLUMNS = [
    "census_batch",
    "census_match_status",
    "census_match_type",
    "census_matched_address",
    "longitude",
    "latitude",
    "census_state_fips",
    "census_county_fips",
    "census_tract",
    "tract_geoid",
    "census_block",
    "needs_zip_fallback",
    "fallback_reason",
    "census_benchmark",
    "census_vintage",
]


def main():
    with CLEANED_FILE.open(
        encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)
        original_columns = list(reader.fieldnames)
        addresses = list(reader)

    original_ids = [row["record_id"] for row in addresses]
    if len(original_ids) != len(set(original_ids)):
        raise ValueError("Duplicate IDs in cleaned addresses.")

    eligible_ids = {
        row["record_id"]
        for row in addresses
        if row["geocode_status"] == "eligible_street"
    }

    results = {}

    for batch_number, path in enumerate(RESULT_FILES, start=1):
        with path.open(
            encoding="utf-8-sig", newline=""
        ) as file:
            for row in csv.reader(file):
                if len(row) < 3:
                    raise ValueError(f"Malformed row in {path.name}")

                record_id = row[0]
                status = row[2]

                if record_id in results:
                    raise ValueError(f"Duplicate result ID: {record_id}")

                if status not in {"Match", "No_Match", "Tie"}:
                    raise ValueError(
                        f"Unexpected status for {record_id}: {status}"
                    )

                result = {
                    column: "" for column in NEW_COLUMNS
                }
                result["census_batch"] = batch_number
                result["census_match_status"] = status
                result["census_benchmark"] = "Public_AR_Current"
                result["census_vintage"] = "ACS2024_Current"

                if status == "Match":
                    if len(row) < 12:
                        raise ValueError(
                            f"Incomplete matched result: {record_id}"
                        )

                    result["census_match_type"] = row[3]
                    result["census_matched_address"] = row[4]

                    coordinates = row[5].split(",")
                    if len(coordinates) != 2:
                        raise ValueError(
                            f"Invalid coordinates: {record_id}"
                        )

                    longitude, latitude = [
                        value.strip() for value in coordinates
                    ]
                    float(longitude)
                    float(latitude)

                    result["longitude"] = longitude
                    result["latitude"] = latitude

                    state, county, tract = [
                        value.strip() for value in row[8:11]
                    ]

                    result["census_state_fips"] = state
                    result["census_county_fips"] = county
                    result["census_tract"] = tract
                    result["census_block"] = row[11]

                    geoid = state + county + tract
                    valid_tract = (
                        re.fullmatch(r"\d{2}", state)
                        and re.fullmatch(r"\d{3}", county)
                        and re.fullmatch(r"\d{6}", tract)
                    )

                    if valid_tract:
                        result["tract_geoid"] = geoid

                results[record_id] = result

    # All submitted records must return exactly one result.
    returned_ids = set(results)
    if returned_ids != eligible_ids:
        raise ValueError(
            f"ID mismatch: missing={len(eligible_ids - returned_ids)}, "
            f"unexpected={len(returned_ids - eligible_ids)}"
        )

    merged = []
    statuses = Counter()
    fallback_reasons = Counter()

    for address in addresses:
        record_id = address["record_id"]
        row = dict(address)

        result = results.get(record_id)

        if result is None:
            result = {column: "" for column in NEW_COLUMNS}
            result["census_match_status"] = "Not_Submitted"
            reason = address["geocode_status"]
        elif result["census_match_status"] != "Match":
            reason = result["census_match_status"]
        elif not result["tract_geoid"]:
            reason = "matched_without_tract"
        elif result["census_state_fips"] != "25":
            reason = "matched_outside_ma"
        else:
            reason = ""

        result["needs_zip_fallback"] = str(bool(reason)).lower()
        result["fallback_reason"] = reason

        row.update(result)
        merged.append(row)

        statuses[result["census_match_status"]] += 1
        if reason:
            fallback_reasons[reason] += 1

    columns = original_columns + NEW_COLUMNS

    def save_csv(filename, rows):
        path = OUTPUT_DIR / filename
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        return path

    # Keep every MA filing in the master file.
    master_path = save_csv("ma_geocoded_all.csv", merged)

    ready = [
        row for row in merged
        if row["needs_zip_fallback"] == "false"
    ]
    fallback = [
        row for row in merged
        if row["needs_zip_fallback"] == "true"
    ]

    ready_path = save_csv("ma_tract_ready.csv", ready)
    fallback_path = save_csv("ma_zip_fallback.csv", fallback)

    submitted = len(results)
    matched = statuses["Match"]
    total = len(merged)

    summary = {
        "summary_created_at": datetime.now().astimezone().isoformat(),
        "benchmark": "Public_AR_Current",
        "vintage": "ACS2024_Current",
        "unit": "filing record; not unique organization",
        "total_ma_records": total,
        "submitted_records": submitted,
        "not_submitted_records": statuses["Not_Submitted"],
        "matched_records": matched,
        "no_match_records": statuses["No_Match"],
        "tie_records": statuses["Tie"],
        "ma_tract_ready_records": len(ready),
        "zip_fallback_records": len(fallback),
        "fallback_reasons": dict(fallback_reasons),
        "submitted_match_rate_pct": round(
            matched / submitted * 100, 4
        ) if submitted else None,
        "overall_ma_tract_coverage_pct": round(
            len(ready) / total * 100, 4
        ) if total else None,
        "result_files": [str(path) for path in RESULT_FILES],
    }

    summary_path = OUTPUT_DIR / "geocoding_summary.json"
    with summary_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)

    print(f"Total MA records preserved: {total:,}")
    print(f"Submitted: {submitted:,}")
    print(f"Match: {matched:,}")
    print(f"No_Match: {statuses['No_Match']:,}")
    print(f"Tie: {statuses['Tie']:,}")
    print(f"Not submitted: {statuses['Not_Submitted']:,}")
    print(f"\nMA tract ready: {len(ready):,}")
    print(f"Needs ZIP fallback: {len(fallback):,}")
    print(
        f"\nSubmitted match rate: "
        f"{summary['submitted_match_rate_pct']:.2f}%"
    )
    print(
        f"Overall MA tract coverage: "
        f"{summary['overall_ma_tract_coverage_pct']:.2f}%"
    )

    print("\nSaved:")
    for path in [
        master_path, ready_path, fallback_path, summary_path
    ]:
        print(path)


if __name__ == "__main__":
    main()