# Task 4: Fuzzy Matching and Final Match-Rate Table

Milestone 2, Pharos Intelligence: Extend the Data Universe (DS539, Fall 2026)

## What this does

Task 3 matched 990-PF grant recipients to EINs and handed the rows it couldn't match to Task 4. This folder
tries to match those rows by name similarity, then builds the final match-rate table and compares it with
Curt's ~80% benchmark.

## Results

For grants made by Massachusetts foundations:

- Task 3 matched 68,889 of 85,010 eligible rows (81.0%).
- Fuzzy matching added 469 rows, bringing it to 69,358 (81.6%), above the ~80% benchmark.

Eligible rows are all grant rows minus individuals, foreign recipients, "SEE ATTACHED" placeholders and rows
with no name. This matches Task 3's definition.

About 18% of eligible rows are still unmatched. Most have no close-enough name in the reference list. 801 are
grants to government bodies (towns, public schools, police), which usually have no nonprofit EIN, so they were
not fuzzy matched.

## How it works

Names are compared with Task 3's reference list of 4.3M names (BMF, Pub 78, 990 and 990-PF filers), using
Curt's tiers:

- F1: same ZIP, similarity at least 0.85
- F2: same 3-digit ZIP, similarity at least 0.85
- F3: same state, similarity at least 0.90

If two different EINs score almost the same, the row is left unmatched instead of guessing.

## How accurate it is

In a held-out test on Schedule I names, about 91% of matches at the 0.85 cutoff had the correct EIN. In a
hand-check of 150 matches, 146 were correct, 2 wrong and 2 unclear. The mistakes were look-alike organizations,
such as a high school matched to a scholarship fund for that school.

## How to run it

Download Task 3's three parquet files from the team Drive folder `pf_recipient_matching` into
`data/raw/pf_recipient_matching/`. They are too large for the repo.

```
python3 src/fuzzy_matching/fuzzy_match.py --sample filer_ma
python3 src/fuzzy_matching/match_rate_table.py --sample filer_ma
```

Results are written to `outputs/`. The table script ends with a few checks against Task 3's numbers, which
should all say OK.

## Files

- `fuzzy_match.py`: runs the fuzzy matching
- `match_rate_table.py`: builds the final match-rate table
- `matching_utils.py`: shared helper functions

## AI Disclosure
- Yanaal Niyazi: yanaal@bu.edu
- AI-C: I used Claude to help me understand the fuzzy matching task and how it fits with Task 3, to (first) draft small parts of the code in fuzzy_match.py and match_rate_table.py and to compare my match-rate numbers with my teammate’s results files. I reviewed each step before moving on and made the decisions on method and scope: using the client's tiers, leaving near-ties unmatched, and building the final table on Task 3’s output so our numbers line up. 
I ran all the code myself and checked the results: I hand-checked 150 fuzzy matches (146 correct), confirmed the table reproduces Task 3’s numbers exactly (90,906 rows, 85,010 eligible, 68,889 matched), and traced a mismatch with my teammate’s numbers to an assumption in an earlier version of my script, which I then fixed. I also looked into the 801 rows the fuzzy step skipped and confirmed they were government recipients before reporting the final 81.6%. 
- Tool: Claude 
