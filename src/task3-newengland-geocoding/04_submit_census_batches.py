"""Step 4: submit each batch file to the Census batch geocoder and save the result.

Run this from your own Terminal (it needs internet access to geocoding.geo.census.gov).
Already-finished batches are skipped, so it is safe to rerun after a failure.
Each batch of 10,000 usually takes several minutes.

Manual alternative: upload each outputs/census_batches/ne_batch_XX.csv at
https://geocoding.geo.census.gov/geocoder/geographies/addressbatch?form
(Benchmark: Public_AR_Current, Vintage: ACS2024_Current) and save the result as
outputs/census_results/ne_batch_XX_result.csv
"""
import time

import requests

from config import BATCH_DIR, RESULT_DIR, CENSUS_BENCHMARK, CENSUS_VINTAGE

URL = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"


def main():
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    batches = sorted(BATCH_DIR.glob("ne_batch_*.csv"))
    if not batches:
        raise FileNotFoundError("No batch files. Run 03_census_batches.py first.")

    for batch in batches:
        out = RESULT_DIR / batch.name.replace(".csv", "_result.csv")
        if out.exists() and out.stat().st_size > 0:
            print(f"{batch.name}: result exists, skipping")
            continue

        for attempt in range(1, 4):
            print(f"{batch.name}: submitting (attempt {attempt}) ...", flush=True)
            t0 = time.time()
            try:
                with batch.open("rb") as f:
                    resp = requests.post(
                        URL,
                        files={"addressFile": (batch.name, f, "text/csv")},
                        data={"benchmark": CENSUS_BENCHMARK, "vintage": CENSUS_VINTAGE},
                        timeout=1800,
                    )
                resp.raise_for_status()
                out.write_bytes(resp.content)
                lines = resp.text.count("\n")
                print(f"  done in {time.time() - t0:.0f}s, {lines:,} rows -> {out.name}")
                break
            except Exception as e:  # network hiccups are common on large batches
                print(f"  failed: {e}")
                if attempt == 3:
                    raise
                time.sleep(30)


if __name__ == "__main__":
    main()
