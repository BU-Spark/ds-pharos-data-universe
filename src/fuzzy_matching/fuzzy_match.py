"""
fuzzy_match.py — fuzzy-match PF grant recipients to EINs (Task 4).

Inputs (data/raw/pf_recipient_matching/, from Task 3):
  pf_recipients_for_fuzzy.parquet   grant rows still missing an EIN
  reference_name_index.parquet      known org names + EIN + location

Tiers (Curt's cutoffs, pg_trgm similarity):
  F1 same ZIP >= 0.85 | F2 same 3-digit ZIP >= 0.85 | F3 same state >= 0.90
  Two different EINs within --margin -> AMBIGUOUS, no match.

Run:  python3 src/fuzzy_matching/fuzzy_match.py --sample filer_ma [--sweep]
      --sample filer_ma | recipient_ma | all
"""

import argparse
import glob
import logging
import os
import time

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

import sys
# config.py lives one folder up, in src/ — make it importable from src/fuzzy-matching/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from matching_utils import is_placeholder, normalize_task3_style, trigram_similarity

log = logging.getLogger("fuzzy")
OUT = config.OUTPUT_DIR

TOPK = 10            # shortlist size per recipient before exact trigram scoring
PRE_CUTOFF = 60      # rapidfuzz token_sort_ratio floor for the shortlist (0-100)
CHUNK = 256          # recipients per cdist call (memory: CHUNK x names in block)
MIN_NAME_LEN = 5     # don't fuzzy-match very short names


def find_file(name: str) -> str:
    hits = sorted(glob.glob(os.path.join(config.DATA_DIR, "**", name), recursive=True))
    if not hits:
        raise FileNotFoundError(f"{name} not found under {config.DATA_DIR}")
    return hits[0]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_pool(sample: str) -> pd.DataFrame:
    cols = ["row_id", "filer_ein", "taxyear", "line_number", "filer_state",
            "rcp_name_full", "rcp_name_norm", "rcp_city_n", "rcp_state_n", "rcp_zip5",
            "amount", "recipient_class", "match_method", "recipient_in_ma"]
    p = pd.read_parquet(find_file("pf_recipients_for_fuzzy.parquet"), columns=cols)
    for c in ["rcp_name_norm", "rcp_state_n", "rcp_zip5", "rcp_city_n"]:
        p[c] = p[c].fillna("").astype(str).str.strip()
    if sample == "filer_ma":
        p = p[p["filer_state"] == "MA"]
    elif sample == "recipient_ma":
        p = p[p["recipient_in_ma"]]
    return p


def load_reference() -> pd.DataFrame:
    r = pd.read_parquet(find_file("reference_name_index.parquet"))
    for c in ["name_norm", "state", "zip5", "city_norm", "ein"]:
        r[c] = r[c].fillna("").astype(str).str.strip()
    r = r[(r["name_norm"].str.len() >= 2) & (r["state"] != "") & r["ein"].str.fullmatch(r"\d{9}")]
    r = r.drop_duplicates(["name_norm", "state", "zip5", "ein"])
    log.info("Reference: %d rows, %d EINs  %s", len(r), r["ein"].nunique(),
             r["source"].value_counts().to_dict())
    return r


def recipients_to_match(pool: pd.DataFrame) -> pd.DataFrame:
    """Unique (name, state, ZIP) among ORGANIZATION rows that aren't placeholders."""
    org = pool[pool["recipient_class"] == "organization"].copy()
    org["is_placeholder"] = org["rcp_name_norm"].map(lambda s: s == "" or is_placeholder(s))
    q = (org[~org["is_placeholder"] & (org["rcp_state_n"] != "")]
         .drop_duplicates(["rcp_name_norm", "rcp_state_n", "rcp_zip5"])
         [["rcp_name_norm", "rcp_state_n", "rcp_zip5", "rcp_city_n", "rcp_name_full"]]
         .rename(columns={"rcp_name_norm": "name_norm", "rcp_state_n": "state", "rcp_zip5": "zip5"}))
    log.info("Pool rows: %d | organisations: %d | placeholders: %d | unique recipients to match: %d",
             len(pool), len(org), int(org["is_placeholder"].sum()), len(q))
    return q.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Shortlist + scoring
