# Setup & Quickstart

Get the full pipeline running locally in about two minutes. No cloud account,
no Docker, no credentials.

---

## Prerequisites

- Python 3.9+
- pip

That's it. DuckDB is embedded (no server to install).

---

## 1. Install

```bash
pip install dbt-duckdb
```

This pulls in dbt Core and the DuckDB adapter together.

---

## 2. Generate the sample data

```bash
cd scripts
python generate_data.py
cd ..
```

This writes four CSVs into `seeds/` — the simulated "legacy export":
`raw_accounts.csv`, `raw_transactions.csv`, `raw_customers.csv`,
`raw_branches.csv`. The data is deliberately messy (mixed date formats, dirty
money strings, legacy codes) and is reproducible (fixed random seed).

---

## 3. Point dbt at the project's profile

```bash
export DBT_PROFILES_DIR=$(pwd)      # macOS / Linux
# Windows PowerShell:  $env:DBT_PROFILES_DIR = (Get-Location).Path
```

`profiles.yml` lives in the project root and is preconfigured for DuckDB.

---

## 4. Build and test

```bash
dbt seed     # load raw CSVs into the warehouse (the bronze sources)
dbt run      # build all bronze → silver → gold models
dbt test     # run 14 data-quality tests
```

Expected: `dbt run` → `PASS=12`, `dbt test` → `PASS=14`. A
`warehouse.duckdb` file appears in the project root — that's your warehouse.

---

## 5. Explore the results

Any DuckDB client works. Quick Python check:

```python
import duckdb
con = duckdb.connect("warehouse.duckdb")

# AML red flags
con.sql("select flag_type, count(*) from gold.gold_aml_flags group by 1").show()

# FDIC uninsured exposure
con.sql("""
  select customer_id, total_deposits, uninsured_exposure
  from gold.gold_fdic_coverage
  where exceeds_fdic_limit
  order by uninsured_exposure desc limit 10
""").show()
```

Or install the DuckDB CLI and run `duckdb warehouse.duckdb` then query the
`bronze`, `silver`, and `gold` schemas directly.

---

## 6. (Optional) Generate the docs site

dbt can auto-generate browsable documentation with a lineage graph — great for
a portfolio screenshot.

> **Note:** `dbt docs generate` is not supported by dbt-fusion (the binary at
> `/Users/<you>/.local/bin/dbt`). Use the script below instead — it generates
> `catalog.json` directly from the warehouse with no extra dependencies.

```bash
python3 scripts/generate_catalog.py
python3 -m http.server 8080 --directory target
# open http://localhost:8080
```

`generate_catalog.py` will also download `target/index.html` from the
dbt-core GitHub repo on first run (requires internet). After that everything
runs offline.

The lineage graph (source → bronze → silver → gold) is a strong visual to
screenshot for LinkedIn.

---

## Swapping to Snowflake (the production target)

The whole point of dbt: the models don't change, only the connection.

1. `pip install dbt-snowflake`
2. In `profiles.yml`, uncomment the `prod:` block and set `target: prod`.
3. Provide credentials via environment variables:
   ```bash
   export SNOWFLAKE_ACCOUNT=your_account
   export SNOWFLAKE_USER=your_user
   export SNOWFLAKE_PASSWORD=your_password
   ```
4. Load the seeds (`dbt seed`) or, in a real migration, replace the seeds with
   an **Airbyte** connector doing CDC from PostgreSQL into the `raw` schema.
5. `dbt run && dbt test` — identical commands, now running in the cloud.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Could not find profile` | Make sure `DBT_PROFILES_DIR` points at the project root (where `profiles.yml` is). |
| `schema "raw" does not exist` | Run `dbt seed` before `dbt run`. |
| Want a clean rebuild | Delete `warehouse.duckdb`, then re-run seed/run/test. |
