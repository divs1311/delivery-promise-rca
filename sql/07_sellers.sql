-- 07_sellers.sql — are late hand-overs spread out or concentrated in a few sellers?
-- Single-seller orders with valid legs only.

-- name: seller_concentration
-- Pareto of "late orders where the seller also missed the hand-over deadline".
WITH per_seller AS (
    SELECT seller_id,
           COUNT(*)                                                    AS orders,
           COUNT(*) FILTER (WHERE is_late AND seller_handover_late)    AS seller_late_orders
    FROM fct_orders
    WHERE n_sellers = 1 AND legs_valid
    GROUP BY seller_id
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (ORDER BY seller_late_orders DESC, orders DESC, seller_id) AS rnk,
           COUNT(*) OVER ()                                                AS n_sellers_total,
           SUM(seller_late_orders) OVER ()                                 AS total_seller_late,
           SUM(orders) OVER ()                                             AS total_orders,
           SUM(seller_late_orders) OVER (ORDER BY seller_late_orders DESC, orders DESC, seller_id
                                         ROWS UNBOUNDED PRECEDING)         AS cum_seller_late,
           SUM(orders) OVER (ORDER BY seller_late_orders DESC, orders DESC, seller_id
                             ROWS UNBOUNDED PRECEDING)                     AS cum_orders
    FROM per_seller
)
SELECT p.top_pct_of_sellers,
       MAX(r.rnk)                                             AS sellers,
       MAX(r.cum_seller_late)::DOUBLE / MAX(r.total_seller_late) AS share_of_seller_late_orders,
       MAX(r.cum_orders)::DOUBLE / MAX(r.total_orders)        AS share_of_all_orders
FROM (VALUES (0.01), (0.05), (0.10), (0.20)) AS p(top_pct_of_sellers)
JOIN ranked r ON r.rnk <= CEIL(p.top_pct_of_sellers * r.n_sellers_total)
GROUP BY p.top_pct_of_sellers
ORDER BY p.top_pct_of_sellers;

-- name: seller_late_handover_reach
-- How many sellers ever cause a late order by handing over late?
WITH per_seller AS (
    SELECT seller_id, COUNT(*) FILTER (WHERE is_late AND seller_handover_late) AS seller_late_orders
    FROM fct_orders WHERE n_sellers = 1 AND legs_valid GROUP BY seller_id
)
SELECT COUNT(*)                                          AS sellers,
       COUNT(*) FILTER (WHERE seller_late_orders > 0)    AS sellers_with_any,
       COUNT(*) FILTER (WHERE seller_late_orders > 0)::DOUBLE / COUNT(*) AS share_with_any
FROM per_seller;

-- name: seller_scorecard
-- Sellers with >= 30 orders, banded by how often they miss the hand-over deadline.
WITH per_seller AS (
    SELECT seller_id,
           COUNT(*)                          AS orders,
           AVG(seller_handover_late::INT)    AS handover_late_rate,
           AVG(is_late::INT)                 AS late_rate,
           AVG(review_score)                 AS avg_score
    FROM fct_orders
    WHERE n_sellers = 1 AND legs_valid
    GROUP BY seller_id
    HAVING COUNT(*) >= 30
)
SELECT CASE WHEN handover_late_rate < 0.05 THEN '1 <5% late hand-overs'
            WHEN handover_late_rate < 0.10 THEN '2 5-10%'
            WHEN handover_late_rate < 0.20 THEN '3 10-20%'
            ELSE '4 20%+' END                               AS seller_band,
       COUNT(*)                                             AS sellers,
       SUM(orders)                                          AS orders,
       SUM(orders) / SUM(SUM(orders)) OVER ()               AS share_of_orders,
       SUM(orders * late_rate) / SUM(orders)                AS late_rate,
       SUM(orders * avg_score) / SUM(orders)                AS avg_score
FROM per_seller
GROUP BY 1
ORDER BY 1;
