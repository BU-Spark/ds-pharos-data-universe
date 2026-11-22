"""NTEE major-group letter -> map category (Task 4b). Shared by View 1 (density) and View 3 (nonprofit mix)."""
import pandas as pd

GROUPS = [
    ("Human services", "IJKLMOP", "Crime & legal (I), employment (J), food & nutrition (K), housing (L), "
                                   "public safety & disaster relief (M), youth development (O), human services (P)"),
    ("Health", "EFGH", "Health care (E), mental health (F), diseases & disorders (G), medical research (H)"),
    ("Education", "B", "Schools, colleges, libraries, PTAs and other education (B)"),
    ("Arts & culture", "A", "Arts, culture and humanities (A)"),
    ("Environment & animals", "CD", "Environment (C), animal-related (D)"),
    ("Recreation & sports", "N", "Recreation, sports and leisure (N)"),
    ("Religion", "X", "Religion-related (X)"),
    ("Community & philanthropy", "STW", "Community improvement (S), philanthropy & grantmaking (T), "
                                         "public & societal benefit (W)"),
    ("Other", "QRUVYZ", "International (Q), civil rights (R), science & technology (U), social science (V), "
                          "mutual & membership benefit (Y), unknown (Z)"),
]
UNKNOWN = "Unknown (no NTEE code)"

LETTER_TO_GROUP = {ch: name for name, letters, _ in GROUPS for ch in letters}


def category_map() -> pd.DataFrame:
    """One row per NTEE letter, for the data dictionary and for other teammates."""
    return pd.DataFrame([{"ntee_letter": ch, "category": name, "category_description": desc}
                         for name, letters, desc in GROUPS for ch in letters])


def categorize(ntee_cd: pd.Series) -> pd.Series:
    """NTEE code (e.g. 'K31') -> category. Blank, '0000' or unknown letters -> UNKNOWN."""
    letter = ntee_cd.fillna("").astype(str).str.strip().str.upper().str[:1]
    return letter.map(LETTER_TO_GROUP).fillna(UNKNOWN)
