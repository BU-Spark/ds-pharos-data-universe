"""
matching_utils.py

Shared helpers for the PF recipient EIN fuzzy-matching prototype (Milestone 2).

- normalize_name(): Python port of Curt's SQL norm() in match_recipient_eins.py,
  so names normalize identically in pandas and in Postgres.
- trigram_similarity(): Python port of Postgres pg_trgm similarity(), so our
  thresholds are on the same scale as Curt's 0.85 / 0.90 cutoffs.
- is_placeholder(): flags non-recipient text ("SEE ATTACHED", "VARIOUS", ...).
- categorize_rcpnt_ein(): buckets the rcpnt_ein column after Curt's pipeline.
"""

import re
import pandas as pd

# ---------------------------------------------------------------------------
# Name normalisation (mirrors norm() in match_recipient_eins.py, same order)
# ---------------------------------------------------------------------------
_SUFFIX_RE = re.compile(r"\s*(,?\s*(INC|CORP|LLC|LTD|INCORPORATED|CORPORATION))\s*$", re.I)
_ABBREV = [
    (re.compile(r"\bFNDTN\b|\bFDN\b"), "FOUNDATION"),
    (re.compile(r"\bUNIV\b"), "UNIVERSITY"),
    (re.compile(r"\bNATL\b"), "NATIONAL"),
    (re.compile(r"\bINTL\b"), "INTERNATIONAL"),
    (re.compile(r"\bASSN\b|\bASSOC\b"), "ASSOCIATION"),
    (re.compile(r"\bCNTR\b|\bCTR\b"), "CENTER"),
    (re.compile(r"\bHOSP\b"), "HOSPITAL"),
    (re.compile(r"\bSW\b"), "SOUTHWEST"),
    (re.compile(r"\bNW\b"), "NORTHWEST"),
    (re.compile(r"\bNE\b"), "NORTHEAST"),
    (re.compile(r"\bSE\b"), "SOUTHEAST"),
]
_THE_OR_WS_RE = re.compile(r"^THE\s+|\s+")


def normalize_name(name) -> str:
    """Normalise an org name for comparison. Same steps as Curt's SQL norm()."""
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return ""
    s = str(name).strip().upper()          # 1 upper + trim
    s = s.replace("'", "")                  # 2 apostrophes
    s = s.replace("&", " AND ")             # 3 ampersand
    s = re.sub(r"[.,\-/]", " ", s)          # 4 punctuation -> space
    s = _SUFFIX_RE.sub("", s, count=1)      # 5 trailing legal suffix
    for pat, rep in _ABBREV:                # 6 abbreviations
        s = pat.sub(rep, s)
    s = _THE_OR_WS_RE.sub(" ", s)           # 7 leading THE + collapse ws
    return s.strip()


_PAREN_PUNCT_RE = re.compile(r"[^A-Z0-9 ]+")


def normalize_task3_style(name) -> str:
    """Approximation of Task 3's name cleaning (as seen in rcp_name_norm):
    upper-case, & -> AND, drop apostrophes, every other non-alphanumeric -> space,
    drop an ATTN / C/O tail, strip trailing INC/CORP/LLC/LTD, strip a leading or
    trailing THE, collapse spaces. No abbreviation expansion.
    Only used to clean Schedule I names for the threshold sweep — swap in the
    teammate's own function from his Task 3 code for an exact match."""
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return ""
    s = str(name).upper().replace("'", "").replace("&", " AND ")
    s = _PAREN_PUNCT_RE.sub(" ", s)
    s = re.sub(r"\s+(ATTN|ATTENTION|C O)\s.*$", "", s)   # drop "ATTN ..." / "C/O ..." tails
    s = _SUFFIX_RE.sub("", s.strip(), count=1)
    s = re.sub(r"^THE\s+|\s+THE$", "", s.strip())
    return re.sub(r"\s+", " ", s).strip()


def normalize_series(s: pd.Series) -> pd.Series:
    """Vectorised-ish wrapper; caches repeated names (grant data repeats a lot)."""
    uniq = pd.Series(s.dropna().unique())
    mapping = dict(zip(uniq, uniq.map(normalize_name)))
    return s.map(mapping).fillna("")


# ---------------------------------------------------------------------------
# pg_trgm-equivalent trigram similarity
# ---------------------------------------------------------------------------
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _trigrams(s: str) -> frozenset:
    """pg_trgm: lowercase, split on non-alphanumerics, pad each word with
    two leading spaces and one trailing space, take all 3-char windows."""
    grams = set()
    for w in _NON_ALNUM_RE.split(s.lower()):
        if not w:
            continue
        p = "  " + w + " "
        grams.update(p[i:i + 3] for i in range(len(p) - 2))
    return frozenset(grams)


def trigram_similarity(a: str, b: str) -> float:
    """|A ∩ B| / |A ∪ B| over trigram sets — same as Postgres similarity()."""
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# ---------------------------------------------------------------------------
# Placeholder / non-recipient text
# ---------------------------------------------------------------------------
PLACEHOLDER_RE = re.compile(
    r"^\s*("
    r"SEE\b.*|.*\bATTACHED\b.*|.*\bATTACHMENT\b.*|SCHEDULE\b.*|STATEMENT\b.*"
    r"|VARIOUS\b.*|MISC(ELLANEOUS)?\b.*|NONE|N/?A|NA|OTHER|TOTAL( GRANTS.*)?|AS LISTED.*"
    r")\s*$",
    re.I,
)


def is_placeholder(name: str) -> bool:
    return bool(PLACEHOLDER_RE.match(name or ""))


# ---------------------------------------------------------------------------
# Bucket rcpnt_ein values written by Curt's pipeline
# ---------------------------------------------------------------------------
MARKERS = ("INDIVIDUAL", "FOREIGN", "GOVERNMENT")


def categorize_rcpnt_ein(ein: pd.Series) -> pd.Series:
    e = ein.fillna("").astype(str).str.strip()
    out = pd.Series("OTHER", index=e.index, dtype=object)
    out[e.str.fullmatch(r"\d{9}")] = "MATCHED"
    out[e == ""] = "UNMATCHED"
    for m in MARKERS:
        out[e == m] = m
    return out


def zip5(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().str[:5]


def upper_trim(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().str.upper()