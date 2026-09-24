# ============================================================
# KPI SERVICE — caching + logging layer between API/dashboard
# and the raw KPI query bank (mirrors services/prediction_service.py
# in the ML template).
# ============================================================

import time
import logging

from src import kpi_queries as kq
from src import metrics, evaluation

logger = logging.getLogger(__name__)

_CACHE = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes — KPI tables don't need per-request recompute


def _cached(key, fn, *args, **kwargs):
    now = time.time()
    entry = _CACHE.get(key)
    if entry and (now - entry["ts"] < _CACHE_TTL_SECONDS):
        return entry["value"]

    value = fn(*args, **kwargs)
    _CACHE[key] = {"value": value, "ts": now}
    logger.info("Cache MISS -> recomputed '%s' in service layer", key)
    return value


def get_executive_summary() -> dict:
    return _cached("executive_summary", metrics.executive_summary)


def get_monthly_revenue():
    return _cached("monthly_revenue", kq.monthly_revenue)


def get_seller_leaderboard(min_orders: int = 5):
    return _cached(f"seller_leaderboard_{min_orders}", kq.seller_leaderboard, min_orders)


def get_rfm_summary():
    return _cached("rfm_summary", kq.rfm_segment_summary)


def get_monitoring_alerts() -> dict:
    # Alerts are always recomputed fresh — never served stale.
    return evaluation.run_all_monitoring_checks()


def clear_cache():
    _CACHE.clear()
    logger.info("KPI service cache cleared")
