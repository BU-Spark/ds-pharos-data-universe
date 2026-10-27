# Milestone 2 · Task 3 — 990-PF Grant Recipient EIN Matching

Pharos Intelligence: Extend the Data Universe (DS539, Fall 2026)

## What Task 3 does

Private foundations report every grant they make on Form 990-PF (Part XV), and Pharos stores those grants in the
table `pf_p14_t03_supplementaryinformation`. Each row is one grant from a foundation (the **filer**) to a
**recipient**. The filer's EIN is always present, but the recipient's EIN (`rcpnt_ein`) is often blank, misspelled,
a word such as `INDIVIDUAL`, or belongs to a different organization.

Task 3 answers, for every grant row: **who received this money, identified by a verified EIN?** It

1. classifies each recipient as an organization, government, individual, foreign, or unspecified recipient;
2. checks every reported recipient EIN against the IRS Exempt Organizations Business Master File (BMF),
   Publication 78, the IRS auto-revocation list, and our own 990 / 990-PF filers;
3. fills blank or bad EINs where the recipient's name matches exactly one known organization in the same ZIP code
   or city;
4. reports match rates, overall and for Massachusetts, and hands the rest to Task 4 (fuzzy matching).

A recipient EIN links a grant to the recipient's own 990 data, address, and Census tract. That is how grant money
can be placed where it is used ("area of impact") instead of at the foundation's headquarters.

Matching runs on the **full national dataset**. The BMF and Pub 78 are national and many grants cross state lines, so
filtering to Massachusetts first would drop real matches. Massachusetts is a flag (`recipient_in_ma`); the MA filter
is applied later, at the ACS join.

## Results at a glance

| | Overall | Recipients in MA |
| --- | --- | --- |
| Grant rows | 2,224,978 | 103,081 |
| Set aside (individual, foreign, unspecified, no name) | 194,292 (8.7%) | 5,188 (5.0%) |
| **Matched to a recipient EIN, excluding set-aside rows** | **78.7%** (1,598,326) | **81.2%** (79,530) |
| Matched, as a share of all rows | 71.8% | 77.2% |
| Not matched, handed to Task 4 | 432,360 | 18,363 |

Grants made by Massachusetts foundations (`filer_in_ma`, 90,906 rows) match at 81.0%.

- **Almost all matches come from reported EINs that pass verification (75.8 of the 78.7 points).** Exact name
  matching adds 0.6 points; closing the remaining gap is Task 4's job.
- **Comparison with Curt's ~80%:** `rcpnt_ein` is filled in 80.6% of rows, but only 72.3% hold a usable 9-digit EIN
  (the rest are blank or words like `INDIVIDUAL`), and 70.6% hold an EIN that exists in an IRS list or our filers.
  About 98% of reported 9-digit EINs are therefore real. Our 78.7% is a *verified* rate, not a fill rate.
