# View 3: Nonprofit mix in high-need vs. low-need areas (Milestone 4)

Which types of nonprofits exist in high-poverty vs. low-poverty areas of Massachusetts? Built on View 1 outputs so both views count the same organizations and use the same NTEE categories.

| File | What it is |
|---|---|
| `view3_nonprofit_mix.ipynb` | The notebook (Google Colab). Builds the need groups, mix and presence tables, charts and map. |

## Inputs (from Google Drive, `outputs/view1_density_by_type/`)
| Input | Comes from |
|---|---|
| `tracts_by_type.csv` | View 1: tract population, poverty, income, college flag and organizations by NTEE category |
| `towns_by_type.csv` | View 1: the same for the 351 MA cities and towns |

Organizations come from `ne_placement_org.csv` (New England placement) through View 1: 22,006 organizations placed in MA tracts.

## How to run (Google Colab)
1. Open the notebook and run the cells top to bottom.
2. When the Setup cell asks, upload `tracts_by_type.csv` and `towns_by_type.csv`.
3. The last cell downloads all outputs as one zip file.

Settings are in the Config cell (`NEED_VAR`, `SPLIT`, `LOW_POP`), the same as View 1.

## Method
- **Need groups:** areas with 500+ residents are split by poverty rate. High need = top quarter (tracts: 14.2%+), low need = bottom quarter (4.3% or less). Same need measure and cut-off as View 1.
- **Mix:** share of each NTEE category among organizations with an NTEE code.
- **Presence:** share of areas with at least one organization of each category. Pooled per-1,000 rates are not used for the main chart: a few downtown tracts with many registered headquarters (one Boston tract has 731 organizations) pull them up.
- **College areas** stay in, as in View 1; the notebook checks that results hold without them.

## Results (tracts, high need vs. low need)
| Category | Share of mix | Tracts with at least one |
|---|---:|---:|
| Human services | 26.4% vs. 17.7% | 64.3% vs. 70.4% |
| Health | 9.7% vs. 8.3% | 33.9% vs. 47.2% |
| Education | 12.6% vs. 18.6% | 47.2% vs. 72.6% |
| Recreation & sports | 4.3% vs. 11.0% | 24.6% vs. 50.5% |
| Environment & animals | 3.3% vs. 5.7% | 17.8% vs. 38.9% |

In high-need tracts, a larger share of nonprofits are human services, but high-need tracts are less likely to have any nonprofit of most types, including human services. Town-level differences are smaller because towns are large.

## Outputs (`view3_nonprofit_mix/`, on the shared Drive)
| File | Contents |
|---|---|
| `view3_tracts.csv`, `view3_towns.csv` | One row per area: need group, counts and share by category (for the combined map) |
| `view3_tracts.html` | Interactive map: need group and share of each category |
| `view3_mix_share_tracts.png`, `view3_mix_share_towns.png`, `view3_presence_tracts.png` | Charts |
| `view3_mix_summary_*.csv`, `view3_presence_summary_*.csv` | Summary tables |

## Limitations
- Organizations are placed at their filing address, not where they provide services.
- About a quarter have no NTEE code (similar share in high- and low-need tracts).
- Small nonprofits (990-N filers) and most churches don't file a 990.
- ACS estimates have margins of error, especially for small areas.

### AI Usage
- AI-C: Used Claude to help plan the analysis, draft the notebook code and check the outputs. I ran the notebook, reviewed the results and chose the presence measure after seeing the downtown outlier.
