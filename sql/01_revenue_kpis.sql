-- ============================================================
-- REVENUE KPIs
-- ============================================================

-- 1.1 Monthly gross revenue, order count, and AOV (delivered orders only)
SELECT
    strftime('%Y-%m', o.order_purchase_timestamp)              AS month,
    COUNT(DISTINCT o.order_id)                                  AS orders,
    ROUND(SUM(oi.price + oi.freight_value), 2)                  AS gross_revenue,
    ROUND(SUM(oi.price), 2)                                     AS product_revenue,
    ROUND(SUM(oi.freight_value), 2)                             AS freight_revenue,
    ROUND(SUM(oi.price + oi.freight_value)
          / COUNT(DISTINCT o.order_id), 2)                      AS avg_order_value
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY month
ORDER BY month;

-- 1.2 Revenue by Brazilian state (customer geography)
SELECT
    c.customer_state,
    COUNT(DISTINCT o.order_id)                    AS orders,
    ROUND(SUM(oi.price + oi.freight_value), 2)    AS gross_revenue,
    ROUND(100.0 * SUM(oi.price + oi.freight_value)
          / (SELECT SUM(oi2.price + oi2.freight_value)
             FROM order_items oi2
             JOIN orders o2 ON o2.order_id = oi2.order_id
             WHERE o2.order_status = 'delivered'), 2)   AS pct_of_total_revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN customers c    ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
GROUP BY c.customer_state
ORDER BY gross_revenue DESC;

-- 1.3 Top 10 product categories by revenue (English category names)
SELECT
    COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
    COUNT(DISTINCT oi.order_id)                    AS orders,
    ROUND(SUM(oi.price), 2)                        AS product_revenue,
    ROUND(AVG(oi.price), 2)                        AS avg_item_price
FROM order_items oi
JOIN orders o     ON o.order_id = oi.order_id
JOIN products p   ON p.product_id = oi.product_id
LEFT JOIN category_translation t
       ON t.product_category_name = p.product_category_name
WHERE o.order_status = 'delivered'
GROUP BY category
ORDER BY product_revenue DESC
LIMIT 10;

-- 1.4 Month-over-month revenue growth rate
WITH monthly AS (
    SELECT
        strftime('%Y-%m', o.order_purchase_timestamp)  AS month,
        SUM(oi.price + oi.freight_value)                AS revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY month
)
SELECT
    month,
    ROUND(revenue, 2)                                              AS revenue,
    ROUND(revenue - LAG(revenue) OVER (ORDER BY month), 2)         AS mom_change,
    ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
          / NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 2)      AS mom_growth_pct
FROM monthly
ORDER BY month;

-- 1.5 Revenue by payment type
SELECT
    pay.payment_type,
    COUNT(DISTINCT pay.order_id)              AS orders,
    ROUND(SUM(pay.payment_value), 2)          AS total_payment_value,
    ROUND(AVG(pay.payment_installments), 2)   AS avg_installments
FROM payments pay
JOIN orders o ON o.order_id = pay.order_id
WHERE o.order_status = 'delivered'
GROUP BY pay.payment_type
ORDER BY total_payment_value DESC;
