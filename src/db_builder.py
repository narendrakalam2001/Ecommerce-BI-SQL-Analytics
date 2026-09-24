# ============================================================
# DATABASE BUILDER — E-Commerce BI & SQL Analytics System
# ============================================================
#
# Loads the 9 validated Olist tables into a single SQLite database
# with explicit indexes on every join column used by the KPI query
# bank in sql/. SQLite is used (over Postgres) so the whole project
# runs anywhere with zero external DB dependency — the SQL itself
# is standard ANSI and portable to Postgres/MySQL if needed.
# ============================================================

import sqlite3
import logging
import pandas as pd

from src.config import DB_PATH

logger = logging.getLogger(__name__)

TABLE_NAME_MAP = {
    "customers":  "customers",
    "orders":     "orders",
    "order_items":"order_items",
    "payments":   "payments",
    "reviews":    "reviews",
    "products":   "products",
    "sellers":    "sellers",
    "geolocation":"geolocation",
    "category_translation": "category_translation",
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_orders_customer     ON orders(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_orders_status        ON orders(order_status)",
    "CREATE INDEX IF NOT EXISTS idx_orders_purchase_ts   ON orders(order_purchase_timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_items_order          ON order_items(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_items_product        ON order_items(product_id)",
    "CREATE INDEX IF NOT EXISTS idx_items_seller         ON order_items(seller_id)",
    "CREATE INDEX IF NOT EXISTS idx_payments_order       ON payments(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_reviews_order        ON reviews(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_customers_unique     ON customers(customer_unique_id)",
    "CREATE INDEX IF NOT EXISTS idx_products_category    ON products(product_category_name)",
]


def build_database(tables: dict, db_path: str = DB_PATH) -> None:
    """
    Writes each validated DataFrame to SQLite, replacing any existing
    table, then creates the join indexes needed for fast KPI queries.
    """
    conn = sqlite3.connect(db_path)
    try:
        for key, table_name in TABLE_NAME_MAP.items():
            df = tables[key]
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            logger.info("Wrote table '%s'  rows=%d  cols=%d", table_name, *df.shape)

        cur = conn.cursor()
        for stmt in INDEXES:
            cur.execute(stmt)
        conn.commit()
        logger.info("Built %d indexes on %s", len(INDEXES), db_path)

    finally:
        conn.close()


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def run_query(sql: str, db_path: str = DB_PATH, params: tuple = ()) -> pd.DataFrame:
    """Thin convenience wrapper used by kpi_queries.py and the API/dashboard."""
    conn = get_connection(db_path)
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()
