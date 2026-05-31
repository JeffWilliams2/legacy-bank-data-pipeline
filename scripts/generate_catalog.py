"""
Build target/catalog.json from the live DuckDB warehouse.

dbt docs generate requires dbt-core (not dbt-fusion). This script is a
drop-in replacement that reads the warehouse schema directly, so the dbt
docs site works without any additional dependencies.

Usage:
    python3 scripts/generate_catalog.py
    python3 -m http.server 8080 --directory target
    # then open http://localhost:8080
"""

import json
import os
import duckdb
from datetime import datetime, timezone

WAREHOUSE = os.path.join(os.path.dirname(__file__), "..", "warehouse.duckdb")
TARGET = os.path.join(os.path.dirname(__file__), "..", "target")
INDEX_URL = (
    "https://raw.githubusercontent.com/dbt-labs/dbt-core"
    "/v1.10.0/core/dbt/task/docs/index.html"
)


def build_catalog(con):
    rows = con.execute(
        """
        select c.table_schema, c.table_name, t.table_type,
               c.column_name, c.data_type, c.ordinal_position
        from information_schema.columns c
        join information_schema.tables t
          on c.table_schema = t.table_schema
         and c.table_name   = t.table_name
        where c.table_schema not in ('information_schema', 'pg_catalog')
        order by c.table_schema, c.table_name, c.ordinal_position
        """
    ).fetchall()

    nodes, sources = {}, {}
    for schema, table, ttype, col, dtype, pos in rows:
        is_source = schema == "raw"
        uid = (
            f"source.legacy_bank.{schema}_{table}"
            if is_source
            else f"model.legacy_bank.{table}"
        )
        bucket = sources if is_source else nodes
        if uid not in bucket:
            bucket[uid] = {
                "metadata": {
                    "type": "BASE TABLE" if ttype == "BASE TABLE" else "VIEW",
                    "schema": schema,
                    "name": table,
                    "database": None,
                    "comment": None,
                    "owner": None,
                },
                "columns": {},
                "stats": {},
                "unique_id": uid,
            }
        bucket[uid]["columns"][col.lower()] = {
            "type": dtype,
            "index": pos,
            "name": col.lower(),
            "comment": None,
        }

    return {
        "metadata": {
            "dbt_schema_version": (
                "https://schemas.getdbt.com/dbt/catalog/v1/upgrade.json"
            ),
            "dbt_version": "1.10.0",
            "generated_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "invocation_id": None,
            "env": {},
        },
        "nodes": nodes,
        "sources": sources,
        "errors": None,
    }


def ensure_index_html(target_dir):
    index_path = os.path.join(target_dir, "index.html")
    if os.path.exists(index_path):
        return
    import urllib.request
    print("Downloading dbt docs index.html …")
    urllib.request.urlretrieve(INDEX_URL, index_path)
    print("  saved to target/index.html")


def main():
    os.makedirs(TARGET, exist_ok=True)
    con = duckdb.connect(WAREHOUSE)
    catalog = build_catalog(con)

    catalog_path = os.path.join(TARGET, "catalog.json")
    with open(catalog_path, "w") as f:
        json.dump(catalog, f, indent=2)
    print(
        f"catalog.json written: "
        f"{len(catalog['nodes'])} nodes, {len(catalog['sources'])} sources"
    )

    ensure_index_html(TARGET)
    print("\nDocs ready. Run:")
    print("  python3 -m http.server 8080 --directory target")
    print("  open http://localhost:8080")


if __name__ == "__main__":
    main()
