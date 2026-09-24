# ============================================================
# E-COMMERCE BI MONITORING DASHBOARD — Streamlit
# ============================================================
# 5 sections (BI-project mapping of the ML template's dashboard):
#   1. Alerts & Monitoring        (was: real-time alerts)
#   2. Seller Leaderboard         (was: Champion vs Challenger)
#   3. Executive KPIs + charts    (was: KPIs + charts)
#   4. KPI Trend / Anomaly Panel  (was: PSI drift)
#   5. Recent Orders Feed         (was: recent predictions)
# ============================================================

import os
import sys
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import DB_PATH
from src import kpi_queries as kq
from src import metrics, evaluation

st.set_page_config(page_title="E-Commerce BI Dashboard", layout="wide")

st.title("📊 E-Commerce Business Intelligence Dashboard")
st.caption("Olist Brazilian E-Commerce · 100K orders · 2016–2018")

if not os.path.exists(DB_PATH):
    # Streamlit Cloud has no separate "build step" like Render does — so on
    # first load (or if the DB is missing for any reason) the dashboard
    # builds it itself from data/sample/ (or RAW_DATA_DIR, e.g. locally).
    with st.spinner("First run — building database from sample dataset..."):
        from src.data_loader import load_raw_tables, validate_raw_tables, parse_order_dates
        from src.data_quality_check import run_data_quality_gate
        from src.db_builder import build_database

        try:
            tables = load_raw_tables()
            validate_raw_tables(tables)
            tables["orders"] = parse_order_dates(tables["orders"])
            run_data_quality_gate(tables, fail_hard=False)
            build_database(tables)
        except Exception as e:
            st.error(f"Could not build the database automatically: {e}")
            st.info("Locally, run `python scripts/build_database.py` first.")
            st.stop()


# ============================================================
# SECTION 1 — ALERTS & MONITORING
# ============================================================

st.header("🚨 Alerts & Monitoring")

checks = evaluation.run_all_monitoring_checks()
col1, col2, col3 = st.columns(3)
col1.metric("Total Active Alerts", checks["total_alerts"])
col2.metric("At-Risk Sellers", checks["at_risk_seller_count"])
sla = checks["sla_alert"]
col3.metric(
    "Late Delivery Rate",
    f"{sla.get('late_pct', 0)}%",
    delta=f"threshold {sla.get('threshold_pct', 0)}%",
    delta_color="inverse",
)

if checks["revenue_anomalies"]:
    st.warning(f"{len(checks['revenue_anomalies'])} month(s) show revenue swings beyond threshold:")
    st.dataframe(pd.DataFrame(checks["revenue_anomalies"]), width='stretch')
else:
    st.success("No revenue anomalies detected in the monitored period.")

st.divider()


# ============================================================
# SECTION 2 — SELLER LEADERBOARD
# ============================================================

st.header("🏆 Seller Leaderboard")

leaderboard = kq.seller_leaderboard()
st.dataframe(leaderboard.head(20), width='stretch')

at_risk = kq.at_risk_sellers()
with st.expander(f"⚠️ At-risk sellers ({len(at_risk)}) — avg review score < 3"):
    st.dataframe(at_risk, width='stretch')

st.divider()


# ============================================================
# SECTION 3 — EXECUTIVE KPIs + CHARTS
# ============================================================

st.header("📈 Executive KPIs")

summary = metrics.executive_summary()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Revenue", f"R$ {summary['total_revenue']:,.0f}")
c2.metric("Total Orders", f"{summary['total_orders']:,}")
c3.metric("Avg Order Value", f"R$ {summary['avg_order_value']:.2f}")
c4.metric("Repeat Purchase Rate", f"{summary['repeat_purchase_pct']}%")

monthly = kq.monthly_revenue()
st.subheader("Monthly Revenue Trend")
st.line_chart(monthly.set_index("month")["gross_revenue"])

top_cat = kq.top_categories(10)
st.subheader("Top 10 Categories by Revenue")
st.bar_chart(top_cat.set_index("category")["product_revenue"])

st.divider()


# ============================================================
# SECTION 4 — KPI TREND / ANOMALY PANEL  (PSI-drift equivalent)
# ============================================================

st.header("📉 KPI Trend & Anomaly Panel")

delivery_trend = kq.delivery_trend_monthly()
st.subheader("Delivery Performance Over Time")
st.line_chart(delivery_trend.set_index("month")[["avg_delivery_days", "late_pct"]])

rfm_summary = kq.rfm_segment_summary()
st.subheader("Customer RFM Segments")
st.bar_chart(rfm_summary.set_index("rfm_segment")["customers"])

st.divider()


# ============================================================
# SECTION 5 — RECENT ORDERS FEED (from live simulation, if running)
# ============================================================

st.header("🕒 Recent Orders Feed")

sim_log_path = "logs/simulated_orders.csv"
if os.path.exists(sim_log_path):
    recent = pd.read_csv(sim_log_path).tail(25).iloc[::-1]
    st.dataframe(recent, width='stretch')
else:
    st.info("No simulated order feed yet — run `python scripts/run_simulation.py` to generate live traffic.")