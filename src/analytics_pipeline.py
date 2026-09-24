# ============================================================
# ANALYTICS PIPELINE — E-Commerce BI & SQL Analytics System
# (BI-project equivalent of the ML template's training_pipeline.py)
# ============================================================

import json
import logging
import time

from src.config import KPI_SNAPSHOT_PATH
from src.data_loader import load_raw_tables, validate_raw_tables, parse_order_dates
from src.data_quality_check import run_data_quality_gate
from src.db_builder import build_database
from src import kpi_queries as kq
from src import metrics
from src import evaluation

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def run_pipeline() -> dict:
    start = time.time()
    logger.info("=" * 60)
    logger.info("STEP 1/5 — Loading raw Olist tables")
    tables = load_raw_tables()

    logger.info("STEP 2/5 — Validating schema")
    validate_raw_tables(tables)
    tables["orders"] = parse_order_dates(tables["orders"])

    logger.info("STEP 3/5 — Running data quality gate")
    quality_report = run_data_quality_gate(tables, fail_hard=True)

    logger.info("STEP 4/5 — Building SQLite database + indexes")
    build_database(tables)

    logger.info("STEP 5/5 — Computing KPI snapshot + monitoring checks")
    snapshot = {
        "executive_summary":  metrics.executive_summary(),
        "monitoring":         evaluation.run_all_monitoring_checks(),
        "top_categories":     kq.top_categories(10).to_dict(orient="records"),
        "seller_leaderboard": kq.seller_leaderboard().head(20).to_dict(orient="records"),
        "rfm_segment_summary":kq.rfm_segment_summary().to_dict(orient="records"),
        "data_quality":       quality_report,
        "generated_in_sec":   round(time.time() - start, 2),
    }

    with open(KPI_SNAPSHOT_PATH, "w") as f:
        json.dump(snapshot, f, indent=2, default=str)

    logger.info("Pipeline complete in %.2fs — snapshot written to %s",
                snapshot["generated_in_sec"], KPI_SNAPSHOT_PATH)
    logger.info("=" * 60)
    return snapshot


if __name__ == "__main__":
    run_pipeline()
