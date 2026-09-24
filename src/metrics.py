# ============================================================
# EXECUTIVE METRICS — E-Commerce BI & SQL Analytics System
# ============================================================

import logging
from src import kpi_queries as kq

logger = logging.getLogger(__name__)


def executive_summary() -> dict:
    """
    Single-call snapshot of the headline numbers shown at the top
    of the dashboard and returned by the API's /kpis/summary route.
    """
    monthly   = kq.monthly_revenue()
    sla       = kq.delivery_sla_overall()
    repeat    = kq.repeat_purchase_rate()
    churn     = kq.churn_risk_count()

    total_revenue = round(float(monthly["gross_revenue"].sum()), 2) if not monthly.empty else 0.0
    total_orders  = int(monthly["orders"].sum()) if not monthly.empty else 0
    aov           = round(total_revenue / total_orders, 2) if total_orders else 0.0

    summary = {
        "total_revenue":        total_revenue,
        "total_orders":         total_orders,
        "avg_order_value":      aov,
        "months_covered":       int(monthly.shape[0]),
        "late_delivery_pct":    float(sla["late_pct"].iloc[0]) if not sla.empty else None,
        "repeat_purchase_pct":  float(repeat["repeat_rate_pct"].iloc[0]) if not repeat.empty else None,
        "churn_risk_customers": int(churn["churn_risk_customers"].iloc[0]) if not churn.empty else 0,
    }

    logger.info("Executive summary computed: %s", summary)
    return summary


def top_movers(df, value_col: str, label_col: str, n: int = 5) -> dict:
    """Generic helper: top-N and bottom-N rows of a KPI table for callouts."""
    if df.empty:
        return {"top": [], "bottom": []}
    sorted_df = df.sort_values(value_col, ascending=False)
    return {
        "top":    sorted_df.head(n)[[label_col, value_col]].to_dict(orient="records"),
        "bottom": sorted_df.tail(n)[[label_col, value_col]].to_dict(orient="records"),
    }
