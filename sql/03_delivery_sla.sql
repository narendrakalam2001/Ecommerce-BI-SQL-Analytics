-- ============================================================
-- DELIVERY SLA & LOGISTICS
-- ============================================================

-- 3.1 Overall on-time vs late delivery rate
SELECT
    COUNT(*)                                                          AS total_delivered,
    SUM(CASE WHEN order_delivered_customer_date
             <= order_estimated_delivery_date THEN 1 ELSE 0 END)      AS on_time,
    SUM(CASE WHEN order_delivered_customer_date
             > order_estimated_delivery_date THEN 1 ELSE 0 END)       AS late,
    ROUND(100.0 * SUM(CASE WHEN order_delivered_customer_date
             > order_estimated_delivery_date THEN 1 ELSE 0 END)
          / COUNT(*), 2)                                              AS late_pct
FROM orders
WHERE order_status = 'delivered'
  AND order_delivered_customer_date IS NOT NULL
  AND order_estimated_delivery_date IS NOT NULL;

-- 3.2 Average delivery time (purchase -> delivered) by customer state
SELECT
    c.customer_state,
    COUNT(*)                                                              AS orders,
    ROUND(AVG(julianday(o.order_delivered_customer_date)
              - julianday(o.order_purchase_timestamp)), 1)                AS avg_delivery_days,
    ROUND(AVG(julianday(o.order_estimated_delivery_date)
              - julianday(o.order_purchase_timestamp)), 1)                AS avg_estimated_days,
    ROUND(100.0 * SUM(CASE WHEN o.order_delivered_customer_date
             > o.order_estimated_delivery_date THEN 1 ELSE 0 END)
          / COUNT(*), 2)                                                  AS late_pct
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
GROUP BY c.customer_state
ORDER BY avg_delivery_days DESC;

-- 3.3 Delivery time trend by month (are we getting faster or slower?)
SELECT
    strftime('%Y-%m', order_purchase_timestamp)                        AS month,
    COUNT(*)                                                            AS orders,
    ROUND(AVG(julianday(order_delivered_customer_date)
              - julianday(order_purchase_timestamp)), 1)                AS avg_delivery_days,
    ROUND(100.0 * SUM(CASE WHEN order_delivered_customer_date
             > order_estimated_delivery_date THEN 1 ELSE 0 END)
          / COUNT(*), 2)                                                AS late_pct
FROM orders
WHERE order_status = 'delivered'
  AND order_delivered_customer_date IS NOT NULL
GROUP BY month
ORDER BY month;

-- 3.4 Freight cost as a percentage of product price, by category (logistics efficiency)
SELECT
    COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
    COUNT(*)                                       AS items,
    ROUND(AVG(oi.price), 2)                        AS avg_price,
    ROUND(AVG(oi.freight_value), 2)                AS avg_freight,
    ROUND(100.0 * AVG(oi.freight_value) / NULLIF(AVG(oi.price), 0), 2) AS freight_pct_of_price
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
GROUP BY category
HAVING COUNT(*) >= 30
ORDER BY freight_pct_of_price DESC;

-- 3.5 Delivery speed bucket distribution (fast / normal / late) and review-score correlation
WITH delivery AS (
    SELECT
        o.order_id,
        julianday(o.order_delivered_customer_date) - julianday(o.order_purchase_timestamp) AS delivery_days,
        CASE
            WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 'late'
            WHEN julianday(o.order_delivered_customer_date)
                 - julianday(o.order_purchase_timestamp) <= 3 THEN 'fast'
            ELSE 'on_time'
        END AS speed_bucket
    FROM orders o
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
)
SELECT
    d.speed_bucket,
    COUNT(*)                        AS orders,
    ROUND(AVG(d.delivery_days), 1)  AS avg_delivery_days,
    ROUND(AVG(r.review_score), 2)   AS avg_review_score
FROM delivery d
LEFT JOIN reviews r ON r.order_id = d.order_id
GROUP BY d.speed_bucket
ORDER BY avg_review_score DESC;
