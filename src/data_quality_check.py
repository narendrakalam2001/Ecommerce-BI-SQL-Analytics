# ============================================================
# DATA QUALITY GATE — E-Commerce BI & SQL Analytics System
# (BI-project equivalent of the ML template's leakage_check.py —
#  fails the pipeline BEFORE the database is built / KPIs computed
#  if referential integrity or key-column nullability is broken.)
# ============================================================

import json
import logging
import pandas as pd

from src.config import (
    MAX_NULL_FRACTION_KEY_COLS,
    MAX_ORPHAN_FK_FRACTION,
    QUALITY_REPORT_PATH,
)

logger = logging.getLogger(__name__)


# ============================================================
# NULL-RATE CHECK ON KEY COLUMNS
# ============================================================

def check_key_column_nulls(tables: dict) -> list:
    key_columns = {
        "customers":   ["customer_id", "customer_unique_id"],
        "orders":      ["order_id", "customer_id"],
        "order_items": ["order_id", "product_id", "seller_id"],
        "payments":    ["order_id", "payment_value"],
        "products":    ["product_id"],
        "sellers":     ["seller_id"],
    }

    violations = []
    for table_name, cols in key_columns.items():
        df = tables[table_name]
        for col in cols:
            null_frac = df[col].isna().mean()
            if null_frac > MAX_NULL_FRACTION_KEY_COLS:
                violations.append({
                    "check": "null_rate", "table": table_name, "column": col,
                    "null_fraction": round(float(null_frac), 4),
                    "threshold": MAX_NULL_FRACTION_KEY_COLS,
                })
    return violations


# ============================================================
# REFERENTIAL INTEGRITY (ORPHANED FOREIGN KEYS)
# ============================================================

def check_referential_integrity(tables: dict) -> list:
    checks = [
        ("order_items", "order_id",   "orders",   "order_id"),
        ("order_items", "product_id", "products", "product_id"),
        ("order_items", "seller_id",  "sellers",  "seller_id"),
        ("orders",      "customer_id","customers","customer_id"),
        ("payments",    "order_id",   "orders",   "order_id"),
        ("reviews",     "order_id",   "orders",   "order_id"),
    ]

    violations = []
    for child_tbl, child_fk, parent_tbl, parent_pk in checks:
        child_keys  = set(tables[child_tbl][child_fk].dropna())
        parent_keys = set(tables[parent_tbl][parent_pk].dropna())
        orphans = child_keys - parent_keys
        orphan_frac = len(orphans) / max(len(child_keys), 1)

        if orphan_frac > MAX_ORPHAN_FK_FRACTION:
            violations.append({
                "check": "referential_integrity",
                "child_table": child_tbl, "child_fk": child_fk,
                "parent_table": parent_tbl,
                "orphan_fraction": round(orphan_frac, 4),
                "threshold": MAX_ORPHAN_FK_FRACTION,
            })
    return violations


# ============================================================
# DUPLICATE PRIMARY KEY CHECK
# ============================================================

def check_duplicate_primary_keys(tables: dict) -> list:
    primary_keys = {
        "customers": "customer_id",
        "orders":    "order_id",
        "products":  "product_id",
        "sellers":   "seller_id",
    }
    violations = []
    for table_name, pk in primary_keys.items():
        dup_count = tables[table_name][pk].duplicated().sum()
        if dup_count > 0:
            violations.append({
                "check": "duplicate_pk", "table": table_name, "column": pk,
                "duplicate_rows": int(dup_count),
            })
    return violations


# ============================================================
# RUN ALL GATES
# ============================================================

def run_data_quality_gate(tables: dict, fail_hard: bool = True) -> dict:
    """
    Runs all quality checks and writes a report to artifacts/.
    If fail_hard=True, raises ValueError on ANY violation — mirrors
    the ML template's "leakage detected → stop training" behaviour.
    """
    violations = (
        check_key_column_nulls(tables)
        + check_referential_integrity(tables)
        + check_duplicate_primary_keys(tables)
    )

    report = {
        "passed": len(violations) == 0,
        "violation_count": len(violations),
        "violations": violations,
    }

    with open(QUALITY_REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)

    if violations:
        logger.warning("Data quality gate found %d violation(s)", len(violations))
        if fail_hard:
            raise ValueError(f"Data quality gate FAILED: {violations}")
    else:
        logger.info("Data quality gate passed — 0 violations")

    return report
