"""
Task 2 (Milestone 2): ZIP fallback placement, statewide ACS join, KPI 1.

Input:  ma_geocoded_all.csv (output of the geocoding step; all MA 990/990-EZ/990-PF filing records)
Output: task2_outputs/ (org placement, tract KPI 1, county KPI 1, ACS pull, spot-check map + sheet, summary JSON)

KPI 1 = registered nonprofits (unique EINs) per 1,000 residents, per census tract.
ZIP fallback: ZIP = ZCTA, assigned to the MA tract with the largest land overlap
(Census 2020 ZCTA-to-tract relationship file).

Census API key: set the CENSUS_API_KEY environment variable, or add it to Colab Secrets
under the name CENSUS_API_KEY. Never commit the key.
"""
import io, os, glob, json, requests
import numpy as np
import pandas as pd
import geopandas as gpd
import folium


def get_census_key():
    key = os.environ.get("CENSUS_API_KEY", "")
    if not key:
        try:
            from google.colab import userdata
            key = userdata.get("CENSUS_API_KEY") or ""
        except Exception:
            pass
    return key


CENSUS_API_KEY = get_census_key()
ACS_YEARS_TO_TRY = [2024, 2023]
STATE_FIPS = "25"
LOW_POP_THRESHOLD = 500
SPOT_CHECK_N = 20
RANDOM_SEED = 539
OUT_DIR = "task2_outputs"
os.makedirs(OUT_DIR, exist_ok=True)

found = sorted(glob.glob("**/*ma_geocoded_all*.csv", recursive=True)) + \
        sorted(glob.glob("/content/**/*ma_geocoded_all*.csv", recursive=True))
if not found:
    raise FileNotFoundError("ma_geocoded_all.csv not found; place it in the working directory")
GEOCODED_PATH = found[0]
print("Reading:", GEOCODED_PATH)

recs = pd.read_csv(GEOCODED_PATH, dtype=str, keep_default_na=False, na_values=[""])


def clean_code(s, width):
    s = s.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    return s.where(s.isna(), s.str.zfill(width))


recs["ein"] = clean_code(recs["ein"], 9)
recs["zip5"] = clean_code(recs["zip5"], 5)
recs["tract_geoid"] = clean_code(recs["tract_geoid"], 11)
recs["tax_year"] = pd.to_numeric(recs["tax_year"], errors="coerce")
recs["latitude"] = pd.to_numeric(recs["latitude"], errors="coerce")
recs["longitude"] = pd.to_numeric(recs["longitude"], errors="coerce")
recs["is_geocoded"] = (recs["census_match_status"].eq("Match") & recs["tract_geoid"].notna()).astype(bool)
print(f"Filing records: {len(recs):,} | unique EINs: {recs['ein'].nunique():,}")

ACS_VARS = {
    "B01003_001E": "population", "B19013_001E": "median_household_income", "B01002_001E": "median_age",
    "B17001_001E": "pov_universe", "B17001_002E": "pov_below",
    "B23025_003E": "civ_labor_force", "B23025_005E": "unemployed",
    "B15003_001E": "edu_universe", "B15003_022E": "edu_ba", "B15003_023E": "edu_ma",
    "B15003_024E": "edu_prof", "B15003_025E": "edu_phd",
    "B03002_001E": "race_universe", "B03002_003E": "white_nh", "B03002_004E": "black_nh",
    "B03002_006E": "asian_nh", "B03002_012E": "hispanic",
    "B25070_001E": "rent_universe", "B25070_007E": "rent_30_35", "B25070_008E": "rent_35_40",
    "B25070_009E": "rent_40_50", "B25070_010E": "rent_50_plus", "B25070_011E": "rent_not_computed",
    "B01001_003E": "m_u5", "B01001_004E": "m_5_9", "B01001_005E": "m_10_14", "B01001_006E": "m_15_17",
    "B01001_027E": "f_u5", "B01001_028E": "f_5_9", "B01001_029E": "f_10_14", "B01001_030E": "f_15_17",
}


