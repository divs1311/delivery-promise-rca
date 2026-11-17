-- 05_confounder_control.sql — is it lateness, or just WHO gets late orders?
-- Late orders skew to remote states and certain categories, which might be rated lower anyway.
-- Compare late vs on-time orders WITHIN the same cell, then average the within-cell gaps weighted
-- by each cell's late orders (an exact-stratification estimate of the effect on late orders).
-- Cells need >= 5 late and >= 5 on-time reviewed orders.

-- name: stratified_gap_state_category
WITH cells AS (
    SELECT customer_state, primary_category,
           COUNT(*) FILTER (WHERE is_late)                    AS late_n,
           COUNT(*) FILTER (WHERE NOT is_late)                AS ontime_n,
           AVG(review_score) FILTER (WHERE is_late)           AS late_avg,
           AVG(review_score) FILTER (WHERE NOT is_late)       AS ontime_avg
    FROM fct_reviewed
    GROUP BY 1, 2
),
eligible AS (SELECT * FROM cells WHERE late_n >= 5 AND ontime_n >= 5)
SELECT
    'customer state × product category'                         AS stratification,
    (SELECT COUNT(*) FROM eligible)                              AS cells_used,
    (SELECT SUM(late_n) FROM eligible)::DOUBLE
        / (SELECT SUM(late_n) FROM cells)                        AS late_orders_covered,
    (SELECT AVG(review_score) FILTER (WHERE NOT is_late) - AVG(review_score) FILTER (WHERE is_late)
       FROM fct_reviewed)                                        AS naive_gap,
    SUM(late_n * (ontime_avg - late_avg)) / SUM(late_n)          AS adjusted_gap
FROM eligible;

-- name: stratified_gap_distance_value_items
WITH banded AS (
    SELECT *,
           NTILE(4) OVER (ORDER BY distance_km)  AS distance_q,
           NTILE(4) OVER (ORDER BY items_value)  AS value_q,
           LEAST(n_items, 2)                     AS items_band
    FROM fct_reviewed
    WHERE distance_km IS NOT NULL
),
cells AS (
    SELECT distance_q, value_q, items_band,
           COUNT(*) FILTER (WHERE is_late)                    AS late_n,
           COUNT(*) FILTER (WHERE NOT is_late)                AS ontime_n,
           AVG(review_score) FILTER (WHERE is_late)           AS late_avg,
           AVG(review_score) FILTER (WHERE NOT is_late)       AS ontime_avg
    FROM banded
    GROUP BY 1, 2, 3
),
eligible AS (SELECT * FROM cells WHERE late_n >= 5 AND ontime_n >= 5)
SELECT
    'distance quartile × order value quartile × single/multi item' AS stratification,
    (SELECT COUNT(*) FROM eligible)                              AS cells_used,
    (SELECT SUM(late_n) FROM eligible)::DOUBLE
        / (SELECT SUM(late_n) FROM cells)                        AS late_orders_covered,
    (SELECT AVG(review_score) FILTER (WHERE NOT is_late) - AVG(review_score) FILTER (WHERE is_late)
       FROM banded)                                              AS naive_gap,
    SUM(late_n * (ontime_avg - late_avg)) / SUM(late_n)          AS adjusted_gap
FROM eligible;
