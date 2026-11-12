# Enrichment view mockups (Milestone 3)

Three Massachusetts map views, proposed to the client for sign-off. They show what the combined IRS 990 + Census data can do.

| Notebook | What it makes |
|---|---|
| `nonprofit_density_maps.ipynb` | **Map 1:** registered nonprofits per 1,000 residents, by census tract.<br>**Map 2:** nonprofit density vs. need (poverty rate), with tracts grouped as possible nonprofit deserts, possible over-concentration, high need with many nonprofits, or other. |
| `grant_recipient_map.ipynb` | **Map 3:** grant dollars from MA-based private foundations, placed at the **recipient's** location (ZIP code) instead of the foundation's office. |

## Inputs

These notebooks build on earlier Milestone 2 work. The inputs below are results of that work, used as-is without changes. None of the data files are in this repo.

| Notebook | Input | Earlier work it comes from | By |
|---|---|---|---|
| Density maps | `ma_tract_kpi1.csv` | MA address geocoding (`ma_geocoded_all.csv`), then ZIP fallback placement, ACS join and nonprofits per 1,000 residents (`task2_zip_fallback_acs_kpi1.py`) | Yunho Choi and Menahil Bakhat |
| Grant map | `fuzzy_matches_filer_ma.csv` | Fuzzy matching of grant recipients (`src/fuzzy_matching/fuzzy_match.py --sample filer_ma`) | Yanaal Niyazi |
| Grant map | `pf_recipients_matched.parquet` | PF grant recipient EIN matching (`src/pf-recipient-matching/`) | Yeongchan Jang |
| Grant map (optional) | `bmf_clean.parquet` | PF grant recipient EIN matching. Only used to fill in city names for fuzzy-matched recipients. | Yeongchan Jang |

Census tract, ZIP code (ZCTA) and state boundary files are downloaded automatically from census.gov.

## How to run (Google Colab)

1. Open the notebook in Colab and run the cells top to bottom.
2. When the Setup cell asks, choose the input files from your computer.
3. The last cell downloads all outputs as one zip file.

To read from and save to Google Drive instead, set `UPLOAD_FROM_COMPUTER = False` in the Config cell.

## Method

**Density maps**
- Tracts with fewer than 500 residents are excluded (28 tracts), because a single nonprofit makes their rate jump.
- Map 1 colors tracts by quintile of nonprofits per 1,000 residents. The statewide rate is 3.05.
- Map 2 splits the remaining tracts into thirds on two measures: poverty rate and nonprofits per 1,000.
  - **Possible desert:** top third for poverty and bottom third for density.
  - **Possible over-concentration:** the reverse.
- The thirds are a proposal for the client to decide. `NEED_VAR` and `SPLIT` in the Config cell change the measure and the cut-off.

**Grant map**
- Uses grants from foundations whose 990-PF address is in MA. Rows set aside during EIN matching (individuals, foreign recipients, "see attached") are dropped.
- Fuzzy matches are joined on normalized name + state + ZIP, the same way the match-rate table does. They are only applied to grants that EIN matching left unmatched or ambiguous, and they add 469 grants.
- **Recipient location:** the IRS-registered ZIP of the matched EIN. If the EIN has no registered ZIP, the ZIP on the grant record is used instead.
- The map uses total dollars per recipient ZIP on a log scale.

## Results (tax years 2024–2025)

**Density**
- Possible deserts: 227 tracts, about 1.0M residents, 661 nonprofits.
- Possible over-concentration: 215 tracts, about 1.0M residents, 5,800 nonprofits (about 9× more for a similar population).
- Poverty rate and density have a Spearman correlation of −0.17.

**Grants**
- 69,358 matched grants from MA-based foundations, totaling $2.74B.
- 51.7% of the dollars go to recipients in MA. After MA, the top states are NY (9.0%), CA (6.3%) and DC (5.1%).
- Within MA, Boston receives 40.1% of in-state dollars and Cambridge 8.6%.

## Limitations

- Nonprofits and grant recipients are placed at their office or mailing address, not where they provide services.
- In student-heavy tracts, ACS poverty rates are high because of students. These tracts are kept and noted, not removed.
- Some large recipients re-grant the money rather than use it, such as donor-advised fund sponsors, community foundations and a foundation's own grant-making arm.
- Some foundations list the same recipient with the same amount on more than one line of the same return. At $100K and up, this is 2.4% of matched dollars. These lines are kept as reported.
