"""
Step 5 (Milestone 1 follow-up for Pharos): which 990 / 990-EZ filings are in the
header table but missing from the summary table, and why?

Compares the two tables on EIN + tax year in both directions, then breaks the
missing filings down by form type, tax year, filing month, return flags, state
and (for 990-EZ) gross receipts, so the client can trace it in their ETL.

Finding (Oct 2026): 2,379 filings from 1,988 orgs, all 990-EZ, 99.8% with zero or
blank gross receipts, spread evenly across filing months.

Output: outputs/missing_summary_filings.xlsx (summary tabs + full list)
        outputs/missing_summary_filings.csv  (full list)
"""
import pandas as pd

from config import find_csv, out

KEY = ["f9_00_org_ein", "f9_00_tax_year"]
FLAGS = ["f9_00_return_amended_x", "f9_00_return_initial_x", "f9_00_return_final_x",
         "f9_00_return_group_x", "f9_00_gro_rcpt_lt50k_x"]
HEADER_COLS = KEY + ["f9_00_org_name_l1", "f9_00_return_type", "f9_00_return_time_stamp",
                     "f9_00_irs_sec_submission_id", "f9_00_tax_period_end_date",
                     "f9_00_org_addr_state", "f9_00_gro_rcpt"] + FLAGS


def load(table, cols):
    df = pd.read_csv(find_csv(table), usecols=cols, dtype=str)
    df["f9_00_org_ein"] = df["f9_00_org_ein"].str.strip().str.zfill(9)   # keep leading zeros
    df["f9_00_tax_year"] = df["f9_00_tax_year"].str.strip()
    return df


header = load("f9_p00_t00_header", HEADER_COLS)
summary = load("f9_p01_t00_summary", KEY)
mission = load("f9_p03_t00_mission", KEY)

# Month the return was filed: the return timestamp, else the YYYYDDD inside the IRS submission ID
ts = pd.to_datetime(header["f9_00_return_time_stamp"], errors="coerce", utc=True).dt.tz_localize(None)
sid = pd.to_datetime(header["f9_00_irs_sec_submission_id"].str.strip().str[6:13], format="%Y%j", errors="coerce")
header["filing_month"] = ts.fillna(sid).dt.strftime("%Y-%m").fillna("(blank)")
header["form"] = header["f9_00_return_type"].fillna("(blank)")

# Gross receipts bucket (blank / zero / positive)
receipts = pd.to_numeric(header["f9_00_gro_rcpt"], errors="coerce")
header["gross_receipts"] = receipts.map(lambda v: "blank" if pd.isna(v) else ("zero" if v == 0 else "positive"))

# ---- 1. Counts, both directions ----------------------------------------------
h_keys = pd.MultiIndex.from_frame(header[KEY])
s_keys = pd.MultiIndex.from_frame(summary[KEY])
m_keys = pd.MultiIndex.from_frame(mission[KEY])
header["in_summary"] = h_keys.isin(s_keys)
header["in_mission"] = h_keys.isin(m_keys)
missing = header[~header["in_summary"]].copy()

checks = pd.DataFrame({
    "header rows": len(header),
    "summary rows": len(summary),
    "raw difference (header - summary)": len(header) - len(summary),
    "duplicate keys in header": int(header.duplicated(KEY).sum()),
    "duplicate keys in summary": int(summary.duplicated(KEY).sum()),
    "in header but NOT in summary": len(missing),
    "in summary but NOT in header": int((~s_keys.isin(h_keys)).sum()),
    "distinct EINs affected": missing["f9_00_org_ein"].nunique(),
    "missing tax year 2024": int((missing["f9_00_tax_year"] == "2024").sum()),
    "missing tax year 2025": int((missing["f9_00_tax_year"] == "2025").sum()),
    "header filings missing from mission": int((~header["in_mission"]).sum()),
    "missing from BOTH summary and mission": int((~missing["in_mission"]).sum()),
}.items(), columns=["check", "value"])


# ---- 2. Breakdowns: missing vs all filings, so over-represented groups stand out
def rate_table(df, col):
    t = df.groupby(col).agg(all_filings=("in_summary", "size"),
                            missing=("in_summary", lambda s: int((~s).sum())))
    t["missing_rate_pct"] = (t["missing"] / t["all_filings"] * 100).round(2)
    t["pct_of_missing"] = (t["missing"] / max(len(missing), 1) * 100).round(1)
    return t.reset_index()


by_form = rate_table(header, "form")
by_year = rate_table(header, "f9_00_tax_year")
by_form_year = rate_table(header, ["form", "f9_00_tax_year"])
by_month = rate_table(header, "filing_month").sort_values("filing_month")
by_receipts_ez = rate_table(header[header["form"] == "990EZ"], "gross_receipts")


def is_true(s):
    return s.fillna("").str.strip().str.lower().isin(["t", "true", "x", "1", "y"])


by_flag = pd.DataFrame([{"flag": c,
                         "pct_of_missing": round(is_true(missing[c]).mean() * 100, 1),
                         "pct_of_all_filings": round(is_true(header[c]).mean() * 100, 1)} for c in FLAGS])
by_state = (missing["f9_00_org_addr_state"].fillna("(blank)").value_counts().head(10)
            .rename_axis("state").reset_index(name="missing"))

tables = [("Count checks", checks), ("By form type", by_form), ("By tax year", by_year),
          ("By form type and tax year", by_form_year), ("990-EZ by gross receipts", by_receipts_ez),
          ("By filing month", by_month), ("Return flags", by_flag), ("Top states", by_state)]

# ---- 3. Save -------------------------------------------------------------------
list_cols = ["f9_00_org_ein", "f9_00_tax_year", "f9_00_org_name_l1", "form", "filing_month",
             "f9_00_return_time_stamp", "f9_00_irs_sec_submission_id", "f9_00_tax_period_end_date",
             "f9_00_org_addr_state", "in_mission"] + FLAGS + ["f9_00_gro_rcpt", "gross_receipts"]
missing_list = missing.sort_values(["form", "f9_00_tax_year", "filing_month", "f9_00_org_ein"])[list_cols]
missing_list.to_csv(out("missing_summary_filings.csv"), index=False)

with pd.ExcelWriter(out("missing_summary_filings.xlsx")) as xw:
    r = 0
    for title, df in tables:
        pd.DataFrame([[title]]).to_excel(xw, sheet_name="Summary", startrow=r, index=False, header=False)
        df.to_excel(xw, sheet_name="Summary", startrow=r + 1, index=False)
        r += len(df) + 4
    missing_list.to_excel(xw, sheet_name="Missing filings", index=False)

# ---- 4. Print ------------------------------------------------------------------
pd.set_option("display.max_rows", 100, "display.width", 160)
for title, df in tables:
    print(f"\n=== {title.upper()} ===\n" + df.to_string(index=False))
print(f"\nSaved {out('missing_summary_filings.xlsx')} and .csv")
