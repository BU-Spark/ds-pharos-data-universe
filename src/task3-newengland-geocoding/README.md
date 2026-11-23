# New England Filer Geocoding (Milestone 4)

Extends the Milestone 2 Massachusetts geocoding (`src/task1-ma-geocoding`) to all six New England states (MA, CT, RI, NH, VT, ME) and places every filing in a census tract. The output `ne_placement_org.csv` is the shared organization list for all three views.

## Method
1. **Extract and clean** (`01`, `02`): filer addresses from the 990/990-EZ and 990-PF headers; same cleaning and PO box rules as Milestone 2. `record_id` uses the same rule, so MA results from Milestone 2 are reused, not resubmitted.
2. **Census geocoding** (`03`–`05`): street addresses for the five new states in 3 batches, Benchmark `Public_AR_Current`, Vintage **`ACS2024_Current`**. Batches can be uploaded on the Census website or sent with `04`.
3. **Retry failed addresses** (`06`, `06b`, `07`): two retry rounds after cleaning unit numbers, spelled-out numbers and C/O lines. A retry match is accepted only if ZIP, state, house number, first street word and street type all agree.
4. **ZIP fallback** (`08`): records without a tract are placed by ZIP:
   - `zip_fallback_cluster`: the tract where that ZIP's geocoded organizations cluster
   - `zip_fallback_area`: if no geocoded organizations share the ZIP, the tract with the largest land overlap
   - `unplaced`: neither rule finds a tract

Every row keeps `placement_method` and `placement_precision` (`tract` / `zip_approx` / `none`), as the client asked.

## Results (tax years 2024–2025, filing records)
| State | Filings | Street-address match rate | Tract-level | Placed (incl. ZIP) |
|---|---:|---:|---:|---:|
| MA | 29,258 | 92.96% | 72.5% | 98.4% |
| CT | 12,839 | 94.78% | 71.7% | 97.3% |
| RI | 3,890 | 88.47% | 69.8% | 98.5% |
| NH | 5,946 | 92.65% | 58.1% | 95.8% |
| VT | 3,740 | 91.87% | 50.5% | 96.9% |
| ME | 5,501 | 91.91% | 49.9% | 94.0% |
| **Total** | **61,174** | **92.9%** | **67.4%** | **97.4%** |

- 46,287 organizations (one row per EIN), 97.5% placed.
- Street addresses match equally well in every state. Lower tract-level coverage in VT and ME comes from PO boxes (about half their filings).
- Retrying 3,144 failed addresses added only 68. Most failures are addresses missing from the Census database, not formatting problems.
- The cluster rule placed 492 more MA organizations than the Milestone 2 area rule (MA placement 96.2% → 98.4%), mostly PO-box-only ZIPs with no Census ZCTA.

## Inputs (put in `data/raw/`, from the team Drive or census.gov)
- `irs990_f9_p00_t00_header_2024_2025.csv`, `irs990pf_pf_p00_t00_header_2024_2025.csv` (client extracts)
- `tab20_zcta520_tract20_natl.txt`: 2020 ZCTA to Census Tract relationship file (census.gov, 2020 Relationship Files)
- `2024_gaz_tracts_09.txt`: 2024 Gazetteer, Connecticut census tracts
- Milestone 2 MA results: `data/outputs/ma_geocoding_result/ma_geocoded_all.csv`

## How to run
```bash
cd src/task3-newengland-geocoding
python 01_extract_ne_addresses.py
python 02_clean_ne_addresses.py
python 03_census_batches.py
python 04_submit_census_batches.py   # or upload batches on the Census website
python 05_merge_geocode_results.py
python 06_retry_batch.py             # upload retry batch to Census, then:
python 06b_retry_round2.py           # upload round 2 batch to Census, then:
python 07_apply_retry.py
python 08_zip_fallback.py
```
Outputs go to `data/outputs/ne_geocoding/`. Final files are in `placement/` and on the team Drive (`Data/outputs/ne_geocoding_result`).

## Outputs
- `placement/ne_placement_filing.csv`: one row per filing (EIN + tax_year + form_type), for Postgres
- `placement/ne_placement_org.csv`: one row per EIN, shared base for the views
- `placement/ne_placement_summary_*.csv`, `ne_placement_summary.json`: counts by state and method
- `retry/ne_retry_log.csv`: every retried address and why it was accepted or rejected

## Notes
- **Connecticut** uses 2022 planning-region county codes (110–190) in ACS 2022+. Geocode with Vintage `ACS2024_Current`; the 2020 ZCTA file's CT tracts are converted by 6-digit tract code.
- EIN + tax_year is not fully unique: 2 organizations filed both a 990 and a 990-PF in the same year.
- Rates count filing records unless noted. Filing addresses are HQ or mailing locations, not service areas.
- Keep EIN, ZIP and GEOID columns as strings.

### AI Usage
- AI-C: Used Claude to help write and debug the scripts for extraction, Census batches, retry rules and ZIP fallback, and to check outputs. I ran the Census batches, reviewed the results and made the method decisions.
