"""Step 8: ZIP fallback placement for New England filers, with a placement_method flag.

Records without a tract (PO box, No_Match, Tie, no house number) are placed by ZIP:
  1. zip_fallback_cluster: tract where that ZIP's directly geocoded orgs cluster
     (most unique EINs; same state). This is the rule described to the client in Meeting #3.
  2. zip_fallback_area:    if no geocoded orgs share the ZIP, the tract with the largest
     land overlap with the ZIP's ZCTA (same rule as Sprint 2).
  3. unplaced:             neither rule finds a tract.
Geocoded records keep their tract: tract_direct / tract_retry.

CT: the 2020 ZCTA-tract file uses old county codes. Tracts are converted to the 2022
planning-region GEOIDs with the 2024 Gazetteer by 6-digit tract code (unique statewide
except water-only 99xxxx tracts, which are dropped).

Inputs:  outputs/ne_geocoded_final.csv
         data/raw/tab20_zcta520_tract20_natl.txt, data/raw/2024_gaz_tracts_09.txt
Outputs (outputs/placement/):
  ne_placement_filing.csv  one row per filing record (EIN + tax_year)
  ne_placement_org.csv     one row per EIN
  ne_placement_summary.json, ne_placement_spotcheck.csv
"""
import json
from datetime import datetime

import pandas as pd

from config import OUTPUT_DIR, RAW_DIR, STATES, ABBR_TO_FIPS

IN_FILE = OUTPUT_DIR / "ne_geocoded_final.csv"
REL_FILE = RAW_DIR / "tab20_zcta520_tract20_natl.txt"
CT_GAZ_FILE = RAW_DIR / "2024_gaz_tracts_09.txt"
OUT_DIR = OUTPUT_DIR / "placement"
NE_FIPS = set(ABBR_TO_FIPS.values())
METHOD_ORDER = ["tract_direct", "tract_retry", "zip_fallback_cluster", "zip_fallback_area", "unplaced"]


