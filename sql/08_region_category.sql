-- 08_region_category.sql — where (geography, lane, category) the promise breaks most.

-- name: state_performance
SELECT customer_state,
       COUNT(*)                      AS orders,
       AVG(is_late::INT)             AS late_rate,
       AVG(promised_days)            AS avg_promised_days,
       AVG(actual_days)              AS avg_actual_days,
       AVG(review_score)             AS avg_score
FROM fct_orders
GROUP BY customer_state
HAVING COUNT(*) >= 300
ORDER BY late_rate DESC;

-- name: distance_bands
SELECT CASE WHEN distance_km < 100  THEN '1 <100 km'
            WHEN distance_km < 500  THEN '2 100-500 km'
            WHEN distance_km < 1000 THEN '3 500-1,000 km'
            WHEN distance_km < 2000 THEN '4 1,000-2,000 km'
            ELSE '5 2,000+ km' END    AS distance_band,
       COUNT(*)                      AS orders,
       AVG(is_late::INT)             AS late_rate,
       AVG(promised_days)            AS avg_promised_days,
       AVG(actual_days)              AS avg_actual_days,
       AVG(promised_days - actual_days) AS avg_buffer_days,
       AVG(review_score)             AS avg_score
FROM fct_orders
WHERE distance_km IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- name: worst_lanes
-- Seller-state → customer-state lanes with >= 300 orders, ranked by late rate.
SELECT seller_state || ' → ' || customer_state  AS lane,
       COUNT(*)                                AS orders,
       AVG(is_late::INT)                       AS late_rate,
       COUNT(*) FILTER (WHERE is_late)         AS late_orders,
       AVG(actual_days)                        AS avg_actual_days,
       AVG(promised_days)                      AS avg_promised_days,
       MEDIAN(distance_km)                     AS median_distance_km
FROM fct_orders
WHERE seller_state IS NOT NULL
GROUP BY 1
HAVING COUNT(*) >= 300
ORDER BY late_rate DESC
LIMIT 10;

-- name: lane_excess_late
-- Lanes with >= 300 orders ranked by EXCESS late orders: actual late orders minus what the lane would
-- have at the platform-wide late rate. Big lanes don't win just by being big.
WITH overall AS (SELECT AVG(is_late::INT) AS rate FROM fct_orders),
lanes AS (
    SELECT seller_state || ' → ' || customer_state AS lane,
           COUNT(*)                                AS orders,
           COUNT(*) FILTER (WHERE is_late)         AS late_orders,
           AVG(is_late::INT)                       AS late_rate,
           MEDIAN(distance_km)                     AS median_distance_km
    FROM fct_orders
    WHERE seller_state IS NOT NULL
    GROUP BY 1
    HAVING COUNT(*) >= 300
)
SELECT l.*,
       l.orders * o.rate                          AS expected_late_at_platform_rate,
       l.late_orders - l.orders * o.rate          AS excess_late_orders,
       RANK() OVER (ORDER BY l.late_orders DESC)  AS rank_by_late_orders
FROM lanes l CROSS JOIN overall o
ORDER BY excess_late_orders DESC;

-- name: category_performance
-- Top 15 categories by volume: how often late, and how hard lateness hits their score.
WITH c AS (
    SELECT primary_category,
           COUNT(*)                                          AS reviewed_orders,
           AVG(is_late::INT)                                 AS late_rate,
           AVG(review_score) FILTER (WHERE NOT is_late)      AS ontime_avg_score,
           AVG(review_score) FILTER (WHERE is_late)          AS late_avg_score,
           MEDIAN(weight_g)                                  AS median_weight_g
    FROM fct_reviewed
    GROUP BY 1
)
SELECT *, ontime_avg_score - late_avg_score AS score_gap,
       late_rate * (ontime_avg_score - late_avg_score) AS rating_drag
FROM c
ORDER BY reviewed_orders DESC
LIMIT 15;
