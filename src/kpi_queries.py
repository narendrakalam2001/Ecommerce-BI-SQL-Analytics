# ============================================================
# KPI QUERY BANK — E-Commerce BI & SQL Analytics System
#
# Each function wraps one query from sql/*.sql so the API, the
# dashboard, and the analytics pipeline all share a single source
# of truth. The raw .sql files under sql/ are the reference
# artifact (interview-round SQL); these functions execute the
# same logic against the SQLite database built by db_builder.py.
# ============================================================

import pandas as pd
from src.db_builder import run_query
from src.config import LOW_REVIEW_SCORE_THRESHOLD, MIN_ORDERS_FOR_SELLER_RANK, CHURN_INACTIVITY_DAYS


# ── Revenue ──────────────────────────────────────────────────

def monthly_revenue() -> pd.DataFrame:
    return run_query("""
        SELECT
            strftime('%Y-%m', o.order_purchase_timestamp) AS month,
            COUNT(DISTINCT o.order_id)                     AS orders,
            ROUND(SUM(oi.price + oi.freight_value), 2)     AS gross_revenue,
            ROUND(SUM(oi.price + oi.freight_value) / COUNT(DISTINCT o.order_id), 2) AS avg_order_value
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        WHERE o.order_status = 'delivered'
        GROUP BY month
        ORDER BY month
    """)


def revenue_by_state() -> pd.DataFrame:
    return run_query("""
        SELECT
            c.customer_state,
            COUNT(DISTINCT o.order_id)                 AS orders,
            ROUND(SUM(oi.price + oi.freight_value), 2) AS gross_revenue
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        JOIN customers c    ON c.customer_id = o.customer_id
        WHERE o.order_status = 'delivered'
        GROUP BY c.customer_state
        ORDER BY gross_revenue DESC
    """)


def top_categories(limit: int = 10) -> pd.DataFrame:
    return run_query(f"""
        SELECT
            COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
            COUNT(DISTINCT oi.order_id) AS orders,
            ROUND(SUM(oi.price), 2)     AS product_revenue
        FROM order_items oi
        JOIN orders o   ON o.order_id = oi.order_id
        JOIN products p ON p.product_id = oi.product_id
        LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
        WHERE o.order_status = 'delivered'
        GROUP BY category
        ORDER BY product_revenue DESC
        LIMIT {int(limit)}
    """)


# ── Seller performance ───────────────────────────────────────

def seller_leaderboard(min_orders: int = MIN_ORDERS_FOR_SELLER_RANK) -> pd.DataFrame:
    return run_query(f"""
        WITH seller_orders AS (
            SELECT oi.seller_id, oi.order_id, oi.price, oi.freight_value,
                   CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date
                        THEN 1 ELSE 0 END AS is_late
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            WHERE o.order_status = 'delivered'
        ),
        seller_reviews AS (
            SELECT oi.seller_id, AVG(r.review_score) AS avg_review_score
            FROM order_items oi
            JOIN reviews r ON r.order_id = oi.order_id
            GROUP BY oi.seller_id
        )
        SELECT
            so.seller_id, s.seller_state,
            COUNT(DISTINCT so.order_id)                  AS total_orders,
            ROUND(SUM(so.price + so.freight_value), 2)   AS total_revenue,
            ROUND(100.0 * SUM(so.is_late) / COUNT(*), 2) AS late_delivery_pct,
            ROUND(sr.avg_review_score, 2)                AS avg_review_score
        FROM seller_orders so
        JOIN sellers s ON s.seller_id = so.seller_id
        LEFT JOIN seller_reviews sr ON sr.seller_id = so.seller_id
        GROUP BY so.seller_id, s.seller_state
        HAVING COUNT(DISTINCT so.order_id) >= {int(min_orders)}
        ORDER BY total_revenue DESC
    """)


def at_risk_sellers(score_threshold: float = LOW_REVIEW_SCORE_THRESHOLD) -> pd.DataFrame:
    return run_query(f"""
        SELECT oi.seller_id, s.seller_state,
               COUNT(DISTINCT oi.order_id) AS orders,
               ROUND(AVG(r.review_score), 2) AS avg_review_score
        FROM order_items oi
        JOIN orders o  ON o.order_id = oi.order_id
        JOIN sellers s ON s.seller_id = oi.seller_id
        JOIN reviews r ON r.order_id = oi.order_id
        GROUP BY oi.seller_id, s.seller_state
        HAVING COUNT(DISTINCT oi.order_id) >= 5
           AND AVG(r.review_score) < {float(score_threshold)}
        ORDER BY avg_review_score ASC
    """)


# ── Delivery SLA ──────────────────────────────────────────────

def delivery_sla_overall() -> pd.DataFrame:
    return run_query("""
        SELECT
            COUNT(*) AS total_delivered,
            SUM(CASE WHEN order_delivered_customer_date <= order_estimated_delivery_date
                     THEN 1 ELSE 0 END) AS on_time,
            SUM(CASE WHEN order_delivered_customer_date > order_estimated_delivery_date
                     THEN 1 ELSE 0 END) AS late,
            ROUND(100.0 * SUM(CASE WHEN order_delivered_customer_date > order_estimated_delivery_date
                     THEN 1 ELSE 0 END) / COUNT(*), 2) AS late_pct
        FROM orders
        WHERE order_status = 'delivered'
          AND order_delivered_customer_date IS NOT NULL
          AND order_estimated_delivery_date IS NOT NULL
    """)


def delivery_by_state() -> pd.DataFrame:
    return run_query("""
        SELECT
            c.customer_state,
            COUNT(*) AS orders,
            ROUND(AVG(julianday(o.order_delivered_customer_date) - julianday(o.order_purchase_timestamp)), 1) AS avg_delivery_days,
            ROUND(100.0 * SUM(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date
                     THEN 1 ELSE 0 END) / COUNT(*), 2) AS late_pct
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL
        GROUP BY c.customer_state
        ORDER BY avg_delivery_days DESC
    """)