def fetch_acs(year):
    url = (f"https://api.census.gov/data/{year}/acs/acs5?get=NAME,{','.join(ACS_VARS)}"
           f"&for=tract:*&in=state:{STATE_FIPS}&in=county:*")
    if CENSUS_API_KEY:
        url += f"&key={CENSUS_API_KEY}"
    r = requests.get(url, timeout=120)
    if r.status_code != 200 or not r.text.lstrip().startswith("["):
        raise ValueError(f"HTTP {r.status_code}: {r.text[:300]}")
    rows = r.json()
    return pd.DataFrame(rows[1:], columns=rows[0])


raw = None
for yr in ACS_YEARS_TO_TRY:
    try:
        raw = fetch_acs(yr)
        ACS_YEAR = yr
        print(f"Pulled ACS 5-year {yr-4}-{yr}: {len(raw):,} tracts")
        break
    except Exception as e:
        print(f"ACS {yr} unavailable ({e}); trying next")
if raw is None:
    raise RuntimeError("Could not pull ACS")

a = raw.rename(columns=ACS_VARS)
a["geoid"] = a["state"] + a["county"] + a["tract"]
num = list(ACS_VARS.values())
a[num] = a[num].apply(pd.to_numeric, errors="coerce")
a[num] = a[num].mask(a[num] < -100000)
pct = lambda n, d: (100 * n / d.replace(0, np.nan)).round(2)
acs = pd.DataFrame({
    "geoid": a["geoid"], "tract_name": a["NAME"], "county_fips": a["state"] + a["county"],
    "population": a["population"], "median_household_income": a["median_household_income"],
    "poverty_rate_pct": pct(a["pov_below"], a["pov_universe"]),
    "unemployment_rate_pct": pct(a["unemployed"], a["civ_labor_force"]),
    "bachelors_or_higher_pct": pct(a[["edu_ba", "edu_ma", "edu_prof", "edu_phd"]].sum(axis=1, min_count=1), a["edu_universe"]),
    "median_age": a["median_age"],
    "under_18_pct": pct(a[["m_u5", "m_5_9", "m_10_14", "m_15_17", "f_u5", "f_5_9", "f_10_14", "f_15_17"]].sum(axis=1, min_count=1), a["population"]),
    "white_non_hispanic_pct": pct(a["white_nh"], a["race_universe"]),
    "black_non_hispanic_pct": pct(a["black_nh"], a["race_universe"]),
    "asian_non_hispanic_pct": pct(a["asian_nh"], a["race_universe"]),
    "hispanic_pct": pct(a["hispanic"], a["race_universe"]),
    "rent_burdened_pct": pct(a[["rent_30_35", "rent_35_40", "rent_40_50", "rent_50_plus"]].sum(axis=1, min_count=1),
                             a["rent_universe"] - a["rent_not_computed"]),
})
print(f"{acs['county_fips'].nunique()} counties, {acs['population'].sum():,.0f} residents")

REL_URL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_tract20_natl.txt"
r = requests.get(REL_URL, timeout=300)
r.raise_for_status()
rel = pd.read_csv(io.StringIO(r.content.decode("utf-8-sig")), sep="|", dtype=str)
rel = rel[["GEOID_ZCTA5_20", "GEOID_TRACT_20", "AREALAND_PART"]].dropna(subset=["GEOID_ZCTA5_20"])
rel = rel[rel["GEOID_TRACT_20"].str.startswith(STATE_FIPS)].copy()
rel["AREALAND_PART"] = pd.to_numeric(rel["AREALAND_PART"], errors="coerce").fillna(0)
rel["zcta_overlap_share"] = (rel["AREALAND_PART"] /
    rel.groupby("GEOID_ZCTA5_20")["AREALAND_PART"].transform("sum").replace(0, np.nan)).round(4)
rel["n_tracts_in_zcta"] = rel.groupby("GEOID_ZCTA5_20")["GEOID_TRACT_20"].transform("nunique")
zcta_lookup = (rel.sort_values(["GEOID_ZCTA5_20", "AREALAND_PART"], ascending=[True, False])
                  .drop_duplicates("GEOID_ZCTA5_20")
                  .rename(columns={"GEOID_ZCTA5_20": "zcta", "GEOID_TRACT_20": "zip_tract_geoid"})
                  [["zcta", "zip_tract_geoid", "zcta_overlap_share", "n_tracts_in_zcta"]])