def load_zcta_tract():
    rel = pd.read_csv(REL_FILE, sep="|", dtype=str, encoding="utf-8-sig",
                      usecols=["GEOID_ZCTA5_20", "GEOID_TRACT_20", "AREALAND_PART"])
    rel = rel.dropna(subset=["GEOID_ZCTA5_20", "GEOID_TRACT_20"])
    rel = rel[rel["GEOID_TRACT_20"].str[:2].isin(NE_FIPS)].copy()
    rel = rel[~rel["GEOID_TRACT_20"].str[5:].str.startswith("99")]  # water-only tracts

    # CT: old county code -> 2022 planning region, via 6-digit tract code
    gaz = pd.read_csv(CT_GAZ_FILE, sep="\t", dtype=str)
    gaz.columns = [c.strip() for c in gaz.columns]
    gaz = gaz[~gaz["GEOID"].str[5:].str.startswith("99")]
    tract6_to_new = dict(zip(gaz["GEOID"].str[5:], gaz["GEOID"]))
    if len(tract6_to_new) != len(gaz):
        raise ValueError("CT 6-digit tract codes are not unique")
    is_ct = rel["GEOID_TRACT_20"].str.startswith("09")
    new = rel.loc[is_ct, "GEOID_TRACT_20"].str[5:].map(tract6_to_new)
    if new.isna().any():
        raise ValueError(f"{new.isna().sum()} CT tracts not found in 2024 Gazetteer")
    rel.loc[is_ct, "GEOID_TRACT_20"] = new

    rel["AREALAND_PART"] = pd.to_numeric(rel["AREALAND_PART"], errors="coerce").fillna(0)
    rel = rel.rename(columns={"GEOID_ZCTA5_20": "zip5", "GEOID_TRACT_20": "tract"})
    rel["state_fips"] = rel["tract"].str[:2]
    rel["zcta_overlap_share"] = rel["AREALAND_PART"] / rel.groupby("zip5")["AREALAND_PART"].transform("sum")
    rel["n_tracts_in_zcta"] = rel.groupby("zip5")["tract"].transform("nunique")
    return rel


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(IN_FILE, dtype=str, keep_default_na=False)
    d["state_fips"] = d["state_clean"].map(ABBR_TO_FIPS)
    d["tax_year_num"] = pd.to_numeric(d["tax_year"], errors="coerce")
    placed = d["geocode_method"].isin(["tract_direct", "tract_retry"])

    rel = load_zcta_tract()

    # Rule 1: cluster of directly geocoded orgs in the same ZIP and state (unique EINs)
    g = d[placed][["zip5", "state_fips", "tract_geoid", "ein"]].drop_duplicates()
    cl = (g.groupby(["zip5", "state_fips", "tract_geoid"])["ein"].nunique()
            .rename("n").reset_index())
    cl["zip_geocoded_orgs"] = cl.groupby(["zip5", "state_fips"])["n"].transform("sum")
    # tie-break: larger land overlap with the ZCTA, then GEOID
    cl = cl.merge(rel[["zip5", "tract", "AREALAND_PART"]].rename(columns={"tract": "tract_geoid"}),
                  on=["zip5", "tract_geoid"], how="left").fillna({"AREALAND_PART": 0})
    cl = (cl.sort_values(["zip5", "state_fips", "n", "AREALAND_PART", "tract_geoid"],
                         ascending=[True, True, False, False, True])
            .drop_duplicates(["zip5", "state_fips"]))
    cl = cl.rename(columns={"tract_geoid": "cluster_tract", "n": "cluster_tract_orgs"})
    cl["cluster_share"] = (cl["cluster_tract_orgs"] / cl["zip_geocoded_orgs"]).round(3)
    cl = cl[["zip5", "state_fips", "cluster_tract", "cluster_tract_orgs", "zip_geocoded_orgs", "cluster_share"]]

    # Rule 2: largest land overlap, preferring tracts in the filing's state
    ar = (rel.sort_values(["zip5", "state_fips", "AREALAND_PART"], ascending=[True, True, False])
             .drop_duplicates(["zip5", "state_fips"])
             .rename(columns={"tract": "area_tract"})
             [["zip5", "state_fips", "area_tract", "zcta_overlap_share", "n_tracts_in_zcta"]])

    d = d.merge(cl, on=["zip5", "state_fips"], how="left").merge(ar, on=["zip5", "state_fips"], how="left")

    d["placement_method"] = "unplaced"
    d["final_tract_geoid"] = ""
    d.loc[placed, "placement_method"] = d.loc[placed, "geocode_method"]
    d.loc[placed, "final_tract_geoid"] = d.loc[placed, "tract_geoid"]
    need = ~placed
    use_cl = need & d["cluster_tract"].notna()
    use_ar = need & ~use_cl & d["area_tract"].notna()
    d.loc[use_cl, ["placement_method", "final_tract_geoid"]] = list(zip(["zip_fallback_cluster"] * use_cl.sum(), d.loc[use_cl, "cluster_tract"]))
    d.loc[use_ar, ["placement_method", "final_tract_geoid"]] = list(zip(["zip_fallback_area"] * use_ar.sum(), d.loc[use_ar, "area_tract"]))
    d["placement_precision"] = d["placement_method"].map({
        "tract_direct": "tract", "tract_retry": "tract",
        "zip_fallback_cluster": "zip_approx", "zip_fallback_area": "zip_approx", "unplaced": "none"})
    d["final_county_fips"] = d["final_tract_geoid"].str[:5]

    # Agreement between the two ZIP rules (where both exist)
    both = need & d["cluster_tract"].notna() & d["area_tract"].notna()
    agree = (d.loc[both, "cluster_tract"] == d.loc[both, "area_tract"]).mean() if both.any() else None

    cols = ["record_id", "ein", "tax_year", "form_type", "org_name", "source_file",
            "street_clean", "city_clean", "state_clean", "zip5", "is_po_box",
            "geocode_status", "census_match_status", "fallback_reason", "geocode_method",
            "latitude", "longitude", "placement_method", "placement_precision",
            "final_tract_geoid", "final_county_fips",
            "cluster_tract_orgs", "zip_geocoded_orgs", "cluster_share",
            "zcta_overlap_share", "n_tracts_in_zcta"]
    filing = d[cols]
    filing.to_csv(OUT_DIR / "ne_placement_filing.csv", index=False)

    # Org level: prefer tract-level placement, then latest tax year
    rank = {m: i for i, m in enumerate(METHOD_ORDER)}
    o = d.assign(_r=d["placement_method"].map(rank))
    o = o.sort_values(["ein", "_r", "tax_year_num"], ascending=[True, True, False])
    n_filings = d.groupby("ein").size()
    org = o.drop_duplicates("ein")[cols].copy()
    org.insert(3, "n_filings", org["ein"].map(n_filings).values)
    org.to_csv(OUT_DIR / "ne_placement_org.csv", index=False)

    # Spot-check sample: 5 per state per ZIP method
    sample = (d[d["placement_method"].isin(["zip_fallback_cluster", "zip_fallback_area"])]
              .groupby(["state_clean", "placement_method"], group_keys=False)
              .apply(lambda x: x.sample(min(5, len(x)), random_state=539), include_groups=True))
    sample[["state_clean", "placement_method", "ein", "org_name", "street_clean", "city_clean",
            "zip5", "final_tract_geoid", "cluster_share", "zcta_overlap_share"]].to_csv(
        OUT_DIR / "ne_placement_spotcheck.csv", index=False)

    def table(df):
        t = pd.crosstab(df["state_clean"], df["placement_method"]).reindex(columns=METHOD_ORDER, fill_value=0)
        t = t.reindex(list(STATES))
        t["total"] = t.sum(axis=1)
        t["tract_level_pct"] = ((t["tract_direct"] + t["tract_retry"]) / t["total"] * 100).round(1)
        t["placed_pct"] = ((t["total"] - t["unplaced"]) / t["total"] * 100).round(1)
        t.loc["TOTAL"] = t[METHOD_ORDER + ["total"]].sum()
        t.loc["TOTAL", "tract_level_pct"] = round((t.loc["TOTAL", "tract_direct"] + t.loc["TOTAL", "tract_retry"]) / t.loc["TOTAL", "total"] * 100, 1)
        t.loc["TOTAL", "placed_pct"] = round((t.loc["TOTAL", "total"] - t.loc["TOTAL", "unplaced"]) / t.loc["TOTAL", "total"] * 100, 1)
        return t

    tf, to = table(filing), table(org)
    unplaced_reasons = filing[filing["placement_method"] == "unplaced"]["fallback_reason"].value_counts().to_dict()
    summary = {
        "summary_created_at": datetime.now().astimezone().isoformat(),
        "rules": {"zip_fallback_cluster": "tract with most directly geocoded unique EINs in same ZIP and state",
                  "zip_fallback_area": "largest land overlap between ZCTA and tract (same state)",
                  "ct_conversion": "2020 CT tracts mapped to 2022 planning-region GEOIDs by 6-digit tract code (2024 Gazetteer)"},
        "filing_level": tf.reset_index().to_dict(orient="records"),
        "org_level": to.reset_index().to_dict(orient="records"),
        "cluster_vs_area_same_tract_pct": round(agree * 100, 1) if agree is not None else None,
        "unplaced_reasons_filing": unplaced_reasons,
    }
    with (OUT_DIR / "ne_placement_summary.json").open("w") as f:
        json.dump(summary, f, indent=2, default=int)

    pd.set_option("display.width", 200)
    print("FILING LEVEL (EIN + tax_year)\n", tf.to_string())
    print("\nORG LEVEL (one row per EIN)\n", to.to_string())
    print(f"\nCluster vs area rule pick the same tract: {summary['cluster_vs_area_same_tract_pct']}% of fallback records where both exist")
    print("Unplaced reasons (filing):", unplaced_reasons)


if __name__ == "__main__":
    main()
