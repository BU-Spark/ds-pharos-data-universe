"""Shared settings for New England filer geocoding (Milestone 4).

Generalizes the Milestone 2 MA geocoding (src/task1-ma-geocoding) to the six New England states.
All paths are relative to the repo root. Data files are not in the repo; get them from the team
Google Drive (see README).
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parents[1]
DATA_DIR = REPO_ROOT / "data"

RAW_DIR = DATA_DIR / "raw"                       # IRS header extracts + Census reference files
MA_PRIOR_GEOCODED = DATA_DIR / "outputs" / "ma_geocoding_result" / "ma_geocoded_all.csv"  # Milestone 2 MA results (reused)

OUTPUT_DIR = DATA_DIR / "outputs" / "ne_geocoding"
BATCH_DIR = OUTPUT_DIR / "census_batches"
RESULT_DIR = OUTPUT_DIR / "census_results"

# abbreviation -> (full name, state FIPS)
STATES = {
    "MA": ("MASSACHUSETTS", "25"),
    "CT": ("CONNECTICUT", "09"),
    "RI": ("RHODE ISLAND", "44"),
    "NH": ("NEW HAMPSHIRE", "33"),
    "VT": ("VERMONT", "50"),
    "ME": ("MAINE", "23"),
}
NAME_TO_ABBR = {name: abbr for abbr, (name, _) in STATES.items()}
ABBR_TO_FIPS = {abbr: fips for abbr, (_, fips) in STATES.items()}

# States already geocoded in Sprint 2; their Census results are reused, not resubmitted.
REUSE_PRIOR_RESULTS = {"MA"}

CENSUS_BENCHMARK = "Public_AR_Current"
CENSUS_VINTAGE = "ACS2024_Current"
BATCH_SIZE = 10_000  # Census batch geocoder limit per file

RAW_FILE = OUTPUT_DIR / "ne_addresses_raw.csv"
CLEAN_FILE = OUTPUT_DIR / "ne_addresses_cleaned.csv"


def normalize_state(value):
    """Return a two-letter New England abbreviation, or the cleaned input if not New England."""
    v = " ".join((value or "").split()).upper()
    return NAME_TO_ABBR.get(v, v)
