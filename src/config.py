"""
Shared settings for every script in src/.

Where the data lives is set with environment variables, so the same code runs
on a laptop, in Colab, or on the SCC without editing any file:

    PHAROS_DATA_DIR    folder holding Curt's 10 IRS CSV extracts (searched recursively)
                       default: data/raw/ inside the repo
    PHAROS_OUTPUT_DIR  where scripts write their results
                       default: outputs/ inside the repo
    CENSUS_API_KEY     free key from https://api.census.gov/data/key_signup.html
                       (only needed by 04_acs_pull.py)

The data and outputs folders are listed in .gitignore, so nothing in them is
ever pushed to GitHub.
"""
import glob
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("PHAROS_DATA_DIR", os.path.join(ROOT, "data", "raw"))
OUTPUT_DIR = os.environ.get("PHAROS_OUTPUT_DIR", os.path.join(ROOT, "outputs"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Regex used to flag PO boxes in street address fields
PO_BOX = r"P\.?\s*O\.?\s*BOX|POST OFFICE BOX"


def all_csvs():
    """Every CSV under DATA_DIR, in any subfolder."""
    return sorted(glob.glob(os.path.join(DATA_DIR, "**", "*.csv"), recursive=True))


def find_csv(table):
    """Path to the extract for one table, e.g. find_csv('f9_p00_t00_header')."""
    hits = [p for p in all_csvs() if table + "_2024_2025" in os.path.basename(p)]
    if not hits:
        raise FileNotFoundError(
            f"No CSV for table '{table}' under {DATA_DIR}. "
            f"Set PHAROS_DATA_DIR to the folder holding the IRS extracts. "
            f"CSVs found: {[os.path.basename(p) for p in all_csvs()]}")
    return hits[0]


def out(filename):
    """Full path for an output file."""
    return os.path.join(OUTPUT_DIR, filename)


# The 10 IRS tables we use, and the columns we keep from each
# (the working data dictionary in Drive explains every column).
SELECTED_COLUMNS = {
    "f9_p00_t00_header": [
        "f9_00_org_ein", "f9_00_tax_year", "f9_00_return_type", "f9_00_org_name_l1",
        "f9_00_org_name_l2", "f9_00_org_name_dba_l1", "f9_00_exempt_stat_501c3_x",
        "f9_00_org_addr_l1", "f9_00_org_addr_l2", "f9_00_org_addr_city",
        "f9_00_org_addr_state", "f9_00_org_addr_zip", "f9_00_org_addr_cntr",
        "f9_00_tax_period_begin_date", "f9_00_tax_period_end_date",
        "f9_00_return_amended_x", "f9_00_return_final_x"],
    "f9_p01_t00_summary": [
        "f9_00_org_ein", "f9_00_tax_year", "f9_01_act_gvrn_act_mission",
        "f9_01_act_gvrn_empl_tot", "f9_01_act_gvrn_vol_tot", "f9_01_rev_tot_cy",
        "f9_01_exp_tot_cy", "f9_01_exp_grant_similar_cy"],
    "f9_p03_t00_mission": [
        "f9_00_org_ein", "f9_00_tax_year", "f9_03_org_mission_purpose"],
    "f9_p10_t00_balance_sheet": [
        "f9_00_org_ein", "f9_00_tax_year", "f9_10_asset_tot_eoy",
        "f9_10_liab_tot_eoy", "f9_10_nafb_tot_eoy"],
    "si_p02_t01_grants_us_orgs_govts": [
        "f9_00_org_ein", "f9_00_tax_year", "line_number", "si_02_grant_us_org_name_l1",
        "si_02_grant_us_org_name_l2", "si_02_grant_us_org_ein", "si_02_grant_us_org_addr_l1",
        "si_02_grant_us_org_addr_city", "si_02_grant_us_org_addr_state",
        "si_02_grant_us_org_addr_zip", "si_02_grant_us_org_irc_section",
        "si_02_grant_us_org_amt_cash", "si_02_grant_us_org_amt_noncsh",
        "si_02_grant_us_org_purpose"],
    "pf_p00_t00_header": [
        "ein", "taxyear", "nameoffoundation", "operatingfoundation", "numberandstreet",
        "cityortown", "stateorprovince", "zipcode", "country", "taxperiodbeginning",
        "taxperiodending", "amnddrtrnind", "fnlrtrnind", "fmvasstseoyamt"],
    "pf_p01_t00_analysisofrevenueandexpenses": [
        "ein", "taxyear", "cntrrcvdrvandexpnssamt", "ttlrvandexpnssamt",
        "ttlexpnssrvandexpnssamt", "cntrpdrvandexpnssamt"],
    "pf_p02_t00_balancesheets": [
        "ein", "taxyear", "ttlasstseoyamt", "ttllbltseoyamt", "ttntastorfndblncseoyamt"],
    "pf_p08a_t00_summaryofdirectcharitableactivities": [
        "ein", "taxyear", "dscrptn1txt", "expnss1amt"],
    "pf_p14_t03_supplementaryinformation": [
        "ein", "taxyear", "line_number", "rcpnt_ein", "rcpntbsnssnm_bsnssnmln1txt",
        "rcpntbsnssnm_bsnssnmln2txt", "grntorcntrbtnpddryr_rcpntprsnnm",
        "rcpntusaddrss_addrssln1txt", "rcpntusaddrss_ctynm", "rcpntusaddrss_sttabbrvtncd",
        "rcpntusaddrss_zipcd", "rcpntfrgnaddrss_cntrycd",
        "grntorcntrbtnpddryr_rcpntfndtnsttstxt", "grntorcntrbtnpddryr_amt",
        "grntorcntrbtnpddryr_grntorcntrbtnprpstxt"],
}
