# ============================================================
# TEST SUITE — E-Commerce BI & SQL Analytics System
# ============================================================

import os
import pandas as pd
import pytest

from src.data_loader import validate_raw_tables, parse_order_dates, REQUIRED_COLUMNS
from src.data_quality_check import (
    check_key_column_nulls,
    check_referential_integrity,
    check_duplicate_primary_keys,
    run_data_quality_gate,
)
from src import kpi_queries as kq
from src import metrics
from src import evaluation
from src.config import (
    MIN_ORDERS_FOR_SELLER_RANK,
    LOW_REVIEW_SCORE_THRESHOLD,
    CHURN_INACTIVITY_DAYS,
)


# ============================================================
# 1. DATA VALIDATION (data_loader.py)
# ============================================================

class TestDataValidation:

    def test_validate_raw_tables_passes_on_synthetic_data(self, synthetic_tables):
        validate_raw_tables(synthetic_tables)  # should not raise

    def test_validate_raw_tables_raises_on_missing_column(self, synthetic_tables):
        broken = dict(synthetic_tables)
        broken["orders"] = broken["orders"].drop(columns=["order_status"])
        with pytest.raises(ValueError, match="missing required columns"):
            validate_raw_tables(broken)

    def test_validate_raw_tables_raises_on_empty_table(self, synthetic_tables):
        broken = dict(synthetic_tables)
        broken["reviews"] = broken["reviews"].iloc[0:0]
        with pytest.raises(ValueError, match="0 rows"):
            validate_raw_tables(broken)

    def test_required_columns_cover_all_nine_tables(self):
        assert len(REQUIRED_COLUMNS) == 9

    def test_parse_order_dates_converts_to_datetime(self, synthetic_tables):
        parsed = parse_order_dates(synthetic_tables["orders"])
        assert pd.api.types.is_datetime64_any_dtype(parsed["order_purchase_timestamp"])


# ============================================================
# 2. DATA QUALITY GATE (data_quality_check.py)
# ============================================================

class TestDataQualityGate:

    def test_no_null_violations_on_clean_synthetic_data(self, synthetic_tables):
        assert check_key_column_nulls(synthetic_tables) == []

    def test_no_referential_integrity_violations_on_clean_data(self, synthetic_tables):
        assert check_referential_integrity(synthetic_tables) == []

    def test_no_duplicate_pk_violations_on_clean_data(self, synthetic_tables):
        assert check_duplicate_primary_keys(synthetic_tables) == []

    def test_referential_integrity_catches_orphaned_seller_fk(self, synthetic_tables):
        broken = dict(synthetic_tables)
        broken["sellers"] = broken["sellers"].iloc[0:0]  # remove all sellers -> every order_item is orphaned
        violations = check_referential_integrity(broken)
        assert any(v["child_fk"] == "seller_id" for v in violations)

    def test_duplicate_pk_check_catches_duplicated_customer_id(self, synthetic_tables):
        broken = dict(synthetic_tables)
        dup_row = broken["customers"].iloc[[0]]
        broken["customers"] = pd.concat([broken["customers"], dup_row], ignore_index=True)
        violations = check_duplicate_primary_keys(broken)
        assert any(v["table"] == "customers" for v in violations)

    def test_quality_gate_passes_and_writes_report(self, synthetic_tables, tmp_path, monkeypatch):
        report_path = tmp_path / "quality_report.json"
        monkeypatch.setattr("src.data_quality_check.QUALITY_REPORT_PATH", str(report_path))
        report = run_data_quality_gate(synthetic_tables, fail_hard=True)
        assert report["passed"] is True
        assert os.path.exists(report_path)

    def test_quality_gate_raises_on_violation_when_fail_hard(self, synthetic_tables, tmp_path, monkeypatch):
        report_path = tmp_path / "quality_report.json"
        monkeypatch.setattr("src.data_quality_check.QUALITY_REPORT_PATH", str(report_path))
        broken = dict(synthetic_tables)
        broken["sellers"] = broken["sellers"].iloc[0:0]
        with pytest.raises(ValueError, match="Data quality gate FAILED"):
            run_data_quality_gate(broken, fail_hard=True)

    def test_quality_gate_does_not_raise_when_fail_hard_false(self, synthetic_tables, tmp_path, monkeypatch):
        report_path = tmp_path / "quality_report.json"
        monkeypatch.setattr("src.data_quality_check.QUALITY_REPORT_PATH", str(report_path))
        broken = dict(synthetic_tables)
        broken["sellers"] = broken["sellers"].iloc[0:0]
        report = run_data_quality_gate(broken, fail_hard=False)
        assert report["passed"] is False


