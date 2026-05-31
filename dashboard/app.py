"""
Legacy Bank Pipeline · Streamlit Dashboard

Reads directly from warehouse.duckdb (the gold schema).
Run from the project root:
    streamlit run dashboard/app.py
"""

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

DB = Path(__file__).parent.parent / "warehouse.duckdb"

st.set_page_config(
    page_title="Legacy Bank Pipeline",
    page_icon="🏦",
    layout="wide",
)


@st.cache_data
def query(sql: str) -> pd.DataFrame:
    con = duckdb.connect(str(DB), read_only=True)
    return con.execute(sql).df()


if not DB.exists():
    st.error(
        "warehouse.duckdb not found. Run `dbt seed && dbt run` from the project root first."
    )
    st.stop()

# ── header ────────────────────────────────────────────────────────────────────
st.title("🏦 Legacy Bank Data Pipeline")
st.caption(
    "Medallion pipeline · bronze → silver → gold · "
    "dbt Core + DuckDB · [GitHub](https://github.com/jeffwilliams2/legacy-bank-data-pipeline)"
)

TIER_COLORS = {"ACTIVE": "#52b788", "PASSIVE": "#f4a261", "AT_RISK": "#e05252"}
FLAG_COLORS = {"CTR_OVER_10K": "#e05252", "STRUCTURING_SUSPECT": "#e08c52"}

tab_aml, tab_fdic, tab_exec, tab_eng = st.tabs(
    ["🚨 AML / BSA Monitoring", "🏛 FDIC Coverage", "📊 Branch Summary", "👥 Customer Engagement"]
)

