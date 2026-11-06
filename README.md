<h1 align="center">
  <br>
  <a href="https://www.bu.edu/spark/" target="_blank"><img src="https://www.bu.edu/spark/files/2023/08/logo.png" alt="BUSpark" width="200"></a>
  <br>
  Pharos Intelligence: Extend the Data Universe
  <br>
</h1>

<h4 align="center">Joining Census/ACS data onto Pharos Intelligence's IRS 990 database (BU Spark! DS539, Fall 2026)</h4>

<p align="center">
  <a href="#key-features">Key Features</a> •
  <a href="#how-to-use">How To Use</a> •
  <a href="#project-description">Project Description</a> •
  <a href="#data-locations">Data Locations</a>
</p>

> This README is a work in progress. It currently covers Milestones 1 and 2.

## Key Features

* `src/task1-ma-geocoding/` - Geocodes Massachusetts nonprofit addresses to Census tracts
* `src/task2-zip-fallback-acs/` - Places PO boxes and unmatched addresses by ZIP, joins ACS data, and calculates KPI 1 (nonprofits per 1,000 residents)
* `src/pf-recipient-matching/` - Matches 990-PF grant recipients to EINs using the IRS BMF and Pub 78
* `src/fuzzy_matching/` - Fuzzy-matches the remaining recipients and builds the final match-rate table

Each folder has its own README with more detail.

## How To Use

To clone and run this application, you'll need <a href="https://git-scm.com" target="_blank">Git</a>
From your command line:

```bash
# Clone this repository
$ git clone https://github.com/BU-Spark/ds-pharos-data-universe.git
```

Large data files are not in the repo. Download them from the team Google Drive and put them in `data/raw/`.

Create a new branch from dev, add changes on the new branch you just created.

You will want to look into <a href="https://git-scm.com/docs/git-branch" target="_blank">git branch</a> and <a href="https://git-scm.com/docs/git-checkout" target="_blank">git checkout</a>

```bash
# Create and Checkout a new branch if it doesn't exist
$ git checkout -b your-branch dev
```

Open a Pull Request to dev. Add your PM and TPM as reviewers.

At the end of the semester during project wrap up open a final Pull Request to main from dev branch.

## Project Description

Pharos Intelligence maintains a national Postgres database built from IRS 990 filings. A 990 alone can't show what is happening in the community a nonprofit serves. This project joins U.S. Census/ACS data onto the 990 data using EIN and location matching, then uses the joined data to build 2–3 descriptive views (for example, where nonprofits are concentrated compared to community economic need).

### Completed Milestones

**Milestone 1: Data Access, Schema Familiarization & Client Engagement**
* Met with the client to confirm scope
* Received the data extracts and data dictionary
* Chose Census/ACS as the main dataset to join

*AI Contribution (AI-C, Claude):* Claude helped explain the project and the IRS 990 data, prepare questions for the first client meeting, build the working data dictionary from samples of the data, and write the test script for pulling Census/ACS data. The team ran the code on the real data, checked the results, and made the final decisions on scope and dataset.

**Milestone 2: Entity-Matching Prototype**
* Geocoded MA nonprofit addresses to Census tracts, using ZIP as a fallback for PO boxes
* Joined ACS data for all MA tracts and calculated KPI 1
* Matched 990-PF grant recipients to EINs, reaching about 81.6% for MA foundation grants (client benchmark: ~80%)
* Documented where matching breaks down (PO boxes, individuals, foreign recipients, missing EINs)

*AI Contribution (AI-C, Claude):* Claude helped plan the Milestone 2 tasks and wrote and debugged the Python/Colab code for recipient matching, ZIP fallback, the ACS join and KPI 1. The team ran the code on the real data, reviewed the outputs, caught and fixed errors, and checked the match rates. More detail is in each task folder's README.

## Data Locations

* Google Drive: **BU Spark Data** folder
  - Raw IRS 990 data extracts from the client
* Google Drive: **Pharos Intelligence: Extend The Data Universe** folder
  - Team outputs and cleaned data
* IRS Business Master File and Publication 78
  - Used for EIN matching
* Census ACS 5-year API
  - Tract-level community data for Massachusetts