# ============================================================
# 3. DATABASE BUILD (db_builder.py)
# ============================================================

class TestDatabaseBuild:

    def test_db_file_created(self, built_test_db):
        assert os.path.exists(built_test_db)

    def test_all_tables_present_in_db(self, built_test_db):
        import sqlite3
        conn = sqlite3.connect(built_test_db)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        expected = {"customers", "orders", "order_items", "payments",
                    "reviews", "products", "sellers", "geolocation", "category_translation"}
        assert expected.issubset(tables)

    def test_indexes_created(self, built_test_db):
        import sqlite3
        conn = sqlite3.connect(built_test_db)
        indexes = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
        conn.close()
        assert "idx_orders_customer" in indexes
        assert "idx_items_seller" in indexes


# ============================================================
# 4. KPI QUERIES (kpi_queries.py)
# ============================================================

class TestKpiQueries:

    def test_monthly_revenue_returns_rows(self, built_test_db):
        df = kq.monthly_revenue()
        assert not df.empty
        assert {"month", "orders", "gross_revenue", "avg_order_value"}.issubset(df.columns)

    def test_monthly_revenue_is_non_negative(self, built_test_db):
        df = kq.monthly_revenue()
        assert (df["gross_revenue"] >= 0).all()

    def test_revenue_by_state_sums_to_total(self, built_test_db):
        by_state = kq.revenue_by_state()
        total = kq.monthly_revenue()["gross_revenue"].sum()
        assert round(by_state["gross_revenue"].sum(), 1) == round(total, 1)

    def test_top_categories_respects_limit(self, built_test_db):
        df = kq.top_categories(limit=2)
        assert len(df) <= 2

    def test_seller_leaderboard_filters_below_min_orders(self, built_test_db):
        df = kq.seller_leaderboard(min_orders=MIN_ORDERS_FOR_SELLER_RANK)
        assert (df["total_orders"] >= MIN_ORDERS_FOR_SELLER_RANK).all()

    def test_at_risk_sellers_below_threshold(self, built_test_db):
        df = kq.at_risk_sellers(score_threshold=LOW_REVIEW_SCORE_THRESHOLD)
        if not df.empty:
            assert (df["avg_review_score"] < LOW_REVIEW_SCORE_THRESHOLD).all()

    def test_delivery_sla_overall_percentages_consistent(self, built_test_db):
        df = kq.delivery_sla_overall()
        row = df.iloc[0]
        assert row["on_time"] + row["late"] == row["total_delivered"]

    def test_delivery_by_state_has_late_pct_between_0_and_100(self, built_test_db):
        df = kq.delivery_by_state()
        assert df["late_pct"].between(0, 100).all()

    def test_repeat_purchase_rate_consistent_totals(self, built_test_db):
        df = kq.repeat_purchase_rate()
        row = df.iloc[0]
        assert row["one_time_customers"] + row["repeat_customers"] == row["total_customers"]

    def test_rfm_segments_returns_all_customers(self, built_test_db, synthetic_tables):
        df = kq.rfm_segments()
        n_unique_customers = synthetic_tables["customers"]["customer_unique_id"].nunique()
        assert len(df) == n_unique_customers

    def test_rfm_scores_within_valid_range(self, built_test_db):
        df = kq.rfm_segments()
        for col in ("r_score", "f_score", "m_score"):
            assert df[col].between(1, 4).all()

    def test_rfm_segment_summary_groups_are_known_labels(self, built_test_db):
        df = kq.rfm_segment_summary()
        known = {"Champions", "New / Promising", "At Risk (high value)",
                 "Churned / Lost", "Needs Attention"}
        assert set(df["rfm_segment"]).issubset(known)

    def test_churn_risk_count_non_negative(self, built_test_db):
        df = kq.churn_risk_count(inactivity_days=CHURN_INACTIVITY_DAYS)
        assert int(df["churn_risk_customers"].iloc[0]) >= 0

    def test_cohort_retention_cohort_month_never_after_activity_month(self, built_test_db):
        df = kq.cohort_retention()
        assert (df["cohort_month"] <= df["activity_month"]).all()