# ---------------------------------------------------------------------------
def shortlist(q_names: list, ref_names: np.ndarray) -> list:
    """For each query name, up to TOPK candidate reference names (rapidfuzz, all cores)."""
    out = []
    if len(ref_names) == 0:
        return [[] for _ in q_names]
    k = min(TOPK, len(ref_names))
    for i in range(0, len(q_names), CHUNK):
        qs = q_names[i:i + CHUNK]
        m = process.cdist(qs, ref_names, scorer=fuzz.token_sort_ratio, score_cutoff=PRE_CUTOFF,
                          dtype=np.uint8, workers=-1)
        # top-k largest scores per row (no negation: m is unsigned and would wrap)
        idx = np.argpartition(m, -k, axis=1)[:, -k:] if k < m.shape[1] else np.tile(np.arange(m.shape[1]), (len(qs), 1))
        for row, cand in zip(m, idx):
            out.append([ref_names[j] for j in cand if row[j] > 0])
    return out


def decide(q_name, q_zip, cands, by_name, tiers, margin):
    """cands: candidate names. Score every (name, ein, zip) row with pg_trgm and apply tiers."""
    scored = []
    for cname in cands:
        sim = trigram_similarity(q_name, cname)
        for ein, zp, src in by_name[cname]:
            scored.append((sim, cname, ein, zp, src))
    for tier, thr, geo_ok in tiers:
        pool = sorted((s for s in scored if geo_ok(q_zip, s[3]) and s[0] >= thr), reverse=True)
        if not pool:
            continue
        top = pool[0]
        rival = next((s for s in pool[1:] if s[2] != top[2]), None)
        if rival and top[0] - rival[0] < margin:
            return {"match_status": "AMBIGUOUS", "match_tier": tier, "best_trgm_seen": round(top[0], 4),
                    "rival_ein": rival[2]}
        return {"match_status": "MATCHED", "match_tier": tier, "matched_ein": top[2],
                "matched_name": top[1], "matched_zip5": top[3], "ref_source": top[4],
                "trgm_score": round(top[0], 4),
                "runner_up_score": round(rival[0], 4) if rival else None}
    best = max((s[0] for s in scored), default=None)
    return {"match_status": "BELOW_THRESHOLD" if scored else "NO_CANDIDATE",
            "best_trgm_seen": None if best is None else round(best, 4)}


def index_rows(ref_block: pd.DataFrame) -> dict:
    by = {}
    for n, e, z, s in zip(ref_block["name_norm"], ref_block["ein"], ref_block["zip5"], ref_block["source"]):
        by.setdefault(n, []).append((e, z, s))
    return by


def match_all(q: pd.DataFrame, ref: pd.DataFrame, t_zip, t_zip3, t_state, margin) -> pd.DataFrame:
    zip_tiers = [("F1_zip5", t_zip, lambda a, b: a != "" and a == b),
                 ("F2_zip3", t_zip3, lambda a, b: a != "" and b != "" and a[:3] == b[:3])]
    state_tier = [("F3_state", t_state, lambda a, b: True)]
    q = q.copy()
    q["zip3"] = q["zip5"].str[:3]
    ref = ref.assign(zip3=ref["zip5"].str[:3])
    results = [None] * len(q)
    t_all = time.time()
    for st, qs in q.groupby("state"):
        t0 = time.time()
        rs = ref[ref["state"] == st]
        # --- F1/F2 inside ZIP3 blocks ---------------------------------------
        rz = rs[rs["zip3"] != ""]
        rz_groups = {z: g for z, g in rz.groupby("zip3")}
        for z3, qz in qs[qs["zip3"] != ""].groupby("zip3"):
            block = rz_groups.get(z3)
            if block is None:
                continue
            names = block["name_norm"].unique()
            by = index_rows(block)
            cands = shortlist(qz["name_norm"].tolist(), names)
            for i, nm, zp, cs in zip(qz.index, qz["name_norm"], qz["zip5"], cands):
                if len(nm) >= MIN_NAME_LEN and cs:
                    results[i] = decide(nm, zp, cs, by, zip_tiers, margin)
        # --- F3 over the whole state, for those still open ------------------
        todo = [i for i in qs.index if len(q.at[i, "name_norm"]) >= MIN_NAME_LEN
                and (results[i] is None or results[i]["match_status"] in ("BELOW_THRESHOLD", "NO_CANDIDATE"))]
        if todo and len(rs):
            names = rs["name_norm"].unique()
            by = index_rows(rs)
            cands = shortlist(q.loc[todo, "name_norm"].tolist(), names)
            for i, cs in zip(todo, cands):
                if cs:
                    r = decide(q.at[i, "name_norm"], q.at[i, "zip5"], cs, by, state_tier, margin)
                    if r["match_status"] != "BELOW_THRESHOLD" or results[i] is None:
                        results[i] = r
        log.info("  %s: %d recipients, %d ref rows, %.1fs", st, len(qs), len(rs), time.time() - t0)
    log.info("Matching done in %.1f min", (time.time() - t_all) / 60)
    res = pd.DataFrame([r or {"match_status": "NO_CANDIDATE"} for r in results])
    return pd.concat([q.drop(columns="zip3"), res], axis=1)


