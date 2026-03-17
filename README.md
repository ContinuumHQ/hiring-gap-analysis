# hiring-gap-analysis

An end-to-end data pipeline analyzing the IT skills gap in Germany compared to
other European countries. Built to answer one question: why does Germany
consistently report thousands of unfilled IT positions while rejecting
career changers who are fully capable of doing the work?

Data sources: Bundesagentur fuer Arbeit (official German job board API) and
Eurostat (EU-wide employment statistics). No API keys required.

---

## What this project does

1. Fetches live IT job postings from the Bundesagentur fuer Arbeit API
2. Pulls ICT employment and vacancy statistics from Eurostat for 7 countries
3. Cleans, merges and engineers features from both sources
4. Trains a polynomial regression model to forecast the skills gap 5 years ahead
5. Generates 4 analysis plots and a standalone HTML report

---

## Quickstart - runs on Linux, Windows and macOS

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
git clone https://github.com/ContinuumHQ/hiring-gap-analysis.git
cd hiring-gap-analysis
docker-compose up
```

Or locally with Python 3.10+:

```bash
pip install -r requirements.txt
python main.py
```

Skip the API fetch and use cached data:

```bash
python main.py --skip-fetch
```

---

## Project structure

```
hiring-gap-analysis/
- ingestion/
  - bundesagentur.py   - Bundesagentur API client with retry logic
  - eurostat.py        - Eurostat REST API client
- pipeline/
  - cleaner.py         - Data cleaning and standardization
  - features.py        - Feature engineering and aggregation
- model/
  - forecaster.py      - Polynomial regression forecasting model
- dashboard/
  - visualizer.py      - 4 analysis plots
  - report.py          - Standalone HTML report
- tests/               - 17 unit tests
- config.yaml          - All API endpoints and parameters
- main.py              - CLI entry point
- requirements.txt
- Dockerfile
- docker-compose.yml
```

---

## Countries analyzed

Germany (DE), Netherlands (NL), Ireland (IE), Estonia (EE),
Poland (PL), Norway (NO), Portugal (PT), EU average

---

## Key findings (updated on each run)

Outputs land in `docs/plots/` and `docs/reports/` after the pipeline runs.
The HTML report includes a country comparison indexed to Germany = 100,
showing how hiring flexibility differs across comparable EU labor markets.

---

## Error handling

Every API call implements retry logic with configurable attempts and delays.
HTTP 4xx errors are not retried. Parse errors are caught per-record so a
single malformed response does not abort the full pipeline. All errors are
logged to `pipeline.log`.

---

## Tech stack

Python 3.12 - pandas - scikit-learn - matplotlib - seaborn - requests - PyYAML

---

## Author

Raffaele Conti