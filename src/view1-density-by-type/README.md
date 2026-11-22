# View 1: Nonprofit density vs. need, by nonprofit type (Milestone 4)

This view updates the Milestone 3 density maps based on the client's feedback at the 2026-11-13 meeting. It shows where Massachusetts has many or few nonprofits relative to need (poverty). It breaks this down by type of nonprofit and shows results for both census tracts and towns.

| File | What it is |
|---|---|
| `view1_density_by_type.ipynb` | The notebook. It builds the tract and town tables, the desert classification and the maps. |
| `ntee_groups.py` | The NTEE category grouping, shared with View 3 (nonprofit mix) so both views use the same categories. |

## What changed from Milestone 3, and why

| Client decision | What the notebook does |
|---|---|
| Use **quarters** for the desert cut-off | A possible desert is an area in the top quarter for poverty **and** the bottom quarter for nonprofits per 1,000 residents. Over-concentration is the reverse. |
| Keep **poverty rate** as the need measure | `NEED_VAR = "poverty_rate_pct"`. Median household income is shown in the hover box. |
| **Flag** college areas, don't remove them | Areas where college and graduate students are at least 30% of the people in poverty are outlined. The poverty rate excluding students is shown alongside. |
| Break density down **by nonprofit type** | Nonprofits are grouped by NTEE category, and users can switch between types. An animal welfare group and a food pantry serve very different needs. |
| Show results **by town** as well as tract | Organizations are placed directly into the 351 Massachusetts cities and towns, and town population and poverty come straight from the ACS. |

## Inputs

These come from earlier work and are used as-is. None of the data files are in this repo; they are on the shared Drive.

| Input | Earlier work it comes from | By |
|---|---|---|
| `ma_tract_kpi1.csv` | ZIP fallback placement, ACS join and nonprofits per 1,000 residents (`task2_zip_fallback_acs_kpi1.py`) | Yunho Choi and Menahil Bakhat |
| `ma_org_tract_placement.csv` | Same step: one row per organization, with its tract, coordinates and ZIP | Yunho Choi and Menahil Bakhat |
| `ma_bmf_ntee.csv` (or `bmf_clean.parquet`) | NTEE codes from the IRS Business Master File, prepared during PF grant recipient EIN matching | Yeongchan Jang |

The notebook also downloads these directly from the Census Bureau:

- **ACS 2020–2024 5-year tables:** B14006 (poverty status by school enrollment) for tracts and towns. For towns only, it also pulls B01003 (population), B17001 (poverty status) and B19013 (median household income).
- **Cartographic boundary files:** Massachusetts tracts, county subdivisions (towns) and ZIP Code Tabulation Areas.

## How to run (Google Colab)

1. Add your Census API key to Colab Secrets as `CENSUS_API_KEY`, and turn on notebook access. The key is free from the Census Bureau. Never put it in the code.
2. Open the notebook and run the cells top to bottom.
3. When the Setup cell asks, upload `ma_tract_kpi1.csv`, `ma_org_tract_placement.csv` and `ma_bmf_ntee.csv`.
4. The last cell downloads all outputs as one zip file.

Change settings only in the Config cell: `SPLIT`, `LOW_POP`, `STUDENT_POVERTY_SHARE`, `SMALL_TOWN`, and the NTEE categories.

## Method

### NTEE categories

NTEE codes are grouped by their first letter:

| Category | NTEE letters |
|---|---|
| Human services | I, J, K, L, M, O, P |
| Health | E, F, G, H |
| Education | B |
| Arts & culture | A |
| Environment & animals | C, D |
| Recreation & sports | N |
| Religion | X |
| Community & philanthropy | S, T, W |
| Other | Q, R, U, V, Y, Z |

There is also a **People-serving** preset, which combines human services and health. About 26% of Massachusetts organizations have no NTEE code. They count toward **All nonprofits** only.

### Tracts