# ---------------------------------------------------------------------------
# Threshold sweep on Schedule I (filer-reported recipient EINs)
# ---------------------------------------------------------------------------
def threshold_sweep(ref, state, margin, n=3000, seed=42) -> pd.DataFrame:
    cols = ["si_02_grant_us_org_name_l1", "si_02_grant_us_org_addr_state",
            "si_02_grant_us_org_addr_zip", "si_02_grant_us_org_ein"]
    si = pd.read_csv(config.find_csv("si_p02_t01_grants_us_orgs_govts"), dtype=str, usecols=cols)
    si = pd.DataFrame({"rcp_name_full": si[cols[0]].fillna(""),
                       "state": si[cols[1]].fillna("").str.strip().str.upper(),
                       "zip5": si[cols[2]].fillna("").str.strip().str[:5],
                       "true_ein": si[cols[3]].fillna("").str.strip()})
    si = si[si["true_ein"].str.fullmatch(r"\d{9}") & (si["state"] == state)]
    si["name_norm"] = si["rcp_name_full"].map(normalize_task3_style)
    si = si[(si["name_norm"].str.len() >= MIN_NAME_LEN) & ~si["name_norm"].map(is_placeholder)]
    si = si.drop_duplicates(["name_norm", "state", "zip5"])
    # Test only names that EXACT matching would miss — that's the fuzzy tiers' job
    exact = set(zip(ref["name_norm"], ref["state"]))
    si = si[[(a, b) not in exact for a, b in zip(si["name_norm"], si["state"])]]
    si["findable"] = si["true_ein"].isin(set(ref.loc[ref["state"] == state, "ein"]))
    si = si.sample(min(n, len(si)), random_state=seed).reset_index(drop=True)
    si["rcp_city_n"] = ""
    log.info("Sweep: %d held-out Schedule I names in %s (%d findable)", len(si), state, si["findable"].sum())

    # Score once at the loosest cutoff, then re-apply tiers per threshold
    base = match_all(si, ref, 0.60, 0.60, 0.60, margin)
    for c in ["trgm_score", "matched_ein"]:
        if c not in base:
            base[c] = None
    rows = []
    for thr in [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]:
        ok = (base["match_status"] == "MATCHED") & (base["trgm_score"].fillna(0) >= thr)
        m = base[ok]
        correct = int((m["matched_ein"] == m["true_ein"]).sum())
        rows.append({"threshold": thr, "tested": len(base), "matched": len(m), "correct": correct,
                     "precision": round(correct / len(m), 4) if len(m) else None,
                     "coverage_of_tested": round(len(m) / len(base), 4),
                     "recall_of_findable": round(correct / max(int(base["findable"].sum()), 1), 4)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="filer_ma", choices=["filer_ma", "recipient_ma", "all"])
    ap.add_argument("--t-zip", type=float, default=0.85)
    ap.add_argument("--t-zip3", type=float, default=0.85)
    ap.add_argument("--t-state", type=float, default=0.90)
    ap.add_argument("--margin", type=float, default=0.03)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--sweep-state", default="MA")
    ap.add_argument("--review-n", type=int, default=150)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ref = load_reference()
    if a.sweep:
        sw = threshold_sweep(ref, a.sweep_state, a.margin)
        sw.to_csv(os.path.join(OUT, "threshold_sweep.csv"), index=False)
        print(sw.to_string(index=False))

    q = recipients_to_match(load_pool(a.sample))
    res = match_all(q, ref, a.t_zip, a.t_zip3, a.t_state, a.margin)
    res.to_csv(os.path.join(OUT, f"fuzzy_matches_{a.sample}.csv"), index=False)

    m = res[res["match_status"] == "MATCHED"]
    rev = m.sample(min(a.review_n, len(m)), random_state=7)[
        ["rcp_name_full", "name_norm", "state", "zip5", "matched_name", "matched_ein",
         "match_tier", "trgm_score", "ref_source"]].assign(is_correct="")
    rev.to_csv(os.path.join(OUT, f"fuzzy_review_sample_{a.sample}.csv"), index=False)
    print(res["match_status"].value_counts().to_string())
    print(m["match_tier"].value_counts().to_string())


if __name__ == "__main__":
    main()