"""
Step 4 (Milestone 1): pull ACS 5-year indicators for every census tract in a county.

Needs a free Census API key, set as an environment variable (never paste it into the code):
    export CENSUS_API_KEY=your_key            (Mac/Linux)
    os.environ['CENSUS_API_KEY'] = '...'      (in Colab, or use Colab Secrets)

Usage:
    python src/04_acs_pull.py                         # Suffolk County, MA (default)
    python src/04_acs_pull.py --state 25 --county '*' # every tract in Massachusetts

Output: outputs/acs_<state>_<county>_tracts.csv
"""
import argparse
import os
import sys

import pandas as pd
import requests

from config import out

parser = argparse.ArgumentParser()
parser.add_argument("--year", type=int, default=2024, help="ACS 5-year release (2024 = 2020-2024)")
parser.add_argument("--state", default="25", help="state FIPS code (25 = Massachusetts)")
parser.add_argument("--county", default="025", help="county FIPS code, or '*' for all (025 = Suffolk)")
args = parser.parse_args()

CENSUS_KEY = os.environ.get("CENSUS_API_KEY")
if not CENSUS_KEY:
    sys.exit("Set the CENSUS_API_KEY environment variable first (see the top of this file).")

# ACS variable -> readable name. The table ID is the part before the underscore.
VARS = {
    "B01003_001E": "population",
    "B19013_001E": "median_household_income",
    "B17001_001E": "poverty_universe",          # people whose poverty status is known
    "B17001_002E": "below_poverty",
    "B23025_003E": "civilian_labor_force",
    "B23025_005E": "unemployed",
    "B15003_001E": "pop_25_plus",
    "B15003_022E": "bachelors",
    "B15003_023E": "masters",
    "B15003_024E": "professional_degree",
    "B15003_025E": "doctorate",
    "B01002_001E": "median_age",
    "B09001_001E": "pop_under_18",
    "B03002_001E": "race_total",
    "B03002_003E": "white_non_hispanic",
    "B03002_004E": "black_non_hispanic",
    "B03002_006E": "asian_non_hispanic",
    "B03002_012E": "hispanic_any_race",
    "B25070_001E": "renter_households",
    "B25070_007E": "rent_30_to_35_pct",
    "B25070_008E": "rent_35_to_40_pct",
    "B25070_009E": "rent_40_to_50_pct",
    "B25070_010E": "rent_50_pct_plus",
    "B25070_011E": "rent_not_computed",
}

url = f"https://api.census.gov/data/{args.year}/acs/acs5"
params = {"get": "NAME," + ",".join(VARS), "for": "tract:*",
          "in": f"state:{args.state} county:{args.county}", "key": CENSUS_KEY}
resp = requests.get(url, params=params, timeout=120)
if not resp.headers.get("content-type", "").startswith("application/json"):
    sys.exit("The Census API did not return data. Check that your key is set and activated.\n\n"
             + resp.text[:300])

data = resp.json()
raw = pd.DataFrame(data[1:], columns=data[0]).rename(columns=VARS)

# 11-digit tract ID: 2-digit state + 3-digit county + 6-digit tract. This is the join key.
raw["geoid"] = raw["state"] + raw["county"] + raw["tract"]

# Counts arrive as text. The Census uses large negative codes (such as -666666666)
# to mean "no estimate", so anything negative becomes missing.
num = raw[list(VARS.values())].apply(pd.to_numeric, errors="coerce")
num = num.where(num >= 0)


def pct(part, whole):
    """Percent, missing when the denominator is zero."""
    return (part / whole.where(whole > 0) * 100).round(1)


rent_burdened = num[["rent_30_to_35_pct", "rent_35_to_40_pct", "rent_40_to_50_pct", "rent_50_pct_plus"]].sum(axis=1)
college = num[["bachelors", "masters", "professional_degree", "doctorate"]].sum(axis=1)

tracts = pd.DataFrame({
    "geoid": raw["geoid"],
    "tract_name": raw["NAME"],
    "population": num["population"],
    "median_household_income": num["median_household_income"],
    "poverty_rate_pct": pct(num["below_poverty"], num["poverty_universe"]),
    "unemployment_rate_pct": pct(num["unemployed"], num["civilian_labor_force"]),
    "bachelors_or_higher_pct": pct(college, num["pop_25_plus"]),
    "median_age": num["median_age"],
    "under_18_pct": pct(num["pop_under_18"], num["population"]),
    "white_non_hispanic_pct": pct(num["white_non_hispanic"], num["race_total"]),
    "black_non_hispanic_pct": pct(num["black_non_hispanic"], num["race_total"]),
    "asian_non_hispanic_pct": pct(num["asian_non_hispanic"], num["race_total"]),
    "hispanic_pct": pct(num["hispanic_any_race"], num["race_total"]),
    "rent_burdened_pct": pct(rent_burdened, num["renter_households"] - num["rent_not_computed"]),
})

county_label = "all" if args.county == "*" else args.county
path = out(f"acs_{args.state}_{county_label}_tracts.csv")
tracts.to_csv(path, index=False)

print(f"{len(tracts)} tracts pulled for state {args.state}, county {args.county}, "
      f"ACS {args.year - 4}-{args.year}")
print(f"Total population: {int(tracts['population'].sum()):,}")
print("\nMissing values per indicator (tracts with no estimate):")
print(tracts.isna().sum()[2:].to_string())
print("\nSummary across tracts:")
print(tracts.describe().T[["min", "50%", "max"]].round(1).to_string())
print(f"\nSaved {path}")
