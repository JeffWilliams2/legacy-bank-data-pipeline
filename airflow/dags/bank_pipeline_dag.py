"""
bank_pipeline_dag.py
--------------------
Example Apache Airflow DAG that orchestrates the medallion pipeline on a
schedule in production.

Flow:  ingest (Airbyte) -> dbt seed/sources -> dbt run -> dbt test

The dbt test stage GATES publication: if data-quality tests fail, the run stops
and bad data never reaches the gold marts that feed reporting. This is the
standard "test before you publish" pattern.

This file documents the production orchestration story. It is illustrative --
running it requires an Airflow environment with the dbt project mounted.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

DBT_DIR = "/opt/airflow/dbt/legacy-bank-data-pipeline"

default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "depends_on_past": False,
}

with DAG(
    dag_id="legacy_bank_medallion_pipeline",
    description="Bronze -> Silver -> Gold pipeline for legacy bank migration",
    default_args=default_args,
    schedule="0 6 * * *",          # daily at 06:00
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["banking", "dbt", "medallion"],
) as dag:

    # 1. Ingest: in production, an Airbyte sync does CDC from the legacy
    #    PostgreSQL core system into the warehouse `raw` schema.
    #    (Locally this is replaced by `dbt seed`.)
    ingest = BashOperator(
        task_id="airbyte_cdc_ingest",
        bash_command='echo "Trigger Airbyte sync: postgres -> raw schema"',
    )

    # 2. Load raw sources (dbt seed stands in for the landed raw tables locally)
    load_sources = BashOperator(
        task_id="dbt_seed",
        bash_command=f"cd {DBT_DIR} && dbt seed",
    )

    # 3. Build all transformations bronze -> silver -> gold
    transform = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {DBT_DIR} && dbt run",
    )

    # 4. Quality gate: tests must pass before marts are considered published
    test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_DIR} && dbt test",
    )

    ingest >> load_sources >> transform >> test