- Nonprofits per 1,000 residents are computed for every type.
- Tracts with fewer than 500 residents are left out of the classification.
- **Deserts are labeled only for All nonprofits and People-serving.** Once split by type, many tracts have zero organizations of that type: 31% of tracts for human services, and 60% for health. A desert label there would be unstable, since a neighboring tract may serve the area. So for single types, the tract map shows density only.

### Towns

**Placing organizations in towns:**
- Geocoded organizations are placed in the town whose boundary contains their address point.
- ZIP-fallback organizations are placed in the town that covers the largest part of their ZIP area.

**Town data:** population, poverty rate and median income are pulled from the ACS for county subdivisions directly, not added up from tracts.

**Desert labels:** every nonprofit type is classified at the town level, because town numbers are larger and more stable.

**Small towns:** towns under 5,000 residents get a note on the map, because having no organization of a given type is common in a small town, and organizations in nearby cities may serve these areas.

### College areas

ACS table B14006 splits the people in poverty by school enrollment. For each area, the notebook computes:
- the share of people in poverty who are college or graduate students
- the poverty rate excluding those students

An area is flagged when students are at least 30% of its people in poverty. The flag **does not mean high poverty**. It means students make up much of the poverty count, so the poverty rate excluding students should be read alongside.

Students living in dorms are not counted in poverty statistics, so the adjustment covers off-campus students.

### Census columns

Census columns are chosen by their labels rather than typed codes. The code stops if a label doesn't match, so the wrong column can't be used by mistake.

## Results (tax years 2024–2025, Massachusetts)

**Tracts (quarters):**

| | Deserts | Over-concentration | Nonprofits per 1,000 (deserts vs. over-concentration) |
|---|---|---|---|
| All nonprofits | 140 tracts | 127 tracts | 0.51 vs. 6.58 |
| People-serving | 122 tracts | 95 tracts | 0.01 vs. 1.56 |

**Towns, all nonprofits:**
- **28 possible deserts**, mostly older industrial cities: Lowell, Brockton, Lynn, New Bedford, Fall River, Lawrence, Chelsea and others.
- **Over-concentration** is mostly in wealthier suburbs: Andover, Needham, Wellesley, Concord and others.

**College areas:** 155 tracts and 10 towns are flagged, including Amherst, Hadley, Cambridge and Brookline. For example, in one Amherst tract the poverty rate is 62.6%, but 4.1% excluding students.

Boston, Springfield and Worcester are not deserts at the town level, because nonprofit headquarters cluster downtown. Their high-poverty neighborhoods do show up as deserts at the tract level, which is why the view shows both levels.

## Outputs (`view1_density_by_type/`, stored on the shared Drive)

| File | Contents |
|---|---|
| `view1_tracts.html`, `view1_towns.html` | Interactive maps with a layer menu by nonprofit type, hover details and a legend |
| `map_tract_deserts_all_vs_people_serving.png` | Static comparison map |
| `tracts_by_type.csv`, `towns_by_type.csv` | Counts, per-1,000 rates, groups and student measures by area |
| `org_tract_town.csv` | Each organization's EIN, category, tract and town (no names) |
| `desert_summary_tracts.csv`, `desert_summary_towns.csv` | Desert and over-concentration counts and cut-offs by filter |
| `density_by_type_tracts.csv`, `organizations_by_category.csv`, `filter_definitions.csv` | Supporting tables |

## Limitations

- Organizations are placed at their filing address (office or mailing location), not where they provide services.
- About a quarter of organizations have no NTEE code, so type-specific maps undercount.
- Very small nonprofits (990-N filers) and most churches don't file a 990, so they are missing from the data.
- Small towns and tracts can show zero organizations of a type even when they are served from nearby.
- ACS estimates have margins of error, especially for small areas.
- The tract map file is large (about 14 MB), because each layer stores its own copy of the boundaries. The combined interactive map will store boundaries once.
