# ============================================================
# DATA LOADER — E-Commerce BI & SQL Analytics System
# ============================================================

import os
import logging
import pandas as pd

from src.config import RAW_DATA_DIR, RAW_FILES

logger = logging.getLogger(__name__)


# ============================================================
# LOAD RAW TABLES
# ============================================================

def _resolve_file_path(raw_dir: str, csv_filename: str) -> str:
    """
    Resolves the actual file on disk for a given logical table.
    Kaggle ships this dataset as .csv, but some local copies get
    saved/exported as .xlsx or .xls (Windows Explorer shows these
    as "XLS Worksheet" even when the visible name has no extension
    because Explorer hides known extensions). This checks .csv
    first, then falls back to .xlsx / .xls so both cases work.
    """
    stem = os.path.splitext(csv_filename)[0]
    for ext in (".csv", ".xlsx", ".xls"):
        candidate = os.path.join(raw_dir, stem + ext)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(raw_dir, csv_filename)  # let the missing-file check below report it


def _read_any(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    return pd.read_csv(path)


def load_raw_tables(raw_dir: str = RAW_DATA_DIR) -> dict:
    """
    Loads all 9 Olist source tables into a dict of DataFrames.
    Accepts either .csv (Kaggle's native format) or .xlsx/.xls
    (some local copies are saved as Excel instead). Raises
    FileNotFoundError with the exact missing files if the dataset
    hasn't been placed under RAW_DATA_DIR yet.
    """
    resolved = {key: _resolve_file_path(raw_dir, fname) for key, fname in RAW_FILES.items()}
    missing = [fname for key, fname in RAW_FILES.items() if not os.path.exists(resolved[key])]
    if missing:
        raise FileNotFoundError(
            "Missing raw Olist files in '{}': {}. "
            "Download from kaggle.com/datasets/olistbr/brazilian-ecommerce "
            "and place all files (.csv or .xlsx) in that folder.".format(raw_dir, missing)
        )

    tables = {}
    for key, path in resolved.items():
        tables[key] = _read_any(path)
        logger.info("Loaded %-22s shape=%s  <- %s", key, tables[key].shape, path)

    return tables


# ============================================================
# VALIDATION
# ============================================================

REQUIRED_COLUMNS = {
    "customers":  ["customer_id", "customer_unique_id", "customer_city", "customer_state"],
    "orders":     ["order_id", "customer_id", "order_status",
                   "order_purchase_timestamp", "order_delivered_customer_date",
                   "order_estimated_delivery_date"],
    "order_items":["order_id", "order_item_id", "product_id", "seller_id",
                   "price", "freight_value"],
    "payments":   ["order_id", "payment_type", "payment_installments", "payment_value"],
    "reviews":    ["review_id", "order_id", "review_score"],
    "products":   ["product_id", "product_category_name"],
    "sellers":    ["seller_id", "seller_city", "seller_state"],
    "geolocation":["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"],
    "category_translation": ["product_category_name", "product_category_name_english"],
}


def validate_raw_tables(tables: dict) -> None:
    """
    Fails fast (before any DB build / KPI computation) if required
    columns are missing or a table is empty. This is the BI-project
    equivalent of the ML template's leakage_check gate.
    """
    for key, required_cols in REQUIRED_COLUMNS.items():
        df = tables[key]

        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            raise ValueError(f"Table '{key}' is missing required columns: {missing_cols}")

        if df.empty:
            raise ValueError(f"Table '{key}' loaded with 0 rows — check the source file")

    logger.info("Raw table validation passed for all %d tables", len(tables))


# ============================================================
# PARSE DATETIME COLUMNS
# ============================================================

ORDER_DATE_COLS = [
    "order_purchase_timestamp", "order_approved_at",
    "order_delivered_carrier_date", "order_delivered_customer_date",
    "order_estimated_delivery_date",
]


def parse_order_dates(orders_df: pd.DataFrame) -> pd.DataFrame:
    df = orders_df.copy()
    for col in ORDER_DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df