print(f"MA ZCTAs in lookup: {len(zcta_lookup):,}")

r_ = recs.sort_values(["ein", "is_geocoded", "tax_year"], ascending=[True, False, False])
orgs = r_.drop_duplicates("ein").copy()
orgs["n_filings"] = orgs["ein"].map(recs.groupby("ein").size())
orgs["had_both_geocode_and_fallback"] = orgs["ein"].map(
    recs.groupby("ein")["is_geocoded"].agg(lambda s: bool(s.any() and not s.all())))
orgs["zip5"] = orgs["zip5"].astype(object)
zcta_lookup["zcta"] = zcta_lookup["zcta"].astype(object)
orgs = orgs.merge(zcta_lookup, how="left", left_on="zip5", right_on="zcta")
orgs["placement_method"] = np.select([orgs["is_geocoded"].to_numpy(), orgs["zip_tract_geoid"].notna().to_numpy()],
                                     ["geocoded", "zip_fallback"], default="unplaced")
orgs["final_tract_geoid"] = np.where(orgs["is_geocoded"], orgs["tract_geoid"].astype(object), orgs["zip_tract_geoid"].astype(object))
orgs.loc[orgs["placement_method"] == "unplaced", "final_tract_geoid"] = None
orgs.loc[orgs["placement_method"] == "geocoded", ["zcta_overlap_share", "n_tracts_in_zcta"]] = np.nan
orgs["fallback_reason"] = orgs["fallback_reason"].where(orgs["placement_method"] != "geocoded")
orgs = orgs[["ein", "org_name", "form_type", "tax_year", "n_filings", "street_clean", "city_clean", "zip5",
             "is_po_box", "fallback_reason", "census_match_status", "latitude", "longitude",
             "placement_method", "final_tract_geoid", "zcta_overlap_share", "n_tracts_in_zcta",
             "had_both_geocode_and_fallback", "record_id"]]

placement_counts = orgs["placement_method"].value_counts()
print("\nPlacement:\n", placement_counts.to_string())
print(f"Org-level tract coverage: {orgs['final_tract_geoid'].notna().mean():.2%}")
print(pd.crosstab(orgs["fallback_reason"], orgs["placement_method"]))

orgs = orgs.merge(acs[["geoid", "population", "poverty_rate_pct", "median_household_income"]],
                  how="left", left_on="final_tract_geoid", right_on="geoid").drop(columns="geoid")
print(f"Placed orgs missing from ACS (should be 0): {(orgs['final_tract_geoid'].notna() & orgs['population'].isna()).sum()}")

placed = orgs[orgs["final_tract_geoid"].notna()]
counts = (placed.groupby("final_tract_geoid")
          .agg(nonprofit_count=("ein", "nunique"),
               n_geocoded=("placement_method", lambda s: (s == "geocoded").sum()),
               n_zip_fallback=("placement_method", lambda s: (s == "zip_fallback").sum()),
               n_990=("form_type", lambda s: (s == "990").sum()),
               n_990ez=("form_type", lambda s: (s == "990EZ").sum()),
               n_990pf=("form_type", lambda s: (s == "990-PF").sum()))
          .reset_index().rename(columns={"final_tract_geoid": "geoid"}))
tract_kpi = acs.merge(counts, on="geoid", how="left")
cnt = ["nonprofit_count", "n_geocoded", "n_zip_fallback", "n_990", "n_990ez", "n_990pf"]
tract_kpi[cnt] = tract_kpi[cnt].fillna(0).astype(int)
pop = tract_kpi["population"].where(tract_kpi["population"] > 0)
tract_kpi["kpi1_nonprofits_per_1k"] = (1000 * tract_kpi["nonprofit_count"] / pop).round(3)
tract_kpi["kpi1_public_charities_per_1k"] = (1000 * (tract_kpi["n_990"] + tract_kpi["n_990ez"]) / pop).round(3)
tract_kpi["low_population_flag"] = tract_kpi["population"].fillna(0) < LOW_POP_THRESHOLD
tract_kpi["share_zip_fallback"] = (tract_kpi["n_zip_fallback"] / tract_kpi["nonprofit_count"].replace(0, np.nan)).round(3)

