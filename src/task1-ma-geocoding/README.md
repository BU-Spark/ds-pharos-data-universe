# MA Address Geocoding

Extracted Massachusetts addresses from IRS 990/990-EZ and 990-PF headers, cleaned address fields, flagged PO boxes, and geocoded street addresses.

## Method
- Preserved EINs, ZIPs, and source identifiers.
- Standardized capitalization and whitespace; flagged common PO box patterns.
- Ran three Census batches using `Public_AR_Current` / `ACS2024_Current`.
- Merged results by `record_id`, preserving all MA filing records.

## Results
- Total MA filing records: **29,258**
- PO box flagged: **6,503**
- Addresses submitted: **22,755**
- Matched with MA tract codes: **21,153**
- No match: **1,347**; Tie: **255**
- Submitted-address match rate: **92.96%**
- Overall MA filing tract coverage: **72.30%**

## Outputs
In `outputs/`:
- `ma_geocoded_all.csv`: all records and results.
- `ma_tract_ready.csv`: ACS-ready records; join using `tract_geoid`.
- `ma_zip_fallback.csv`: 8,105 records for Task 2 ZIP fallback using `zip5`.
- `geocoding_summary.json`: counts and settings.

Rates are per filing record, not unique organization. Addresses may be mailing locations rather than service areas. Keep EIN, ZIP, and tract codes as strings.

### AI Usage: 
- AI-C: Used ChatGPT to help generate code for address extraction, cleaning, Census batch preparation, and result merging. I ran the scripts and reviewed the outputs.
