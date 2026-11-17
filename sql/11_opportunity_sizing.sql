-- 11_opportunity_sizing.sql — what is fixing each root cause worth?
--
-- Assumption (stated in the README): a late order that becomes on time gets the review behaviour of
-- on-time orders. "Naive" uses the raw on-time vs late gap; "adjusted" scales it by
-- adjusted_gap / naive_gap from the state × category stratification (05), which strips out the part
-- of the gap explained by where and what customers ordered.
-- Scenarios:
--   A  Seller hand-over fixed: orders labelled "Seller hand-over only" arrive on time
--   B  Every late order arrives on time (upper bound = rating drag)

-- name: opportunity_sizing
WITH reviewed AS (SELECT * FROM fct_reviewed),
ontime AS (
    SELECT AVG(review_score) AS avg_score, AVG((review_score <= 2)::INT) AS pct12
    FROM reviewed WHERE NOT is_late
),
totals AS (
    SELECT COUNT(*) AS n_reviewed, SUM((review_score <= 2)::INT) AS n12 FROM reviewed
),
-- adjustment factor from the state × category stratification
cells AS (
    SELECT customer_state, primary_category,
           COUNT(*) FILTER (WHERE is_late)               AS late_n,
           COUNT(*) FILTER (WHERE NOT is_late)           AS ontime_n,
           AVG(review_score) FILTER (WHERE is_late)      AS late_avg,
           AVG(review_score) FILTER (WHERE NOT is_late)  AS ontime_avg
    FROM reviewed GROUP BY 1, 2
),
adj AS (
    SELECT (SELECT SUM(late_n * (ontime_avg - late_avg)) / SUM(late_n)
              FROM cells WHERE late_n >= 5 AND ontime_n >= 5)
         / (SELECT AVG(review_score) FILTER (WHERE NOT is_late) - AVG(review_score) FILTER (WHERE is_late)
              FROM reviewed) AS factor
),
scenarios AS (
    SELECT 'A Seller hand-over fixed (seller-only late orders on time)' AS scenario,
           COUNT(*) AS orders_fixed, AVG(review_score) AS avg_score, AVG((review_score <= 2)::INT) AS pct12
    FROM v_late_root_cause WHERE has_review AND root_cause = '1 Seller hand-over only'
    UNION ALL
    SELECT 'B Every late order on time (upper bound)',
           COUNT(*), AVG(review_score), AVG((review_score <= 2)::INT)
    FROM reviewed WHERE is_late
)
SELECT s.scenario,
       s.orders_fixed,
       s.orders_fixed::DOUBLE / t.n_reviewed                                   AS share_of_reviewed_orders,
       s.orders_fixed::DOUBLE / t.n_reviewed * (o.avg_score - s.avg_score)     AS avg_score_uplift_naive,
       s.orders_fixed::DOUBLE / t.n_reviewed * (o.avg_score - s.avg_score) * a.factor AS avg_score_uplift_adjusted,
       s.orders_fixed * (s.pct12 - o.pct12)                                    AS one_two_star_reviews_avoided_naive,
       s.orders_fixed * (s.pct12 - o.pct12) / t.n12                            AS share_of_all_1_2_star_avoided_naive,
       a.factor                                                                AS adjustment_factor
FROM scenarios s CROSS JOIN ontime o CROSS JOIN totals t CROSS JOIN adj a
ORDER BY s.scenario;