state_rate = 1000 * tract_kpi["nonprofit_count"].sum() / tract_kpi["population"].sum()
stable = tract_kpi[~tract_kpi["low_population_flag"]]
county = (tract_kpi.groupby("county_fips")
          .agg(tracts=("geoid", "count"), population=("population", "sum"), nonprofits=("nonprofit_count", "sum"),
               zero_nonprofit_tracts=("nonprofit_count", lambda s: (s == 0).sum()))
          .assign(nonprofits_per_1k=lambda d: (1000 * d["nonprofits"] / d["population"]).round(2))
          .sort_values("nonprofits_per_1k", ascending=False))
print(f"\nStatewide: {state_rate:.2f} nonprofits per 1,000 residents")
print(f"Tracts: {len(tract_kpi):,} | zero nonprofits: {(tract_kpi['nonprofit_count'] == 0).sum():,} | low-pop flagged: {tract_kpi['low_population_flag'].sum()}")
print(stable["kpi1_nonprofits_per_1k"].describe(percentiles=[.1, .25, .5, .75, .9, .99]).round(2).to_string())
print(county)

tracts_gdf = None
for yr in [ACS_YEAR, 2024, 2023, 2022, 2020]:
    for url in [f"https://www2.census.gov/geo/tiger/GENZ{yr}/shp/cb_{yr}_{STATE_FIPS}_tract_500k.zip",
                f"https://www2.census.gov/geo/tiger/TIGER{yr}/TRACT/tl_{yr}_{STATE_FIPS}_tract.zip"]:
        try:
            resp = requests.get(url, timeout=300)
            resp.raise_for_status()
            with open("ma_tracts.zip", "wb") as f:
                f.write(resp.content)
            tracts_gdf = gpd.read_file("ma_tracts.zip")
            print("Boundaries:", url)
            break
        except Exception:
            print("Failed:", url)
    if tracts_gdf is not None:
        break
tracts_gdf = tracts_gdf.to_crs(4326)[["GEOID", "geometry"]]

geo = orgs[orgs["placement_method"] == "geocoded"].dropna(subset=["latitude", "longitude"])
pts = gpd.GeoDataFrame(geo[["ein", "final_tract_geoid"]],
                       geometry=gpd.points_from_xy(geo["longitude"], geo["latitude"]), crs=4326)
hit = gpd.sjoin(pts, tracts_gdf, how="left", predicate="within")
point_in_tract_rate = (hit["GEOID"] == hit["final_tract_geoid"]).mean()
print(f"Geocoded orgs whose point falls inside their assigned tract: {point_in_tract_rate:.2%}")

half = SPOT_CHECK_N // 2
spot = pd.concat([orgs[orgs["placement_method"] == "geocoded"].sample(half, random_state=RANDOM_SEED),
                  orgs[orgs["placement_method"] == "zip_fallback"].sample(half, random_state=RANDOM_SEED)])
spot_tracts = tracts_gdf[tracts_gdf["GEOID"].isin(spot["final_tract_geoid"])]
kpi_lookup = tract_kpi.set_index("geoid")["kpi1_nonprofits_per_1k"]

