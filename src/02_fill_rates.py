"""
Step 2 (Milestone 1): fill rate of every column in the working data dictionary.

Reads each table in chunks (the full files are too big to load at once) and
reports the share of rows where each selected column is filled, plus the
row count per tax year.

Output: outputs/full_file_fill_rates.csv
"""
import pandas as pd

from config import SELECTED_COLUMNS, find_csv, out

rows = []
for table, cols in SELECTED_COLUMNS.items():
    filled = pd.Series(0, index=cols)
    n = 0
    years = pd.Series(dtype=int)
    for chunk in pd.read_csv(find_csv(table), usecols=cols, dtype=str, chunksize=250_000):
        filled += chunk[cols].notna().sum()
        n += len(chunk)
        years = years.add(chunk[cols[1]].value_counts(), fill_value=0)   # cols[1] is the tax year
    print(f"{table}: {n:,} rows | tax years: {years.astype(int).to_dict()}")
    for c in cols:
        rows.append({"table": table, "column": c, "full_fill_pct": round(filled[c] / n * 100, 1)})

result = pd.DataFrame(rows)
result.to_csv(out("full_file_fill_rates.csv"), index=False)
print(f"\nSaved {out('full_file_fill_rates.csv')}")
