# ============================================================
# CONFIGURATION — E-Commerce BI & SQL Analytics System
# ============================================================

import os

# ── Reproducibility ──────────────────────────────────────────
RANDOM_STATE = 42

# ── Paths ────────────────────────────────────────────────────
# RAW_DATA_DIR resolution order (so the same code works locally AND on
# Render/Streamlit Cloud, where your local D:\ path doesn't exist):
#   1. RAW_DATA_DIR environment variable, if set
#   2. Your local Windows dataset folder, if it exists on this machine
#   3. data/sample/ — the lightweight sample committed to the repo,
#      used automatically on any cloud deployment
import os as _os

_LOCAL_WINDOWS_PATH = "D:/Data Science Datasets/Olist Brazilian E-Commerce"

RAW_DATA_DIR = (
    _os.environ.get("RAW_DATA_DIR")
    or (_LOCAL_WINDOWS_PATH if _os.path.exists(_LOCAL_WINDOWS_PATH) else "data/sample")
)
PROCESSED_DIR      = "data/processed"
DB_PATH            = "artifacts/olist.db"
ARTIFACTS_DIR      = "artifacts"
KPI_SNAPSHOT_PATH  = "artifacts/kpi_snapshot.json"
LOGS_DIR           = "logs"
QUALITY_REPORT_PATH = "artifacts/data_quality_report.json"

# ── Raw Olist source files (8 relational tables + translation) ─
RAW_FILES = {
    "customers":  "olist_customers_dataset.csv",
    "orders":     "olist_orders_dataset.csv",
    "order_items":"olist_order_items_dataset.csv",
    "payments":   "olist_order_payments_dataset.csv",
    "reviews":    "olist_order_reviews_dataset.csv",
    "products":   "olist_products_dataset.csv",
    "sellers":    "olist_sellers_dataset.csv",
    "geolocation":"olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

# ── Business rule thresholds ─────────────────────────────────
LATE_DELIVERY_GRACE_DAYS   = 0        # delivered_date > estimated_date => late
FAST_DELIVERY_DAYS         = 3        # <= this => "fast" delivery bucket
LOW_REVIEW_SCORE_THRESHOLD = 3        # review_score < this => "at risk" for seller
MIN_ORDERS_FOR_SELLER_RANK = 5        # sellers below this are excluded from leaderboards

# ── RFM segmentation ─────────────────────────────────────────
RFM_QUANTILES        = 4              # quartile-based scoring (1-4)
CHURN_INACTIVITY_DAYS = 180           # no repeat purchase in N days => churn-risk

# ── KPI trend-anomaly thresholds (BI equivalent of PSI drift) ─
# A KPI moving more than this fraction week-over-week triggers a monitoring alert.
KPI_WOW_ALERT_PCT   = 0.25            # 25% week-over-week swing
KPI_MOM_ALERT_PCT   = 0.20            # 20% month-over-month swing
LATE_RATE_ALERT_PCT = 0.15            # fleet-wide late-delivery rate alert threshold

# ── Data-quality gate thresholds (BI equivalent of leakage_check) ─
MAX_NULL_FRACTION_KEY_COLS = 0.02     # >2% nulls in a key join column fails the gate
MAX_ORPHAN_FK_FRACTION     = 0.01     # >1% orphaned foreign keys fails the gate

os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)