- **Spot check:** 20 random rows per `match_method` (288 rows) were judged against IRS lists and, where possible, the
  organization's own published EIN. `ein_verified` (96% of all matches) was 20 of 20 correct. The errors found are in
  small buckets described under [Limitations](#limitations-and-handoff-to-task-4).
- **Report row rates first.** Dollar rates (79.6% overall) swing on a few huge rows: pharmaceutical
  patient-assistance foundations report billions in donated drugs as single "INDIVIDUAL" grants (the 10 largest
  individual grants total $15.0B of $16.2B).

## Input data

### Pharos extracts (tax years 2024–2025)

Expected folder layout (on the team Drive):

```
DATA_DIR/
├── irs990_2024_2025/
│   └── irs990_f9_p00_t00_header_2024_2025.csv
└── irs990pf_2024_2025/
    ├── irs990pf_pf_p00_t00_header_2024_2025.csv
    └── irs990pf_pf_p14_t03_supplementaryinformation_2024_2025.csv
```

| File | Rows | What we use it for |
| --- | --- | --- |
| `pf_p14_t03_supplementaryinformation` (990-PF grants paid) | 2,224,978 grants from 97,143 foundations | **The rows being matched.** Recipient EIN, name (two lines), person-name field, address, recipient status text, amount. |
| `f9_p00_t00_header` (990 / 990-EZ header) | 766,551 filings, 581,496 EINs | **Reference names and addresses.** Many recipients file a 990 themselves; matching to them links grants back to the Pharos 990 base. |
| `pf_p00_t00_header` (990-PF header) | 190,674 filings, 126,428 EINs | Foundation state (for the `filer_in_ma` slice) and foundation names as references. |

The other seven Pharos extracts are not needed for Task 3.

### IRS reference files (downloaded by the notebook)

| File | Source | What we use it for |
| --- | --- | --- |
| EO Business Master File, regional files `eo1.csv`–`eo4.csv` (~1.98M organizations, posted 2026-10-13) | [irs.gov EO BMF](https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf) | **Main reference.** Every organization the IRS currently recognizes as tax-exempt, with name, secondary name, and address. |
| Publication 78 data | [irs.gov bulk downloads](https://www.irs.gov/charities-non-profits/tax-exempt-organization-search-bulk-data-downloads) | Organizations eligible for deductible contributions; fills gaps in the BMF. |
| Auto-revocation list | same page | Organizations whose exemption was revoked (see below). |

The files are cached in `task3_outputs/reference/` and their download dates are logged in `download_log.json`.

### Why the auto-revocation list is included

An organization that fails to file a 990 for three consecutive years loses its tax-exempt status automatically.
The IRS then **removes it from the BMF but lists it on the auto-revocation list**, and its EIN stays valid.

The BMF is a current snapshot, while the grants are from 2024–2025. A recipient that received a grant and then lost
its status (often a small organization that has since closed) is missing from the BMF even though the foundation
reported its EIN correctly. Without the revocation list, those EINs would look like typos.

The list also exposes the opposite case: a filer types a revoked organization's EIN by mistake. The notebook
therefore compares the recipient name with the name on the revocation list. If the names disagree, the reported EIN
is treated as wrong and the row is re-matched by name.

## How the notebook works

`task3_pf_recipient_matching.ipynb`, run top to bottom. Only the **Config** cell needs editing.

1. **Setup.** Mounts Google Drive, installs `rapidfuzz` and `pyarrow`, and finds the three Pharos files. It looks
   first at `DATA_DIR`, then anywhere under `DATA_DIR`, then anywhere under `MyDrive`.
2. **Normalization helpers.** The same cleanup is applied to grant rows and every reference source, so keys line
   up:
   - **Names:** remove accents, upper-case, drop `C/O …` / `ATTN …`, `&` → `AND`, drop punctuation, a leading `THE`
     and legal suffixes (`INC`, `CORP`, `LLC`, …).
   - **Cities:** the same, plus `ST`/`MT`/`FT` → `SAINT`/`MOUNT`/`FORT`.
   - **ZIP:** first 5 digits, restoring a dropped leading zero.
   - **Two-line names:** joined correctly. Line 1 is often cut at 35 characters; line 2 may repeat the full name,
     continue mid-word (`…Associatio` + `n Inc`), or follow a `D/B/A`.
3. **Download and clean IRS references** (steps 1–2): BMF, Pub 78, and the revocation list.
4. **Load the Pharos tables** (step 3). Every column is read as text, so EINs keep their leading zeros.
5. **Build one reference name index** (step 4). Every known name for every EIN goes into one table: BMF legal and
   secondary names, Pub 78, 990 names and DBAs, and 990-PF names. Each entry has its city, state, and ZIP.
6. **Clean reported EINs** (step 5). Remove hyphens, pad 8-digit values, mark words (`INDIVIDUAL`, `FOREIGN`,
   `GOVERNMENT`) and placeholders (`000000000`, `123456789`).
7. **Classify recipients** (step 6). The first matching rule wins:
   - **foreign:** EIN word or a country code;
   - **individual:** EIN word, status `I`, or a name only in the person field with no EIN and nothing
     organization-like;
   - **government:** EIN word or status `GOV`;
   - **unspecified:** `SEE ATTACHED`, `VARIOUS`, …;
   - **unidentifiable:** no name and no EIN;
   - **organization:** everything else.

   Note: a name in the person-name field does *not* by itself mean an individual. 143,881 rows with a valid EIN
   hold organization names there (e.g. `MASSACHUSETTS GENERAL HOSPITAL`).
8. **Verify reported EINs** (step 7). Look the EIN up in each reference, then score the recipient name against the
   names on file (`token_set_ratio`, agreement threshold 60).
9. **Exact name matching** (step 8). This runs for rows with no usable EIN, an EIN that fails verification, or a
   name that disagrees. Every reading of the two name lines is tried, first on name + ZIP5, then on name + city +
   state. A match counts only when **exactly one EIN** comes back; two or more is `ambiguous`.
10. **Decide** (step 9). The rules in the table below set `match_method` and `matched_ein`. This step also attaches
    the matched organization's own address (BMF first, then 990 / 990-PF header, then Pub 78) and sets the MA flag.
11. **Report and save** (steps 10–12): match-rate tables, output files, and a spot-check sample.

### Running it

1. Upload the two Pharos folders shown above to Google Drive.
2. Open the notebook in Colab and set `DATA_DIR` in the Config cell to the folder that contains them.
3. Choose **Runtime → Run all**. The first run downloads the IRS files; later runs reuse the cache.
4. Outputs are written to `task3_outputs/`, next to the data folders, and overwrite the previous run.

## `match_method` reference

Each grant row gets exactly one `match_method`. Rows marked "yes" count as matched and carry a `matched_ein`.

| `match_method` | Matched? | Rows | Meaning |
| --- | --- | --- | --- |
| `ein_verified` | yes | 1,539,609 | Reported EIN is in a reference and the recipient name agrees. |
| `ein_name_disagrees` | yes, flagged | 31,707 | Reported EIN is in a reference but the name disagrees. These are mostly acronyms and sub-units (`MOCSA`, `NYU SCHOOL OF MEDICINE` under NYU Langone). A listed EIN is never overwritten; any other exact-match EIN goes to `alt_ein`. |
| `ein_government_likely` | yes, flagged | 10,770 | Reported EIN is in no list but has the `XX-60xxxxx` shape used by state and local government units (state universities, school districts, cities), which are not in the BMF. Kept as reported. |
| `ein_revoked` | yes, flagged | 4,526 | Reported EIN is only on the revocation list, and the recipient name agrees with the name there. |
| `ein_unlisted_kept` | yes, flagged | 845 | Reported 9-digit EIN is in no list, and an exact name match points to an unrelated EIN. The reported EIN is kept, because public universities are often right here (Ohio University, Oregon State). The other EIN goes to `alt_ein`. |
| `ein_self_grant` | yes, flagged | 114 | Recipient EIN and name are the foundation's own (e.g. its own scholarship fund). |
| `ein_corrected_name_zip` / `ein_corrected_name_city` | yes | 41 | Reported EIN was replaced by the EIN an exact name match found. This happens when the reported EIN is the foundation's own, is revoked under a different name, or differs by at most 2 digits (a typo, e.g. `870212468` → `870212460`). Never applied to government recipients. |
| `ein_no_name` | yes | 39 | Reported EIN is in a reference, but there is no recipient name to compare. |
| `name_zip` | yes | 9,194 | No usable EIN; the exact name matched exactly one EIN in the same ZIP. |
| `name_city` | yes | 1,481 | No usable EIN; the exact name matched exactly one EIN in the same city and state. |
| `gov_name_review` | no → Task 4 | 2,221 | The filer marked the recipient as government, and an exact name match found one EIN. Governments are mostly not in the BMF, so that EIN is often a different same-name organization (`CITY OF OLYMPIA` matched a small 501(c)(4) of that name). It is kept as a candidate in `alt_ein`. |
| `ambiguous` | no → Task 4 | 3,153 | The exact name matched 2 or more EINs; up to five are in `ambiguous_candidates`. |
| `unmatched` | no → Task 4 | 426,986 | Nothing found. |
| `set_aside` | excluded | 194,292 | Individual, foreign, unspecified, or unidentifiable recipient; left out of the match-rate denominator. |

Recipient classes over all rows:

| Class | Rows | Share |
| --- | --- | --- |
| organization | 1,990,085 | 89.4% |
| individual | 159,533 | 7.2% |
| government (kept in the denominator) | 40,601 | 1.8% |
| foreign | 31,108 | 1.4% |
| unspecified | 2,939 | 0.1% |
| unidentifiable | 712 | <0.1% |

## Output files

All outputs are written to `task3_outputs/` on the team Drive. They are not stored in this repository.

| File | Contents | Used by |
| --- | --- | --- |
| `pf_recipients_matched.parquet` | All 2,224,978 grant rows with the columns below | ETL; Tasks 1–2 (recipient locations) |
| `pf_recipients_for_fuzzy.parquet` | The 432,360 rows with `match_method` = `unmatched`, `ambiguous`, or `gov_name_review` | **Task 4 input** |
| `reference_name_index.parquet` | `ein, name_norm, city_norm, state, zip5, source` for every known EIN | **Task 4 candidate pool** |
| `bmf_clean.parquet`, `pub78_clean.parquet` | Cleaned IRS references | Anyone |
| `match_rates.csv` | Rows, dollars, and percentages by `match_method` for `overall`, `recipient_in_ma`, `filer_in_ma` | Report |
| `match_benchmarks.csv` | Fill rate vs. usable vs. verified vs. matched, for the comparison with Curt's ~80% | Report |
| `recipient_classes.csv` | Rows and dollars by recipient class and reason | Report |
| `spot_check_sample.csv` | 20 random rows per `match_method`, with empty `reviewer_ok` / `reviewer_note` columns | Manual review |
| `reference/` | Cached IRS downloads and `download_log.json` | Re-runs |

Main columns of `pf_recipients_matched.parquet`:

| Column | Meaning |
| --- | --- |
| `filer_ein`, `taxyear`, `line_number` | **Key of a grant row.** Unique together; `line_number` alone repeats across filings. |
| `row_id` | Internal row number from this run. Do not use it as a join key. |
| `rcp_name1`, `rcp_name2`, `rcp_person`, `rcp_city`, `rcp_state`, `rcp_zip`, `amount`, `purpose` | Original grant fields. |
| `rcp_name_full`, `rcp_name_norm` | Recipient name after joining the two lines, and its normalized form. |
| `name_from_person_field` | The name was taken from the person-name field. |
| `name_maybe_truncated` | Name line 1 is exactly 35 or 75 characters with nothing on line 2, so it was probably cut off. |
| `recipient_class`, `class_reason` | Classification and the rule that set it. |
| `ein_raw`, `ein_form`, `ein_clean` | Reported EIN as typed, its form (`valid9`, `blank`, `word_INDIVIDUAL`, …), and the cleaned 9-digit value. |
| `ein_status`, `ein_in_*`, `ein_name_score` | Where the reported EIN was found, and how well the name agrees (0–100). |
| `exact_ein`, `exact_pass`, `ein_digit_diff` | Result of exact name matching, and how many digits it differs from the reported EIN. |
| `match_method`, `is_matched`, **`matched_ein`** | Final decision and the recipient EIN to use. |
| `alt_ein`, `ambiguous_candidates` | Other candidate EINs kept for review. |
| `matched_street`, `matched_city`, `matched_state`, `matched_zip5`, `matched_addr_source` | The matched organization's own address, for geocoding. |
| `recipient_in_ma`, `ma_flag_source` | Recipient is in Massachusetts. The flag uses the reported state, else the ZIP (MA ZIP3 010–027 and 055), else the matched organization's address. |
| `filer_state` | The foundation's state. |

## Limitations and handoff to Task 4

The matched total rests mostly on reported EINs, which the spot check supports. The known errors sit in small
buckets, together under 0.5% of rows. Each one below ends with what Task 4 should do.

- **Exact name matching recovers little.** It filled 10,675 rows that had no usable EIN, while 432,360 remain
  unmatched, because it requires an identical normalized name. Most misses are acronyms, chapter names (`JDRF NEBRASKA IOWA CHAPTER`), or
  ZIP differences (PO box vs. street address).
  → *Task 4:* start from `pf_recipients_for_fuzzy.parquet` and `reference_name_index.parquet`. Prefix-match rows
  flagged `name_maybe_truncated`. Reuse `ambiguous_candidates` instead of searching from scratch.
- **`gov_name_review` (2,221) is conservative.** In the spot check, about half of the `alt_ein` candidates were
  right: filers often mark nonprofits (a volunteer ambulance, a private school, a school foundation) as GOVERNMENT.
  The other half were same-name entities, not the public body.
  → *Task 4:* accept `alt_ein` when the recipient is plainly a nonprofit; leave public bodies unmatched.
- **`ein_revoked` (4,526) is the weakest matched bucket.** Both checkable sample rows were wrong. `GBH` and
  `UNIVERSITY OF MONTANA` carry EINs of revoked organizations with the same name; WGBH is 04-2104397 and the
  university is 81-6001713. Name comparison moved 241 rows out of this bucket but cannot catch a same-name entity.
  → *Task 4 and analysis:* treat as low confidence; a fuzzy match to a BMF organization should override it.
- **`ein_unlisted_kept` (845) is right for public universities but not always for nonprofits.** 2 of 20 sample
  rows were wrong: Florida Atlantic University Foundation's EIN is 59-0917284 (its `alt_ein`), not the reported one.
  → *Task 4:* when `alt_ein` is a BMF organization whose name contains `FOUNDATION`, prefer `alt_ein`.
- **A student's name before a university name** (`CARLY BENNETT INDIANA UNIVERSITY`) exact-matched a different
  IU-named entity, not Indiana University (35-6001673). These are scholarship grants paid through the university.
- **The `XX-60` rule mislabels some churches as government** (e.g. `PORT CLYDE BAPTIST CHURCH`). Only the class
  label is wrong; the kept EIN is the reported one.
- **The BMF is a current snapshot** (posted 2026-10-13), while grants are from 2024–2025. Organizations that closed
  since then fall to the revocation list or to unmatched.
- **Validation is limited.** It consists of the 288-row spot check plus a 44-case synthetic test suite; there is no
  hand-labeled ground truth. The spot check's "likely" judgments are based on the data alone, not on an outside
  lookup.

## Files in this folder

| File | Description |
| --- | --- |
| `task3_pf_recipient_matching.ipynb` | Matching pipeline |
| `task3_explore_outputs.ipynb` | Loads the output parquet files for browsing |
| `results/match_rates.csv`, `results/match_benchmarks.csv`, `results/recipient_classes.csv` | Summary tables from the latest run |
