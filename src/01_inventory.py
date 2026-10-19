"""
Step 1 (Milestone 1): inventory the IRS extracts.

Prints the row and column count of every table and saves the first 5,000 rows
of each as a small sample (handy for exploring without loading the full files).

Output: outputs/samples/sample_<file>.csv
"""
import os

import pandas as pd

from config import SELECTED_COLUMNS, find_csv, out

os.makedirs(out("samples"), exist_ok=True)

for table in SELECTED_COLUMNS:
    path = find_csv(table)
    name = os.path.basename(path)
    sample = pd.read_csv(path, nrows=5000, dtype=str)
    sample.to_csv(out(os.path.join("samples", "sample_" + name)), index=False)
    rows = sum(len(c) for c in pd.read_csv(path, usecols=[0], dtype=str, chunksize=500_000))
    print(f"{name}: {rows:,} rows, {sample.shape[1]} columns")

print(f"\nSamples saved to {out('samples')}")
