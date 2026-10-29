"""
match_rate_table.py — final PF recipient match-rate table vs. the ~80% benchmark.

Built on Task 3's final output, pf_recipients_matched.parquet, so the starting
point is exactly Task 3's numbers (no re-deriving from the raw CSV):
  - every grant row keeps Task 3's match_method
  - Task 3's set_aside rows (individual, foreign, unspecified, unidentifiable)
    are excluded from the denominator; government stays in, as in Task 3
  - rows Task 3 handed to fuzzy (unmatched / ambiguous) take the result of
    fuzzy_match.py (F1/F2/F3, or still unmatched)
  - gov_name_review rows stay unmatched (Task 3 left them for review, since a
    same-name nonprofit is often not the public body)

Two rates are reported:
  standard  = everything Task 3 counts as matched, plus fuzzy
  strict    = same, minus Task 3's flagged EIN buckets (name disagrees,
              government-likely, revoked, unlisted-kept, self-grant)

Run:  python3 src/fuzzy_matching/match_rate_table.py --sample filer_ma
      (use the same --sample as fuzzy_match.py)
"""

import argparse
import glob
import os
import sys

import pandas as pd

# config.py lives one folder up, in src/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

OUT = config.OUTPUT_DIR
BENCHMARK = 0.80
KEY = ["filer_ein", "taxyear", "line_number"]

# Task 3 match_method -> category in this table
TASK3_MAP = {
    "ein_verified": "T3_VERIFIED",
    "ein_no_name": "T3_VERIFIED",
    "ein_corrected_name_zip": "T3_VERIFIED",
    "ein_corrected_name_city": "T3_VERIFIED",
    "name_zip": "T3_NAME",
    "name_city": "T3_NAME",
    "ein_name_disagrees": "T3_FLAGGED",
    "ein_government_likely": "T3_FLAGGED",
    "ein_revoked": "T3_FLAGGED",
    "ein_unlisted_kept": "T3_FLAGGED",
    "ein_self_grant": "T3_FLAGGED",
    "gov_name_review": "GOV_NAME_REVIEW",
    "set_aside": "SET_ASIDE",
    "unmatched": "TO_FUZZY",
    "ambiguous": "TO_FUZZY",
}
ORDER = ["T3_VERIFIED", "T3_NAME", "T3_FLAGGED", "MATCHED_F1", "MATCHED_F2", "MATCHED_F3",
         "AMBIGUOUS", "BELOW_THRESHOLD", "NO_CANDIDATE", "NOT_IN_FUZZY_RUN", "GOV_NAME_REVIEW",
         "SET_ASIDE"]
LABELS = {
    "T3_VERIFIED": "Task 3: reported EIN verified",
    "T3_NAME": "Task 3: exact name match (name + ZIP, name + city)",
    "T3_FLAGGED": "Task 3: reported EIN kept but flagged (name disagrees, gov-likely, revoked, unlisted, self-grant)",
    "MATCHED_F1": "Fuzzy F1: same ZIP, similarity >= 0.85",
    "MATCHED_F2": "Fuzzy F2: same 3-digit ZIP, >= 0.85",
    "MATCHED_F3": "Fuzzy F3: same state, >= 0.90",
    "AMBIGUOUS": "No match: two close EINs (ambiguous)",
    "BELOW_THRESHOLD": "No match: below fuzzy threshold",
    "NO_CANDIDATE": "No match: no candidate found",
    "NOT_IN_FUZZY_RUN": "No match: row not found in fuzzy results (check)",
    "GOV_NAME_REVIEW": "No match: government, left for review (Task 3)",
    "SET_ASIDE": "Excluded: individual, foreign, unspecified, no name",
}
MATCHED_BEFORE = ["T3_VERIFIED", "T3_NAME", "T3_FLAGGED"]
MATCHED_FUZZY = ["MATCHED_F1", "MATCHED_F2", "MATCHED_F3"]

# Task 3's published numbers for filer_in_ma (README / match_rates.csv), used as a check
TASK3_CHECK = {"filer_ma": {"rows": 90_906, "eligible": 85_010, "matched": 68_889}}


def find_file(name):
    hits = sorted(glob.glob(os.path.join(config.DATA_DIR, "**", name), recursive=True))
    if not hits:
        raise FileNotFoundError(f"{name} not found under {config.DATA_DIR}")
    return hits[0]


