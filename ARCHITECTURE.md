# Architecture Guide

This document explains *why* the pipeline is built the way it is — the part
interviewers actually probe. Anyone can wire up dbt; the value is understanding
the design decisions.

---

## The medallion pattern

The pipeline uses the **medallion architecture**: data flows through three
quality tiers, each a named schema in the warehouse.

```
  ┌──────────┐   ┌──────────┐   ┌──────────┐
  │  BRONZE  │──▶│  SILVER  │──▶│   GOLD   │
  │  raw     │   │ cleaned  │   │  marts   │
  └──────────┘   └──────────┘   └──────────┘
   views          tables         tables
```

Why three layers instead of one big transform? **Separation of concerns and
auditability.** Each layer has one job, and you can inspect data at every stage
to find exactly where something went wrong.

---

## Bronze — raw landing (the audit trail)

**Materialized as views. No business logic. Ever.**

Bronze is an exact copy of what arrived from the source, plus audit metadata:

```sql
select
    *,
    '{{ source(...) }}' as _source_table,
    current_timestamp   as _loaded_at,
    '{{ invocation_id }}' as _batch_id
from {{ source(...) }}
```

**The key insight: bronze isn't a staging area you delete — it's your audit
trail.** In a regulated industry, being able to prove exactly what came out of
the source system, and when, isn't optional. If a regulator or auditor asks
"what did the core system report on March 4th," bronze is the answer. Every
transformation downstream is reproducible from it.

It's materialized as **views** because it's cheap, always reflects the latest
seed/ingest, and we don't query it directly in hot paths.

---

## Silver — cleaned & standardized

**Materialized as tables.** This is where the real data-engineering work lives,
because legacy banking exports are messy in specific, recurring ways:

### 1. Inconsistent date formats
The same logical date appears in four formats depending on which legacy
subsystem wrote the row:

| Format | Example |
|--------|---------|
| ISO | `2021-03-04` |
| US slash | `03/04/2021` |
| Oracle default | `04-Mar-2021` |
| Compact numeric | `20210304` |

The `parse_legacy_date` macro `COALESCE`s across all four using DuckDB's
`try_strptime` (which returns NULL instead of erroring on a mismatch). First
match wins. A `not_null` test on the output guarantees every date parsed —
**0 unparsed dates** in the sample run.

### 2. Dirty money strings
Balances and amounts arrive as strings, ~15% carrying a stray `$` and
thousands-commas (`"$12,345.67"`). The `clean_money` macro regex-strips
everything but digits, sign, and decimal point, then casts to `decimal(18,2)`.

### 3. Debit/credit sign convention — the important one
The source stores **every amount as a positive number.** Whether it's money in
or out is encoded separately in `txn_code`. You can't sum that to get a
balance. Silver derives `signed_amount`:

```sql
case when txn_code in ('DR','ATM','FEE','WIRE')
     then -1 * amount   -- money out
     else amount        -- money in
end as signed_amount
```

Now net flow and balances aggregate correctly. *(Verified: debit average is
negative, credit average positive.)* This is exactly the kind of domain rule a
generic engineer wouldn't know to apply.

### 4. Legacy code decoding
3-letter account-type codes (`CHK`, `SAV`, `MMA`, `CD`, `LOC`, `IRA`) are
decoded to human labels and tagged with a deposit/non-deposit flag (a line of
credit is not an insured deposit — that matters for FDIC math downstream).

---

## Gold — business-ready marts

**Materialized as tables**, each answering a specific business question. This
is where banking domain knowledge becomes the differentiator.

### `gold_aml_flags` — BSA/AML monitoring
Two classic patterns every bank must surface:

1. **CTR-reportable** — any single transaction over **$10,000** triggers a
   Currency Transaction Report under the Bank Secrecy Act.
2. **Structuring ("smurfing")** — multiple sub-$10,000 same-day deposits by one
   account that *aggregate* over the threshold: a deliberate attempt to evade
   CTR filing, itself a reportable red flag. Detected with a same-day
   `group by` where each transaction is individually under $10k but the daily
   sum clears it and there are ≥ 3 of them.

### `gold_fdic_coverage` — deposit-insurance exposure
FDIC insures deposits up to **$250,000** per depositor. This mart sums each
customer's insured-deposit accounts (excluding lines of credit), splits insured
vs. uninsured exposure, and flags customers over the limit — a figure treasury
and risk teams watch.

### `gold_customer_engagement` — retention scoring
A transparent, explainable 0–100 score from recency + frequency + product
breadth, bucketed into ACTIVE / PASSIVE / AT_RISK tiers.

### `gold_executive_summary` — portfolio rollup
Balances, account counts, and net transaction flow by branch and product — the
mart an executive opens first.

---

## Materialization strategy

| Layer | Materialization | Reasoning |
|-------|-----------------|-----------|
| Bronze | view | Cheap, always fresh, not in hot query paths |
| Silver | table | Queried repeatedly by many gold models; materialize once |
| Gold | table | Feeds BI tools that need fast, stable reads |

---

## Warehouse portability (DuckDB → Snowflake)

The transformations are **warehouse-agnostic**. Locally they run on DuckDB
(zero setup); in production the identical dbt models run on Snowflake by
switching the target in `profiles.yml`. Nothing in `models/` changes. This is
the core promise of dbt and a deliberate design choice so the project is both
*runnable today* and *production-credible*.

---

## Orchestration

`airflow/dags/bank_pipeline_dag.py` shows how this runs on a schedule in
production: ingest (Airbyte) → `dbt seed`/source-load → `dbt run` → `dbt test`,
with the test stage gating publication so bad data never reaches the gold marts.

---

## How I'd extend this next

- Incremental models on `silver_transactions` (process only new partitions)
- Snapshots (SCD Type 2) on accounts to track balance history over time
- `dbt source freshness` checks to alert on stale ingestion
- Great Expectations or `dbt-expectations` for richer data contracts
- A BI layer (Metabase/Power BI) reading the gold schema directly
