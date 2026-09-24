# ============================================================
# KPI TREND MONITORING — E-Commerce BI & SQL Analytics System
# (BI-project equivalent of the ML template's PSI drift monitor —
#  instead of feature distribution shift, we watch week-over-week
#  and month-over-month swings in business KPIs and raise alerts.)
# ============================================================

import logging
import pandas as pd

from src.config import KPI_WOW_ALERT_PCT, KPI_MOM_ALERT_PCT, LATE_RATE_ALERT_PCT
from src import kpi_queries as kq

logger = logging.getLogger(__name__)


def monthly_revenue_alerts() -> list:
    """
    Flags months where revenue moved more than KPI_MOM_ALERT_PCT
    vs. the prior month — same "did something break or spike"
    signal that PSI drift gives an ML model, applied to a KPI series.
    """
    df = kq.monthly_revenue().sort_values("month").reset_index(drop=True)
    alerts = []

    for i in range(1, len(df)):
        prev, curr = df.loc[i - 1, "gross_revenue"], df.loc[i, "gross_revenue"]
        if prev == 0:
            continue
        pct_change = (curr - prev) / prev
        if abs(pct_change) >= KPI_MOM_ALERT_PCT:
            alerts.append({
                "month": df.loc[i, "month"],
                "metric": "monthly_revenue",
                "prior_value": float(prev),
                "current_value": float(curr),
                "pct_change": round(pct_change * 100, 2),
                "severity": "high" if abs(pct_change) >= 2 * KPI_MOM_ALERT_PCT else "moderate",
            })

    if alerts:
        logger.warning("%d monthly revenue anomalies detected", len(alerts))
    return alerts


def delivery_sla_alert() -> dict:
    """Flags if the fleet-wide late-delivery rate breaches the alert threshold."""
    sla = kq.delivery_sla_overall()
    if sla.empty:
        return {"triggered": False}

    late_pct = float(sla["late_pct"].iloc[0]) / 100.0
    triggered = late_pct >= LATE_RATE_ALERT_PCT

    result = {
        "triggered": triggered,
        "late_pct": round(late_pct * 100, 2),
        "threshold_pct": round(LATE_RATE_ALERT_PCT * 100, 2),
    }
    if triggered:
        logger.warning("Late-delivery SLA alert triggered: %s", result)
    return result


def seller_quality_alerts(min_orders: int = 5) -> pd.DataFrame:
    """At-risk sellers table, reused as a standing monitoring alert feed."""
    return kq.at_risk_sellers()


def run_all_monitoring_checks() -> dict:
    """Aggregates every monitoring signal into one payload for the dashboard's alert panel."""
    revenue_alerts = monthly_revenue_alerts()
    sla_alert      = delivery_sla_alert()
    at_risk        = seller_quality_alerts()

    return {
        "revenue_anomalies":     revenue_alerts,
        "sla_alert":             sla_alert,
        "at_risk_seller_count":  int(len(at_risk)),
        "total_alerts":          len(revenue_alerts) + (1 if sla_alert.get("triggered") else 0),
    }
