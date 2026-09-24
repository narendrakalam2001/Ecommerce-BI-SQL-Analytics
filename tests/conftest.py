# ============================================================
# PYTEST FIXTURES — synthetic Olist-shaped dataset
# ============================================================
# CI never downloads the real 100K-row Kaggle dataset. Instead we
# build a small, schema-correct synthetic dataset so every layer
# of the pipeline (validation -> quality gate -> DB build -> KPI
# queries -> metrics -> evaluation) is exercised on every push.
# ============================================================

import os
import sqlite3
import shutil
import pandas as pd
import numpy as np
import pytest
from datetime import datetime, timedelta

N_CUSTOMERS = 12
N_ORDERS    = 30


@pytest.fixture(scope="session")
def synthetic_tables():
    rng = np.random.default_rng(42)
    base_date = datetime(2017, 1, 1)

    customer_ids        = [f"cust_{i:03d}" for i in range(N_CUSTOMERS)]
    customer_unique_ids = [f"uniq_{i % 8:03d}" for i in range(N_CUSTOMERS)]  # some repeat customers
    states               = ["SP", "RJ", "MG", "RS", "BA"]

    customers = pd.DataFrame({
        "customer_id":        customer_ids,
        "customer_unique_id": customer_unique_ids,
        "customer_city":      [f"city_{i % 5}" for i in range(N_CUSTOMERS)],
        "customer_state":     [states[i % len(states)] for i in range(N_CUSTOMERS)],
    })

    order_ids   = [f"order_{i:03d}" for i in range(N_ORDERS)]
    cust_choice = rng.choice(customer_ids, size=N_ORDERS)
    purchase_ts = [base_date + timedelta(days=int(d)) for d in rng.integers(0, 150, size=N_ORDERS)]

    orders = pd.DataFrame({
        "order_id":    order_ids,
        "customer_id": cust_choice,
        "order_status": "delivered",
        "order_purchase_timestamp":       purchase_ts,
        "order_approved_at":              purchase_ts,
        "order_delivered_carrier_date":   [t + timedelta(days=1) for t in purchase_ts],
        "order_delivered_customer_date":  [t + timedelta(days=int(d)) for t, d in
                                            zip(purchase_ts, rng.integers(2, 15, size=N_ORDERS))],
        "order_estimated_delivery_date":  [t + timedelta(days=10) for t in purchase_ts],
    })
    orders["order_purchase_timestamp"] = pd.to_datetime(orders["order_purchase_timestamp"])
    orders["order_delivered_customer_date"] = pd.to_datetime(orders["order_delivered_customer_date"])
    orders["order_estimated_delivery_date"] = pd.to_datetime(orders["order_estimated_delivery_date"])

    seller_ids   = [f"seller_{i:02d}" for i in range(3)]
    product_ids  = [f"prod_{i:03d}" for i in range(8)]
    categories   = ["bed_bath_table", "health_beauty", "sports_leisure"]

    products = pd.DataFrame({
        "product_id": product_ids,
        "product_category_name": [categories[i % len(categories)] for i in range(len(product_ids))],
    })

    sellers = pd.DataFrame({
        "seller_id": seller_ids,
        "seller_city": [f"scity_{i}" for i in range(len(seller_ids))],
        "seller_state": [states[i % len(states)] for i in range(len(seller_ids))],
    })

    order_items = pd.DataFrame({
        "order_id":  order_ids,
        "order_item_id": 1,
        "product_id": rng.choice(product_ids, size=N_ORDERS),
        "seller_id":  rng.choice(seller_ids, size=N_ORDERS),
        "price":         rng.uniform(20, 300, size=N_ORDERS).round(2),
        "freight_value": rng.uniform(5, 40, size=N_ORDERS).round(2),
    })

    payments = pd.DataFrame({
        "order_id": order_ids,
        "payment_type": rng.choice(["credit_card", "boleto", "voucher"], size=N_ORDERS),
        "payment_installments": rng.integers(1, 6, size=N_ORDERS),
        "payment_value": order_items["price"] + order_items["freight_value"],
    })

    reviews = pd.DataFrame({
        "review_id": [f"rev_{i:03d}" for i in range(N_ORDERS)],
        "order_id":  order_ids,
        "review_score": rng.integers(1, 6, size=N_ORDERS),
    })

    geolocation = pd.DataFrame({
        "geolocation_zip_code_prefix": rng.integers(1000, 9999, size=20),
        "geolocation_lat": rng.uniform(-30, -5, size=20),
        "geolocation_lng": rng.uniform(-55, -35, size=20),
    })

    category_translation = pd.DataFrame({
        "product_category_name": categories,
        "product_category_name_english": ["bed_bath_table", "health_beauty", "sports_leisure"],
    })

    return {
        "customers": customers, "orders": orders, "order_items": order_items,
        "payments": payments, "reviews": reviews, "products": products,
        "sellers": sellers, "geolocation": geolocation,
        "category_translation": category_translation,
    }


@pytest.fixture(scope="session")
def built_test_db(synthetic_tables, tmp_path_factory):
    """Builds a throwaway SQLite DB from the synthetic tables and points
    the db_builder/kpi_queries modules at it for the duration of the test session."""
    from src import db_builder
    from src import kpi_queries as kq
    import src.evaluation as evaluation_module
    import src.metrics as metrics_module

    tmp_dir = tmp_path_factory.mktemp("db")
    db_path = str(tmp_dir / "test_olist.db")

    db_builder.build_database(synthetic_tables, db_path=db_path)

    original_run_query = db_builder.run_query

    def patched_run_query(sql, db_path_arg=db_path, params=()):
        return original_run_query(sql, db_path=db_path_arg, params=params)

    # kpi_queries, evaluation, and metrics all call run_query() with the
    # module-level default db_path — patch the bound name in every module
    # that imported it directly so tests hit the throwaway test DB.
    db_builder.run_query = patched_run_query
    kq.run_query = patched_run_query

    yield db_path

    db_builder.run_query = original_run_query
    kq.run_query = original_run_query
