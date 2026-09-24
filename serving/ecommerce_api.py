# ============================================================
# E-COMMERCE BI API — FastAPI Serving
# ============================================================

from fastapi import FastAPI, HTTPException, Query
import logging
import os
import json
import sqlite3

from src.config import DB_PATH, KPI_SNAPSHOT_PATH
from src.db_builder import run_query
from src import kpi_queries as kq
from src import metrics
from src import evaluation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="E-Commerce BI & SQL Analytics API")

# ── Whitelisted read-only SQL for the ad-hoc /query endpoint ───
_ALLOWED_QUERY_PREFIX = ("select", "with")


def _db_available() -> bool:
    return os.path.exists(DB_PATH)


# ============================================================
# HEALTH / INFO
# ============================================================

@app.get("/")
def home():
    return {
        "message": "E-Commerce BI & SQL Analytics API is live 🚀",
        "docs":    "/docs",
        "health":  "/health",
    }


@app.get("/health")
def health():
    return {"status": "running", "database_built": _db_available()}


@app.get("/schema_info")
def schema_info():
    """BI-project equivalent of /model_info — describes what's actually loaded."""
    if not _db_available():
        raise HTTPException(status_code=503, detail="Database not built yet — run scripts/build_database.py")

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        info = {}
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            info[t] = cur.fetchone()[0]
        return {"tables": info, "db_path": DB_PATH}
    finally:
        conn.close()


# ============================================================
# KPI ROUTES
# ============================================================

@app.get("/kpis/summary")
def kpis_summary():
    return metrics.executive_summary()


@app.get("/kpis/revenue/monthly")
def kpis_revenue_monthly():
    return kq.monthly_revenue().to_dict(orient="records")


@app.get("/kpis/revenue/by-state")
def kpis_revenue_by_state():
    return kq.revenue_by_state().to_dict(orient="records")


@app.get("/kpis/revenue/top-categories")
def kpis_top_categories(limit: int = Query(10, ge=1, le=50)):
    return kq.top_categories(limit).to_dict(orient="records")


@app.get("/kpis/sellers/leaderboard")
def kpis_seller_leaderboard(min_orders: int = Query(5, ge=1)):
    return kq.seller_leaderboard(min_orders).to_dict(orient="records")


@app.get("/kpis/sellers/at-risk")
def kpis_at_risk_sellers():
    return kq.at_risk_sellers().to_dict(orient="records")


@app.get("/kpis/delivery/sla")
def kpis_delivery_sla():
    return kq.delivery_sla_overall().to_dict(orient="records")[0]


@app.get("/kpis/delivery/by-state")
def kpis_delivery_by_state():
    return kq.delivery_by_state().to_dict(orient="records")


@app.get("/kpis/customers/rfm-summary")
def kpis_rfm_summary():
    return kq.rfm_segment_summary().to_dict(orient="records")


@app.get("/kpis/customers/repeat-rate")
def kpis_repeat_rate():
    return kq.repeat_purchase_rate().to_dict(orient="records")[0]


@app.get("/kpis/customers/cohort-retention")
def kpis_cohort_retention():
    return kq.cohort_retention().to_dict(orient="records")


# ============================================================
# MONITORING
# ============================================================

@app.get("/monitoring/alerts")
def monitoring_alerts():
    return evaluation.run_all_monitoring_checks()


@app.get("/monitoring/snapshot")
def monitoring_snapshot():
    """Returns the last full KPI snapshot written by the analytics pipeline."""
    if not os.path.exists(KPI_SNAPSHOT_PATH):
        raise HTTPException(status_code=503, detail="No snapshot yet — run scripts/run_pipeline.py")
    with open(KPI_SNAPSHOT_PATH) as f:
        return json.load(f)


# ============================================================
# AD-HOC READ-ONLY QUERY (whitelisted SELECT/CTE only)
# ============================================================

@app.post("/query")
def run_ad_hoc_query(sql: str):
    cleaned = sql.strip().lower()
    if not cleaned.startswith(_ALLOWED_QUERY_PREFIX):
        raise HTTPException(status_code=400, detail="Only SELECT / WITH read-only queries are allowed")
    if any(kw in cleaned for kw in ("insert", "update", "delete", "drop", "alter", "attach", "pragma")):
        raise HTTPException(status_code=400, detail="Query contains a disallowed keyword")

    try:
        df = run_query(sql)
        return df.head(500).to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query failed: {e}")