# ── AML ───────────────────────────────────────────────────────────────────────
with tab_aml:
    st.subheader("BSA/AML Flag Summary")

    flags_summary = query(
        "select flag_type, count(*) as flags from gold.gold_aml_flags group by flag_type"
    )
    flags_detail = query(
        """
        select txn_id, account_id, txn_date::varchar as txn_date,
               amount, flag_type, flag_reason
        from gold.gold_aml_flags
        order by amount desc
        limit 200
        """
    )

    total = int(flags_summary["flags"].sum())
    ctr = int(flags_summary.loc[flags_summary["flag_type"] == "CTR_OVER_10K", "flags"].sum())
    struct = int(
        flags_summary.loc[flags_summary["flag_type"] == "STRUCTURING_SUSPECT", "flags"].sum()
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Flags", total)
    c2.metric("CTR Reportable (> $10k)", ctr)
    c3.metric("Structuring Suspect", struct)

    fig = px.bar(
        flags_summary,
        x="flag_type",
        y="flags",
        color="flag_type",
        color_discrete_map=FLAG_COLORS,
        labels={"flag_type": "Flag Type", "flags": "Count"},
        title="AML Flags by Type",
        text="flags",
    )
    fig.update_layout(showlegend=False, xaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Flagged Transaction Detail")
    st.dataframe(flags_detail, use_container_width=True, hide_index=True)

# ── FDIC ──────────────────────────────────────────────────────────────────────
with tab_fdic:
    st.subheader("FDIC Deposit Insurance Coverage")

    fdic = query(
        """
        select customer_id, full_name, risk_rating, deposit_account_count,
               total_deposits, fdic_insured_amount, uninsured_exposure,
               exceeds_fdic_limit
        from gold.gold_fdic_coverage
        order by uninsured_exposure desc
        """
    )

    over_limit = int(fdic["exceeds_fdic_limit"].sum())
    total_uninsured = fdic["uninsured_exposure"].sum()
    total_deposits = fdic["total_deposits"].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Customers Over $250k Limit", over_limit)
    c2.metric("Total Uninsured Exposure", f"${total_uninsured:,.0f}")
    c3.metric("Total Deposits", f"${total_deposits:,.0f}")

    top10 = fdic[fdic["uninsured_exposure"] > 0].head(10).copy()

    col_left, col_right = st.columns(2)

    with col_left:
        fig = px.bar(
            top10,
            x="customer_id",
            y="uninsured_exposure",
            color="risk_rating",
            labels={"customer_id": "Customer", "uninsured_exposure": "Uninsured ($)"},
            title="Top 10 Customers by Uninsured Exposure",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        totals_df = pd.DataFrame(
            {
                "category": ["FDIC Insured", "Uninsured Exposure"],
                "amount": [
                    fdic["fdic_insured_amount"].sum(),
                    total_uninsured,
                ],
            }
        )
        fig2 = px.pie(
            totals_df,
            values="amount",
            names="category",
            color="category",
            color_discrete_map={"FDIC Insured": "#52b788", "Uninsured Exposure": "#e05252"},
            title="Total Deposit Coverage Split",
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("All Customers")
    st.dataframe(
        fdic.assign(
            total_deposits=fdic["total_deposits"].map("${:,.2f}".format),
            fdic_insured_amount=fdic["fdic_insured_amount"].map("${:,.2f}".format),
            uninsured_exposure=fdic["uninsured_exposure"].map("${:,.2f}".format),
        ),
        use_container_width=True,
        hide_index=True,
    )

# ── Executive Summary ─────────────────────────────────────────────────────────
with tab_exec:
    st.subheader("Branch & Product Executive Summary")

    exec_df = query(
        """
        select branch_id, branch_name, state, account_type,
               account_count, total_balance, avg_balance, net_transaction_flow
        from gold.gold_executive_summary
        order by total_balance desc
        """
    )

    by_branch = (
        exec_df.groupby("branch_name", as_index=False)
        .agg(
            total_balance=("total_balance", "sum"),
            account_count=("account_count", "sum"),
            net_flow=("net_transaction_flow", "sum"),
        )
        .sort_values("total_balance", ascending=False)
    )
    by_type = exec_df.groupby("account_type", as_index=False).agg(
        total_balance=("total_balance", "sum")
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Deposits", f"${exec_df['total_balance'].sum():,.0f}")
    c2.metric("Total Accounts", int(exec_df["account_count"].sum()))
    c3.metric("Net Transaction Flow", f"${exec_df['net_transaction_flow'].sum():,.0f}")

    col_left, col_right = st.columns(2)

    with col_left:
        fig = px.bar(
            by_branch.head(12),
            x="total_balance",
            y="branch_name",
            orientation="h",
            color="total_balance",
            color_continuous_scale="Blues",
            labels={"total_balance": "Total Balance ($)", "branch_name": "Branch"},
            title="Total Balance by Branch",
        )
        fig.update_layout(
            yaxis={"categoryorder": "total ascending"},
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        fig2 = px.pie(
            by_type,
            values="total_balance",
            names="account_type",
            title="Balance Mix by Product Type",
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Full Detail")
    st.dataframe(exec_df, use_container_width=True, hide_index=True)

# ── Customer Engagement ───────────────────────────────────────────────────────
with tab_eng:
    st.subheader("Customer Engagement Scoring")

    eng = query(
        """
        select customer_id, full_name, age_years, account_count, txn_count,
               last_txn_date::varchar as last_txn_date,
               days_since_last_txn, engagement_score, engagement_tier
        from gold.gold_customer_engagement
        order by engagement_score desc
        """
    )

    tier_counts = eng["engagement_tier"].value_counts()

    c1, c2, c3 = st.columns(3)
    c1.metric("Active", int(tier_counts.get("ACTIVE", 0)))
    c2.metric("Passive", int(tier_counts.get("PASSIVE", 0)))
    c3.metric("At Risk", int(tier_counts.get("AT_RISK", 0)))

    col_left, col_right = st.columns(2)

    with col_left:
        tier_df = tier_counts.reset_index()
        tier_df.columns = ["tier", "count"]
        fig = px.bar(
            tier_df,
            x="tier",
            y="count",
            color="tier",
            color_discrete_map=TIER_COLORS,
            text="count",
            labels={"tier": "Engagement Tier", "count": "Customers"},
            title="Customers by Engagement Tier",
        )
        fig.update_layout(showlegend=False, xaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        fig2 = px.scatter(
            eng,
            x="days_since_last_txn",
            y="engagement_score",
            color="engagement_tier",
            color_discrete_map=TIER_COLORS,
            hover_data=["full_name", "txn_count", "account_count"],
            labels={
                "days_since_last_txn": "Days Since Last Transaction",
                "engagement_score": "Engagement Score (0–100)",
            },
            title="Score vs Recency",
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("At-Risk Customers (priority outreach list)")
    at_risk = eng[eng["engagement_tier"] == "AT_RISK"].sort_values(
        "days_since_last_txn", ascending=False
    )
    st.dataframe(at_risk, use_container_width=True, hide_index=True)