# ============================================================
# 5. EXECUTIVE METRICS (metrics.py)
# ============================================================

class TestMetrics:

    def test_executive_summary_has_expected_keys(self, built_test_db):
        summary = metrics.executive_summary()
        expected_keys = {
            "total_revenue", "total_orders", "avg_order_value", "months_covered",
            "late_delivery_pct", "repeat_purchase_pct", "churn_risk_customers",
        }
        assert expected_keys.issubset(summary.keys())

    def test_executive_summary_aov_matches_revenue_over_orders(self, built_test_db):
        summary = metrics.executive_summary()
        if summary["total_orders"] > 0:
            expected_aov = round(summary["total_revenue"] / summary["total_orders"], 2)
            assert abs(summary["avg_order_value"] - expected_aov) < 0.01

    def test_top_movers_returns_top_and_bottom(self, built_test_db):
        df = kq.seller_leaderboard()
        result = metrics.top_movers(df, value_col="total_revenue", label_col="seller_id", n=2)
        assert "top" in result and "bottom" in result


# ============================================================
# 6. MONITORING / EVALUATION (evaluation.py)
# ============================================================

class TestEvaluation:

    def test_monthly_revenue_alerts_returns_list(self, built_test_db):
        alerts = evaluation.monthly_revenue_alerts()
        assert isinstance(alerts, list)

    def test_delivery_sla_alert_has_triggered_key(self, built_test_db):
        result = evaluation.delivery_sla_alert()
        assert "triggered" in result

    def test_run_all_monitoring_checks_returns_full_payload(self, built_test_db):
        result = evaluation.run_all_monitoring_checks()
        assert {"revenue_anomalies", "sla_alert", "at_risk_seller_count", "total_alerts"}.issubset(result.keys())


# ============================================================
# 7. SIMULATION (order_event_simulator.py)
# ============================================================

class TestSimulation:

    def test_run_simulation_writes_log_file(self, tmp_path, monkeypatch):
        from simulation import order_event_simulator as sim
        log_path = tmp_path / "simulated_orders.csv"
        monkeypatch.setattr(sim, "LOG_PATH", str(log_path))
        sim.run_simulation(scenario_name="normal_day", ticks=2, tick_delay_sec=0)
        assert os.path.exists(log_path)

    def test_run_simulation_rejects_unknown_scenario(self):
        from simulation import order_event_simulator as sim
        with pytest.raises(ValueError, match="Unknown scenario"):
            sim.run_simulation(scenario_name="not_a_real_scenario", ticks=1, tick_delay_sec=0)

    def test_logistics_disruption_scenario_has_higher_late_prob_than_normal(self):
        from simulation.order_event_simulator import SCENARIOS
        assert SCENARIOS["logistics_disruption"]["late_prob"] > SCENARIOS["normal_day"]["late_prob"]

    def test_flash_sale_scenario_has_higher_order_volume_than_normal(self):
        from simulation.order_event_simulator import SCENARIOS
        assert SCENARIOS["flash_sale_spike"]["orders_per_tick"][0] > SCENARIOS["normal_day"]["orders_per_tick"][0]
