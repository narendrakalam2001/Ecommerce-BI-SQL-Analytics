# Entry point: full analytics pipeline (build DB + compute KPI snapshot).
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.analytics_pipeline import run_pipeline

if __name__ == "__main__":
    run_pipeline()