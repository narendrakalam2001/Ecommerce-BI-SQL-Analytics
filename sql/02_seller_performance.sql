-- ============================================================
-- SELLER PERFORMANCE
-- ============================================================

-- 2.1 Seller leaderboard: revenue, orders, avg review score, late-delivery rate
WITH seller_orders AS (
    SELECT
        oi.seller_id,
        oi.order_id,
        oi.price,
        oi.freight_value,
        o.order_delivered_customer_date,
        o.order_estimated_delivery_date,
        CASE
            WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date
            THEN 1 ELSE 0
        END AS is_late
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
    so.seller_id,
    s.seller_state,
    COUNT(DISTINCT so.order_id)                          AS total_orders,
    ROUND(SUM(so.price + so.freight_value), 2)           AS total_revenue,
    ROUND(AVG(so.price), 2)                              AS avg_item_price,
    ROUND(100.0 * SUM(so.is_late) / COUNT(*), 2)         AS late_delivery_pct,
    ROUND(sr.avg_review_score, 2)                        AS avg_review_score
FROM seller_orders so
JOIN sellers s ON s.seller_id = so.seller_id
LEFT JOIN seller_reviews sr ON sr.seller_id = so.seller_id
GROUP BY so.seller_id, s.seller_state
HAVING COUNT(DISTINCT so.order_id) >= 5          -- MIN_ORDERS_FOR_SELLER_RANK
ORDER BY total_revenue DESC;

-- 2.2 Top 20 sellers by revenue
SELECT
    oi.seller_id,
    s.seller_city,
    s.seller_state,
    COUNT(DISTINCT oi.order_id)                   AS orders,
    ROUND(SUM(oi.price + oi.freight_value), 2)    AS revenue
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN sellers s ON s.seller_id = oi.seller_id
WHERE o.order_status = 'delivered'
GROUP BY oi.seller_id, s.seller_city, s.seller_state
ORDER BY revenue DESC
LIMIT 20;

-- 2.3 Sellers "at risk" — avg review score below threshold with meaningful volume
SELECT
    oi.seller_id,
    s.seller_state,
    COUNT(DISTINCT oi.order_id)          AS orders,
    ROUND(AVG(r.review_score), 2)        AS avg_review_score
FROM order_items oi
JOIN orders o    ON o.order_id = oi.order_id
JOIN sellers s   ON s.seller_id = oi.seller_id
JOIN reviews r   ON r.order_id = oi.order_id
GROUP BY oi.seller_id, s.seller_state
HAVING COUNT(DISTINCT oi.order_id) >= 5
   AND AVG(r.review_score) < 3            -- LOW_REVIEW_SCORE_THRESHOLD
ORDER BY avg_review_score ASC;

-- 2.4 Seller concentration — revenue share of top 10% of sellers (Pareto check)
WITH seller_rev AS (
    SELECT oi.seller_id, SUM(oi.price + oi.freight_value) AS revenue
    FROM order_items oi
    JOIN orders o ON o.order_id = oi.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY oi.seller_id
),
ranked AS (
    SELECT *, NTILE(10) OVER (ORDER BY revenue DESC) AS decile
    FROM seller_rev
)
SELECT
    decile,
    COUNT(*)                         AS sellers_in_decile,
    ROUND(SUM(revenue), 2)           AS decile_revenue,
    ROUND(100.0 * SUM(revenue) / (SELECT SUM(revenue) FROM seller_rev), 2) AS pct_of_total_revenue
FROM ranked
GROUP BY decile
ORDER BY decile;