m = folium.Map(location=[42.25, -71.8], zoom_start=8, tiles="OpenStreetMap")
for _, row in spot.iterrows():
    tgeom = spot_tracts[spot_tracts["GEOID"] == row["final_tract_geoid"]]
    color = "#2563eb" if row["placement_method"] == "geocoded" else "#ea580c"
    popup = (f"<b>{row['org_name']}</b><br>EIN {row['ein']} · {row['form_type']}<br>"
             f"{row['street_clean']}, {row['city_clean']} {row['zip5']}<br>"
             f"Method: {row['placement_method']}<br>Tract: {row['final_tract_geoid']}<br>"
             f"Tract KPI 1: {kpi_lookup.get(row['final_tract_geoid'])}")
    if row["placement_method"] == "zip_fallback":
        popup += f"<br>ZCTA overlap share: {row['zcta_overlap_share']}"
    if not tgeom.empty:
        folium.GeoJson(tgeom.__geo_interface__,
                       style_function=lambda _, c=color: {"color": c, "weight": 2, "fillOpacity": 0.08}).add_to(m)
    if row["placement_method"] == "geocoded":
        lat, lon = row["latitude"], row["longitude"]
    elif not tgeom.empty:
        c = tgeom.to_crs(26986).centroid.to_crs(4326).iloc[0]
        lat, lon = c.y, c.x
    else:
        continue
    folium.CircleMarker([lat, lon], radius=6, color=color, fill=True, fill_opacity=0.9,
                        popup=folium.Popup(popup, max_width=320)).add_to(m)
m.get_root().html.add_child(folium.Element(
    "<div style='position:fixed;bottom:20px;left:20px;z-index:9999;background:white;padding:8px 10px;"
    "border:1px solid #ccc;font:13px sans-serif'><span style='color:#2563eb'>●</span> geocoded (address point)<br>"
    "<span style='color:#ea580c'>●</span> ZIP fallback (tract centroid)</div>"))
if not spot_tracts.empty:
    minx, miny, maxx, maxy = spot_tracts.total_bounds
    m.fit_bounds([[miny, minx], [maxy, maxx]])
m.save(f"{OUT_DIR}/spot_check_map.html")

spot_sheet = spot[["ein", "org_name", "form_type", "street_clean", "city_clean", "zip5",
                   "placement_method", "final_tract_geoid", "zcta_overlap_share"]].copy()
spot_sheet["looks_right (Y/N)"] = ""
spot_sheet["notes"] = ""
spot_sheet.to_csv(f"{OUT_DIR}/spot_check_sheet.csv", index=False)

orgs.to_csv(f"{OUT_DIR}/ma_org_tract_placement.csv", index=False)
tract_kpi.to_csv(f"{OUT_DIR}/ma_tract_kpi1.csv", index=False)
county.reset_index().to_csv(f"{OUT_DIR}/ma_county_kpi1.csv", index=False)
acs.to_csv(f"{OUT_DIR}/acs_ma_tracts_{ACS_YEAR}.csv", index=False)
summary = {
    "acs_dataset": f"ACS 5-year {ACS_YEAR-4}-{ACS_YEAR}",
    "unit": "organization (unique EIN); most recent geocoded filing preferred",
    "filing_records": int(len(recs)),
    "unique_orgs": int(len(orgs)),
    "orgs_geocoded": int(placement_counts.get("geocoded", 0)),
    "orgs_zip_fallback": int(placement_counts.get("zip_fallback", 0)),
    "orgs_unplaced": int(placement_counts.get("unplaced", 0)),
    "org_tract_coverage_pct": round(100 * orgs["final_tract_geoid"].notna().mean(), 2),
    "orgs_with_mixed_geocode_and_fallback_filings": int(orgs["had_both_geocode_and_fallback"].sum()),
    "zip_fallback_rule": "ZIP=ZCTA; MA tract with largest land overlap (Census 2020 ZCTA-tract relationship file)",
    "geocoded_point_in_assigned_tract_pct": round(100 * point_in_tract_rate, 2),
    "ma_tracts": int(len(tract_kpi)),
    "tracts_with_zero_nonprofits": int((tract_kpi["nonprofit_count"] == 0).sum()),
    "low_population_threshold": LOW_POP_THRESHOLD,
    "low_population_tracts": int(tract_kpi["low_population_flag"].sum()),
    "statewide_nonprofits_per_1k": round(state_rate, 3),
    "kpi1_median_tract_per_1k_excl_low_pop": round(float(stable["kpi1_nonprofits_per_1k"].median()), 3),
}
with open(f"{OUT_DIR}/task2_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary, indent=2))
