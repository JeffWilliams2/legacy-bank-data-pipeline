# Legacy Bank Data Migration Pipeline

[![Pipeline CI](https://github.com/JeffWilliams2/legacy-bank-data-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/JeffWilliams2/legacy-bank-data-pipeline/actions/workflows/ci.yml)
![dbt](https://img.shields.io/badge/dbt-1.10-orange?logo=dbt)
![DuckDB](https://img.shields.io/badge/DuckDB-embedded-yellow?logo=duckdb)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)
![Tests](https://img.shields.io/badge/dbt%20tests-14%20passing-brightgreen)
![Models](https://img.shields.io/badge/models-12%20passing-brightgreen)

A production-style **medallion (bronze → silver → gold)** data pipeline that
migrates a legacy core-banking dataset into a modern warehouse and produces
regulatory-reporting and analytics marts — including **BSA/AML monitoring**,
**FDIC deposit-insurance coverage**, and **executive reporting**.

> **Runs locally in under 2 minutes on DuckDB — no cloud account needed —**
> and the same dbt models deploy to Snowflake by changing a single profile.

---

## Why this project

Banks and financial institutions run legacy PostgreSQL/Oracle core systems and
are migrating to cloud warehouses (Snowflake, Databricks) for regulatory
reporting and analytics. This pipeline simulates that migration end to end and
implements the domain logic that makes banking data hard: dirty legacy formats,
debit/credit sign conventions, and compliance rules like the $10,000 CTR
threshold and structuring detection.

**Domain context informed by frontline financial-services experience at
JPMorgan Chase and Charles Schwab.** *(Roles were in financial operations /
client service; the engineering here is my own.)*

---

## Architecture

```
Legacy PostgreSQL              ┌─────────── dbt Core ───────────┐
(accounts, transactions,  ──▶  │  BRONZE  →  SILVER  →  GOLD     │  ──▶  BI / Reporting
 customers, branches)          │  (raw)   (cleaned)  (marts)     │       (dashboards)
        │                      └────────────────────────────────┘
   Airbyte CDC ingestion              orchestrated by Airflow
```

| Layer  | Purpose | What happens here |
|--------|---------|-------------------|
| **Bronze** | Raw landing / audit trail | Exact source copy + audit metadata (`_loaded_at`, `_batch_id`). No transforms. |
| **Silver** | Cleaned & standardized | Parse 4 messy date formats, strip `$`/commas from money, decode legacy account-type codes, derive signed transaction amounts. |
| **Gold** | Business-ready marts | AML/BSA flags, FDIC coverage, customer engagement scoring, executive summary. |

Full detail in **[ARCHITECTURE.md](ARCHITECTURE.md)**.

---

## What it produces (verified output on the sample data)

- **AML monitoring** — 30 CTR-reportable transactions (> $10,000) and 15
  structuring clusters (multiple sub-$10k same-day credits aggregating over the
  threshold) automatically flagged.
- **FDIC coverage** — per-customer insured vs. uninsured deposit exposure
  against the $250,000 limit.
- **Customer engagement** — transparent 0–100 score with ACTIVE / PASSIVE /
  AT_RISK tiers.
- **Executive summary** — balances, account counts, and net transaction flow
  by branch and product.

All **14 data-quality tests pass** (uniqueness, not-null, referential
integrity, accepted values).

---

## Sample output (verified on synthetic dataset)

**AML flags**
```
┌─────────────────────┬───────┐
│      flag_type      │ count │
├─────────────────────┼───────┤
│ CTR_OVER_10K        │    30 │
│ STRUCTURING_SUSPECT │    15 │
└─────────────────────┴───────┘
```

**FDIC uninsured exposure — top customers**
```
┌─────────────┬────────────────┬────────────────────┐
│ customer_id │ total_deposits │ uninsured_exposure │
├─────────────┼────────────────┼────────────────────┤
│ CUST00790   │  1,299,713.01  │      1,049,713.01  │
│ CUST00654   │  1,284,083.74  │      1,034,083.74  │
│ CUST00068   │  1,282,488.95  │      1,032,488.95  │
│ CUST00756   │  1,272,589.61  │      1,022,589.61  │
└─────────────┴────────────────┴────────────────────┘
```

**Customer engagement sample**
```
┌─────────────┬───────────────┬───────────┬─────────────────────┬──────────────────┬─────────────────┐
│ customer_id │   full_name   │ age_years │ days_since_last_txn │ engagement_score │ engagement_tier │
├─────────────┼───────────────┼───────────┼─────────────────────┼──────────────────┼─────────────────┤
│ CUST00790   │ Patricia Kim  │        72 │                 153 │             69.2 │ PASSIVE         │
│ CUST00184   │ Carlos Nguyen │        51 │                 152 │             66.6 │ PASSIVE         │
└─────────────┴───────────────┴───────────┴─────────────────────┴──────────────────┴─────────────────┘
```

---

## Lineage graph (dbt docs)

![Lineage graph: raw sources → bronze → silver → gold marts](lineage_graph.png)

The full **source → bronze → silver → gold** lineage is browsable via the dbt
docs site. To launch it locally:

```bash
# 1. Generate catalog.json from the live warehouse
python3 scripts/generate_catalog.py

# 2. Serve the docs site
python3 -m http.server 8080 --directory target
# then open http://localhost:8080
```

> **Note:** The `dbt docs generate` command requires dbt-core (not dbt-fusion).
> `scripts/generate_catalog.py` is a drop-in that builds `catalog.json` directly
> from the DuckDB warehouse — no extra install needed.

---

## Tech stack

| Tool | Role | In this repo |
|------|------|--------------|
| **dbt Core** | Transformations (bronze/silver/gold) | ✅ fully implemented |
| **DuckDB** | Local warehouse (runs instantly) | ✅ default target |
| **Snowflake** | Cloud warehouse | ✅ profile ready (one-file swap) |
| **Airbyte** | CDC ingestion from PostgreSQL | 📋 documented migration path |
| **Apache Airflow** | Orchestration | ✅ example DAG included |
| **Python / SQL** | Data generation + transforms | ✅ throughout |

> **Note on simulated data:** all data is synthetic, generated by
> `scripts/generate_data.py`. No real customer data is used — appropriate for a
> regulated domain, and the generator deliberately injects the kind of "mess"
> (inconsistent dates, dirty money strings, legacy codes) a real export has.

---

## Quickstart

See **[SETUP.md](SETUP.md)** for the full walkthrough. The short version:

```bash
pip install dbt-duckdb
cd scripts && python generate_data.py && cd ..
export DBT_PROFILES_DIR=$(pwd)
dbt seed && dbt run && dbt test
```

Then explore the gold marts in any DuckDB client (`warehouse.duckdb`), or
launch the dashboard:

```bash
pip install streamlit plotly pandas
streamlit run dashboard/app.py
```

---

## Repository layout

```
legacy-bank-data-pipeline/
├── README.md                 ← you are here
├── ARCHITECTURE.md           ← deep dive on the medallion design
├── SETUP.md                  ← step-by-step run guide + Snowflake swap
├── dbt_project.yml
├── profiles.yml              ← DuckDB (default) + Snowflake (commented)
├── scripts/
│   ├── generate_data.py      ← synthetic messy banking data
│   └── generate_catalog.py   ← builds target/catalog.json for dbt docs site
├── dashboard/
│   └── app.py                ← Streamlit dashboard (AML · FDIC · branches · engagement)
└── .github/
    └── workflows/
        └── ci.yml            ← GitHub Actions: seed → run → test on every push
├── seeds/                    ← generated raw CSVs (the "legacy export")
├── macros/                   ← date parsing, money cleaning, code decoding
├── models/
│   ├── bronze/               ← raw landing + audit metadata
│   ├── silver/               ← cleaned & standardized
│   └── gold/                 ← AML, FDIC, engagement, exec summary
└── airflow/
    └── dags/                 ← example orchestration DAG
```
