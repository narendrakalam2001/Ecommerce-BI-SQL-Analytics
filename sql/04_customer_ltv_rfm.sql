-- ============================================================
-- CUSTOMER LIFETIME VALUE, RFM SEGMENTATION & CHURN
-- ============================================================

-- 4.1 Customer-level order history & lifetime value (Olist: mostly single-purchase customers,
--     so customer_unique_id is used to link repeat customers across customer_id records)
WITH customer_orders AS (
    SELECT
        c.customer_unique_id,
        o.order_id,
        o.order_purchase_timestamp,
        SUM(oi.price + oi.freight_value) AS order_value
    FROM orders o
    JOIN customers c    ON c.customer_id = o.customer_id
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id, o.order_id, o.order_purchase_timestamp
)
SELECT
    customer_unique_id,
    COUNT(order_id)                          AS total_orders,
    ROUND(SUM(order_value), 2)               AS lifetime_value,
    ROUND(AVG(order_value), 2)               AS avg_order_value,
    MIN(order_purchase_timestamp)            AS first_order_date,
    MAX(order_purchase_timestamp)            AS last_order_date
FROM customer_orders
GROUP BY customer_unique_id
ORDER BY lifetime_value DESC;

-- 4.2 Repeat-purchase rate (the single most important CLV signal on Olist)
WITH customer_order_counts AS (
    SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS n_orders
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
)
SELECT
    COUNT(*)                                                      AS total_customers,
    SUM(CASE WHEN n_orders = 1 THEN 1 ELSE 0 END)                 AS one_time_customers,
    SUM(CASE WHEN n_orders > 1 THEN 1 ELSE 0 END)                 AS repeat_customers,
    ROUND(100.0 * SUM(CASE WHEN n_orders > 1 THEN 1 ELSE 0 END)
          / COUNT(*), 2)                                          AS repeat_rate_pct
FROM customer_order_counts;

-- 4.3 RFM segmentation (Recency / Frequency / Monetary, quartile-scored 1-4)
-- Recency is computed relative to the most recent purchase date in the dataset.
WITH customer_orders AS (
    SELECT
        c.customer_unique_id,
        o.order_id,
        o.order_purchase_timestamp,
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
        COUNT(order_id)             AS frequency,
        ROUND(SUM(order_value), 2)  AS monetary
    FROM customer_orders
    GROUP BY customer_unique_id
),
rfm_scored AS (
    SELECT
        *,
        NTILE(4) OVER (ORDER BY recency_days DESC) AS r_score,   -- lower recency_days = more recent = higher score
        NTILE(4) OVER (ORDER BY frequency ASC)     AS f_score,
        NTILE(4) OVER (ORDER BY monetary ASC)      AS m_score
    FROM rfm_base
)
SELECT
    *,
    (r_score + f_score + m_score)          AS rfm_total,
    CASE
        WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Champions'
        WHEN r_score >= 3 AND f_score <= 2                  THEN 'New / Promising'
        WHEN r_score <= 2 AND f_score >= 3 AND m_score >= 3  THEN 'At Risk (high value)'
        WHEN r_score <= 2 AND f_score <= 2                  THEN 'Churned / Lost'
        ELSE 'Needs Attention'
    END AS rfm_segment
FROM rfm_scored
ORDER BY rfm_total DESC;

-- 4.4 Churn-risk count: customers with a single purchase > N days ago (no repeat signal)
SELECT
    COUNT(*) AS churn_risk_customers
FROM (
    SELECT
        c.customer_unique_id,
        MAX(o.order_purchase_timestamp) AS last_order,
        COUNT(DISTINCT o.order_id)      AS n_orders
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
    HAVING n_orders = 1
) t
WHERE julianday((SELECT MAX(order_purchase_timestamp) FROM orders))
      - julianday(last_order) > 180;    -- CHURN_INACTIVITY_DAYS

-- 4.5 Monthly cohort retention (cohort = month of first purchase)
WITH first_purchase AS (
    SELECT
        c.customer_unique_id,
        MIN(strftime('%Y-%m', o.order_purchase_timestamp)) AS cohort_month
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
),
activity AS (
    SELECT
        c.customer_unique_id,
        strftime('%Y-%m', o.order_purchase_timestamp) AS activity_month
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
)
SELECT
    fp.cohort_month,
    a.activity_month,
    COUNT(DISTINCT a.customer_unique_id) AS active_customers
FROM first_purchase fp
JOIN activity a ON a.customer_unique_id = fp.customer_unique_id
GROUP BY fp.cohort_month, a.activity_month
ORDER BY fp.cohort_month, a.activity_month;
