# Entry point: loads raw CSVs, validates, runs quality gate, builds SQLite DB.
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_loader import load_raw_tables, validate_raw_tables, parse_order_dates
from src.data_quality_check import run_data_quality_gate
from src.db_builder import build_database

if __name__ == "__main__":
    tables = load_raw_tables()
    validate_raw_tables(tables)
    tables["orders"] = parse_order_dates(tables["orders"])
    run_data_quality_gate(tables, fail_hard=True)
    build_database(tables)
    print("Database built successfully at artifacts/olist.db")