def norm_key(df):
    for c in KEY:
        df[c] = df[c].astype(str).str.strip()
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="filer_ma", choices=["filer_ma", "recipient_ma", "all"])
    a = ap.parse_args()

    # 1. Task 3's final row-level output
    g = pd.read_parquet(find_file("pf_recipients_matched.parquet"),
                        columns=KEY + ["amount", "match_method", "filer_state", "recipient_in_ma"])
    g = norm_key(g)
    g["amt"] = pd.to_numeric(g["amount"], errors="coerce").fillna(0)

    if a.sample == "filer_ma":
        g = g[g["filer_state"].fillna("").astype(str).str.strip().str.upper() == "MA"]
    elif a.sample == "recipient_ma":
        g = g[g["recipient_in_ma"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])]
    g = g.reset_index(drop=True)

    unknown = set(g["match_method"].unique()) - set(TASK3_MAP)
    if unknown:
        raise SystemExit(f"Unknown match_method values from Task 3: {sorted(unknown)}")
    g["category"] = g["match_method"].map(TASK3_MAP)

    # 2. Fuzzy results for the rows Task 3 handed over
    fz_path = os.path.join(OUT, f"fuzzy_matches_{a.sample}.csv")
    if not os.path.exists(fz_path):
        raise SystemExit(f"Run fuzzy_match.py --sample {a.sample} first ({fz_path} missing)")
    fz = pd.read_csv(fz_path, dtype=str, keep_default_na=False)
    fz["final"] = [f"MATCHED_{t.split('_')[0]}" if s == "MATCHED" else s
                   for s, t in zip(fz["match_status"], fz["match_tier"])]
    lut = dict(zip(zip(fz["name_norm"], fz["state"], fz["zip5"]), fz["final"]))

    # normalized name/state/ZIP for pool rows (same keys fuzzy_match.py used)
    pool = pd.read_parquet(find_file("pf_recipients_for_fuzzy.parquet"),
                           columns=KEY + ["rcp_name_norm", "rcp_state_n", "rcp_zip5"])
    pool = norm_key(pool)
    for c in ["rcp_name_norm", "rcp_state_n", "rcp_zip5"]:
        pool[c] = pool[c].fillna("").astype(str).str.strip()
    g = g.merge(pool, on=KEY, how="left")

    to_fz = g["category"] == "TO_FUZZY"
    g.loc[to_fz, "category"] = [
        lut.get(k, "NOT_IN_FUZZY_RUN") for k in
        zip(g.loc[to_fz, "rcp_name_norm"].fillna(""), g.loc[to_fz, "rcp_state_n"].fillna(""),
            g.loc[to_fz, "rcp_zip5"].fillna(""))]

    # for information only: fuzzy matches on gov_name_review rows (not counted)
    gov = g["category"] == "GOV_NAME_REVIEW"
    gov_fz = sum(str(lut.get(k, "")).startswith("MATCHED") for k in
                 zip(g.loc[gov, "rcp_name_norm"].fillna(""), g.loc[gov, "rcp_state_n"].fillna(""),
                     g.loc[gov, "rcp_zip5"].fillna("")))

    # 3. Table
    t = g.groupby("category").agg(rows=("amt", "size"), dollars=("amt", "sum")).reindex(ORDER).fillna(0)
    t = t[t["rows"] > 0]
    elig = t.index != "SET_ASIDE"
    t.insert(0, "label", [LABELS[i] for i in t.index])
    t["pct_eligible_rows"] = (t["rows"] / t.loc[elig, "rows"].sum()).where(elig)
    t["pct_eligible_dollars"] = (t["dollars"] / t.loc[elig, "dollars"].sum()).where(elig)
    t.to_csv(os.path.join(OUT, f"match_rate_table_{a.sample}.csv"))

    # 4. Summary: standard and strict, before and after fuzzy
    er, ed = t.loc[elig, "rows"].sum(), t.loc[elig, "dollars"].sum()
    summ = []
    for rate, drop in [("standard (Task 3 definition)", []), ("strict (excl. flagged EINs)", ["T3_FLAGGED"])]:
        for stage, cats in [("before fuzzy", MATCHED_BEFORE), ("after fuzzy", MATCHED_BEFORE + MATCHED_FUZZY)]:
            m = t.index.isin([c for c in cats if c not in drop])
            r, d = t.loc[m, "rows"].sum(), t.loc[m, "dollars"].sum()
            summ.append({"rate": rate, "stage": stage, "eligible_rows": int(er), "matched_rows": int(r),
                         "match_rate_rows": round(r / er, 4), "match_rate_dollars": round(d / ed, 4),
                         "benchmark": BENCHMARK, "gap_vs_80_pts_rows": round((r / er - BENCHMARK) * 100, 2)})
    s = pd.DataFrame(summ)
    s.to_csv(os.path.join(OUT, f"match_rate_summary_{a.sample}.csv"), index=False)

    # 5. Print
    pd.set_option("display.width", 240)
    pd.set_option("display.max_colwidth", 70)
    show = t.copy()
    show["rows"] = show["rows"].astype(int).map("{:,}".format)
    show["dollars"] = show["dollars"].map("${:,.0f}".format)
    for c in [c for c in show.columns if c.startswith("pct")]:
        show[c] = show[c].map(lambda x: "" if pd.isna(x) else f"{x:.1%}")
    print(f"\nSample '{a.sample}': {len(g):,} grant rows, ${g['amt'].sum():,.0f}\n")
    print(show.to_string())
    print("\n" + s.to_string(index=False))

    # 6. Checks
    print("\nChecks")
    print(f"  every row has one category: {g['category'].notna().all()}")
    nf = int((g["category"] == "NOT_IN_FUZZY_RUN").sum())
    print(f"  rows handed to fuzzy but not found in fuzzy results: {nf:,} (should be 0)")
    print(f"  fuzzy matches on gov_name_review rows (not counted): {gov_fz:,}")
    if a.sample in TASK3_CHECK:
        exp = TASK3_CHECK[a.sample]
        before = int(t.loc[t.index.isin(MATCHED_BEFORE), "rows"].sum())
        for name, got in [("rows", len(g)), ("eligible", int(er)), ("matched before fuzzy", before)]:
            want = exp["matched" if name.startswith("matched") else name]
            print(f"  {name}: {got:,} vs Task 3 {want:,} -> {'OK' if got == want else 'MISMATCH'}")


if __name__ == "__main__":
    main()