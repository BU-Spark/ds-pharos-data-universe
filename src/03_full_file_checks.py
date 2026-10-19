"""
Step 3 (Milestone 1): data-quality checks on the full files.

For every table: row count, rows per tax year, duplicate keys, distinct EINs.
Where relevant: share of PO box addresses, ZIP code formats, the 990 vs 990-EZ
split, and what is really inside the recipient EIN columns.

Output: outputs/full_file_checks.csv
"""
import pandas as pd

from config import PO_BOX, find_csv, out

# table -> key columns, street columns, ZIP columns, recipient EIN columns, columns to count values of
CHECKS = {
    "f9_p00_t00_header": dict(key=["f9_00_org_ein", "f9_00_tax_year"], street=["f9_00_org_addr_l1"],
                              zip=["f9_00_org_addr_zip"], counts=["f9_00_return_type"]),
    "f9_p01_t00_summary": dict(key=["f9_00_org_ein", "f9_00_tax_year"]),
    "f9_p03_t00_mission": dict(key=["f9_00_org_ein", "f9_00_tax_year"]),
    "f9_p10_t00_balance_sheet": dict(key=["f9_00_org_ein", "f9_00_tax_year"]),
    "si_p02_t01_grants_us_orgs_govts": dict(key=["f9_00_org_ein", "f9_00_tax_year", "line_number"],
                                            street=["si_02_grant_us_org_addr_l1"],
                                            zip=["si_02_grant_us_org_addr_zip"], ein=["si_02_grant_us_org_ein"]),
    "pf_p00_t00_header": dict(key=["ein", "taxyear"], street=["numberandstreet"], zip=["zipcode"]),
    "pf_p01_t00_analysisofrevenueandexpenses": dict(key=["ein", "taxyear"]),
    "pf_p02_t00_balancesheets": dict(key=["ein", "taxyear"]),
    "pf_p08a_t00_summaryofdirectcharitableactivities": dict(key=["ein", "taxyear"]),
    "pf_p14_t03_supplementaryinformation": dict(key=["ein", "taxyear", "line_number"],
                                                street=["rcpntusaddrss_addrssln1txt"],
                                                zip=["rcpntusaddrss_zipcd"], ein=["rcpnt_ein"]),
}

rows = []


def add(table, check, value):
    rows.append({"table": table, "check": check, "value": value})


for table, cfg in CHECKS.items():
    street, zips, eins, counts = (cfg.get(k, []) for k in ("street", "zip", "ein", "counts"))
    usecols = list(dict.fromkeys(cfg["key"] + street + zips + eins + counts))
    n, keys, tally, value_counts = 0, [], {}, {}

    def bump(name, amount):
        tally[name] = tally.get(name, 0) + int(amount)

    for chunk in pd.read_csv(find_csv(table), usecols=usecols, dtype=str, chunksize=250_000):
        n += len(chunk)
        keys.append(chunk[cfg["key"]])
        for c in street:
            s = chunk[c].dropna()
            bump(c + " | filled", len(s))
            bump(c + " | PO box", s.str.contains(PO_BOX, case=False).sum())
        for c in zips:
            s = chunk[c].dropna().str.strip()
            bump(c + " | filled", len(s))
            bump(c + " | exactly 5 digits", s.str.fullmatch(r"\d{5}").sum())
            bump(c + " | 9 digits", s.str.fullmatch(r"\d{5}-?\d{4}").sum())
        for c in eins:
            s = chunk[c].fillna("(blank)").str.strip()
            label = s.where(~s.str.fullmatch(r"\d{9}"), "(9-digit EIN)")
            value_counts[c] = value_counts.get(c, pd.Series(dtype=float)).add(label.value_counts(), fill_value=0)
        for c in counts:
            value_counts[c] = value_counts.get(c, pd.Series(dtype=float)).add(
                chunk[c].fillna("(blank)").value_counts(), fill_value=0)

    keys = pd.concat(keys, ignore_index=True)
    add(table, "rows", n)
    for year, k in keys[cfg["key"][1]].value_counts().sort_index().items():
        add(table, f"tax year {year} rows", int(k))
    add(table, "duplicate rows on key (" + " + ".join(cfg["key"]) + ")", int(keys.duplicated().sum()))
    add(table, "distinct EINs", int(keys[cfg["key"][0]].nunique()))
    for c in street:
        add(table, f"{c}: % PO box (of filled)", round(tally[c + " | PO box"] / tally[c + " | filled"] * 100, 1))
    for c in zips:
        f = tally[c + " | filled"]
        add(table, f"{c}: % exactly 5 digits", round(tally[c + " | exactly 5 digits"] / f * 100, 1))
        add(table, f"{c}: % 9 digits", round(tally[c + " | 9 digits"] / f * 100, 1))
    for c, vc in value_counts.items():
        for value, k in vc.sort_values(ascending=False).head(8).items():
            add(table, f"{c} = {value}: % of rows", round(k / n * 100, 1))
    print("done:", table)

result = pd.DataFrame(rows)
result.to_csv(out("full_file_checks.csv"), index=False)
pd.set_option("display.max_rows", 200, "display.max_colwidth", 90)
print(result.to_string(index=False))
print(f"\nSaved {out('full_file_checks.csv')}")