def delivery_trend_monthly() -> pd.DataFrame:
    return run_query("""
        SELECT
            strftime('%Y-%m', order_purchase_timestamp) AS month,
            COUNT(*) AS orders,
            ROUND(AVG(julianday(order_delivered_customer_date) - julianday(order_purchase_timestamp)), 1) AS avg_delivery_days,
            ROUND(100.0 * SUM(CASE WHEN order_delivered_customer_date > order_estimated_delivery_date
                     THEN 1 ELSE 0 END) / COUNT(*), 2) AS late_pct
        FROM orders
        WHERE order_status = 'delivered'
          AND order_delivered_customer_date IS NOT NULL
        GROUP BY month
        ORDER BY month
    """)


# ── Customer LTV / RFM / churn ────────────────────────────────

def repeat_purchase_rate() -> pd.DataFrame:
    return run_query("""
        WITH customer_order_counts AS (
            SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS n_orders
            FROM orders o
            JOIN customers c ON c.customer_id = o.customer_id
            WHERE o.order_status = 'delivered'
            GROUP BY c.customer_unique_id
        )
        SELECT
            COUNT(*) AS total_customers,
            SUM(CASE WHEN n_orders = 1 THEN 1 ELSE 0 END) AS one_time_customers,
            SUM(CASE WHEN n_orders > 1 THEN 1 ELSE 0 END) AS repeat_customers,
            ROUND(100.0 * SUM(CASE WHEN n_orders > 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS repeat_rate_pct
        FROM customer_order_counts
    """)


def rfm_segments() -> pd.DataFrame:
    return run_query("""
        WITH customer_orders AS (
            SELECT c.customer_unique_id, o.order_id, o.order_purchase_timestamp,
                   SUM(oi.price + oi.freight_value) AS order_value
            FROM orders o
            JOIN customers c    ON c.customer_id = o.customer_id
            JOIN order_items oi ON oi.order_id = o.order_id
            WHERE o.order_status = 'delivered'
            GROUP BY c.customer_unique_id, o.order_id, o.order_purchase_timestamp
        ),
        rfm_base AS (
            SELECT
                customer_unique_id,
                CAST(julianday((SELECT MAX(order_purchase_timestamp) FROM customer_orders))
                     - julianday(MAX(order_purchase_timestamp)) AS INTEGER) AS recency_days,
                COUNT(order_id) AS frequency,
                ROUND(SUM(order_value), 2) AS monetary
            FROM customer_orders
            GROUP BY customer_unique_id
        ),
        rfm_scored AS (
            SELECT *,
                NTILE(4) OVER (ORDER BY recency_days DESC) AS r_score,
                NTILE(4) OVER (ORDER BY frequency ASC)     AS f_score,
                NTILE(4) OVER (ORDER BY monetary ASC)      AS m_score
            FROM rfm_base
        )
        SELECT *,
            (r_score + f_score + m_score) AS rfm_total,
            CASE
                WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Champions'
                WHEN r_score >= 3 AND f_score <= 2                  THEN 'New / Promising'
                WHEN r_score <= 2 AND f_score >= 3 AND m_score >= 3 THEN 'At Risk (high value)'
                WHEN r_score <= 2 AND f_score <= 2                  THEN 'Churned / Lost'
                ELSE 'Needs Attention'
            END AS rfm_segment
        FROM rfm_scored
    """)


def rfm_segment_summary() -> pd.DataFrame:
    rfm = rfm_segments()
    return (
        rfm.groupby("rfm_segment")
           .agg(customers=("customer_unique_id", "count"), total_monetary=("monetary", "sum"))
           .reset_index()
           .sort_values("total_monetary", ascending=False)
    )


def churn_risk_count(inactivity_days: int = CHURN_INACTIVITY_DAYS) -> pd.DataFrame:
    return run_query(f"""
        SELECT COUNT(*) AS churn_risk_customers
        FROM (
            SELECT c.customer_unique_id,
                   MAX(o.order_purchase_timestamp) AS last_order,
                   COUNT(DISTINCT o.order_id) AS n_orders
            FROM orders o
            JOIN customers c ON c.customer_id = o.customer_id
            WHERE o.order_status = 'delivered'
            GROUP BY c.customer_unique_id
            HAVING n_orders = 1
        ) t
        WHERE julianday((SELECT MAX(order_purchase_timestamp) FROM orders))
              - julianday(last_order) > {int(inactivity_days)}
    """)


def cohort_retention() -> pd.DataFrame:
    return run_query("""
        WITH first_purchase AS (
            SELECT c.customer_unique_id,
                   MIN(strftime('%Y-%m', o.order_purchase_timestamp)) AS cohort_month
            FROM orders o
            JOIN customers c ON c.customer_id = o.customer_id
            WHERE o.order_status = 'delivered'
            GROUP BY c.customer_unique_id
        ),
        activity AS (
            SELECT c.customer_unique_id,
                   strftime('%Y-%m', o.order_purchase_timestamp) AS activity_month
            FROM orders o
            JOIN customers c ON c.customer_id = o.customer_id
            WHERE o.order_status = 'delivered'
        )
        SELECT fp.cohort_month, a.activity_month,
               COUNT(DISTINCT a.customer_unique_id) AS active_customers
        FROM first_purchase fp
        JOIN activity a ON a.customer_unique_id = fp.customer_unique_id
        GROUP BY fp.cohort_month, a.activity_month
        ORDER BY fp.cohort_month, a.activity_month
    """)
