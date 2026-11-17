-- 09_promise_backtest.sql — are delivery promises set well?
-- Olist promises ~24 days on average but delivers in ~12. Padding protects the on-time rate, but a
-- long promise shown at checkout can cost conversion (not measurable in this dataset).
-- Test: set each order's promise from HISTORY only. Learn delivery-time percentiles per
-- seller-state → customer-state lane on 2017 orders, apply them to Jan–Aug 2018 orders, and compare
-- with the promises Olist actually made on those same 2018 orders.
-- Lane needs >= 30 training orders, else fall back to the customer state, else to all orders.
-- Promises are whole days (rounded up).

-- name: promise_padding
SELECT CASE WHEN promised_days - actual_days < 0   THEN '1 late (promise too short)'
            WHEN promised_days - actual_days <= 3  THEN '2 0-3 days spare'
            WHEN promised_days - actual_days <= 7  THEN '3 4-7 days spare'
            WHEN promised_days - actual_days <= 14 THEN '4 8-14 days spare'
            ELSE '5 15+ days spare' END            AS buffer_band,
       COUNT(*)                                    AS orders,
       COUNT(*) / SUM(COUNT(*)) OVER ()            AS share
FROM fct_orders
GROUP BY 1
ORDER BY 1;

-- name: promise_backtest
WITH train AS (SELECT * FROM fct_orders WHERE purchase_ts <  TIMESTAMP '2018-01-01'),
test  AS (SELECT * FROM fct_orders WHERE purchase_ts >= TIMESTAMP '2018-01-01'),
lane_q AS (
    SELECT seller_state, customer_state,
           QUANTILE_CONT(actual_days, 0.80) AS p80, QUANTILE_CONT(actual_days, 0.85) AS p85,
           QUANTILE_CONT(actual_days, 0.90) AS p90, QUANTILE_CONT(actual_days, 0.95) AS p95
    FROM train WHERE seller_state IS NOT NULL
    GROUP BY 1, 2 HAVING COUNT(*) >= 30
),
state_q AS (
    SELECT customer_state,
           QUANTILE_CONT(actual_days, 0.80) AS p80, QUANTILE_CONT(actual_days, 0.85) AS p85,
           QUANTILE_CONT(actual_days, 0.90) AS p90, QUANTILE_CONT(actual_days, 0.95) AS p95
    FROM train GROUP BY 1
),
all_q AS (
    SELECT QUANTILE_CONT(actual_days, 0.80) AS p80, QUANTILE_CONT(actual_days, 0.85) AS p85,
           QUANTILE_CONT(actual_days, 0.90) AS p90, QUANTILE_CONT(actual_days, 0.95) AS p95
    FROM train
),
scored AS (
    SELECT t.actual_days, t.promised_days AS olist_promise,
           CEIL(COALESCE(l.p80, s.p80, a.p80)) AS p80_promise,
           CEIL(COALESCE(l.p85, s.p85, a.p85)) AS p85_promise,
           CEIL(COALESCE(l.p90, s.p90, a.p90)) AS p90_promise,
           CEIL(COALESCE(l.p95, s.p95, a.p95)) AS p95_promise,
           (l.p90 IS NOT NULL) AS lane_level
    FROM test t
    LEFT JOIN lane_q  l ON l.seller_state = t.seller_state AND l.customer_state = t.customer_state
    LEFT JOIN state_q s ON s.customer_state = t.customer_state
    CROSS JOIN all_q a
),
policies AS (
    SELECT '0 Olist actual promise' AS policy, olist_promise AS promise, actual_days, lane_level FROM scored
    UNION ALL SELECT '1 Lane P80 (history)', p80_promise, actual_days, lane_level FROM scored
    UNION ALL SELECT '2 Lane P85 (history)', p85_promise, actual_days, lane_level FROM scored
    UNION ALL SELECT '3 Lane P90 (history)', p90_promise, actual_days, lane_level FROM scored
    UNION ALL SELECT '4 Lane P95 (history)', p95_promise, actual_days, lane_level FROM scored
)
SELECT policy,
       COUNT(*)                                  AS test_orders,
       AVG((actual_days <= promise)::INT)        AS on_time_rate,
       AVG(promise)                              AS avg_promised_days,
       MEDIAN(promise)                           AS median_promised_days,
       AVG(lane_level::INT)                      AS share_lane_level
FROM policies
GROUP BY policy
ORDER BY policy;

-- name: promise_backtest_adaptive
-- Same idea, but the history adapts week by week: for each week of 2018, learn lane percentiles from
-- orders purchased 45–135 days before that week (≈99% of orders arrive within 45 days, so the
-- window is not biased towards fast deliveries). Fallback: customer state for that week.
WITH test AS (SELECT * FROM fct_orders WHERE purchase_ts >= TIMESTAMP '2018-01-01' AND seller_state IS NOT NULL),
weeks AS (SELECT DISTINCT DATE_TRUNC('week', purchase_ts) AS wk FROM test),
hist AS (
    SELECT w.wk, f.seller_state, f.customer_state, f.actual_days
    FROM weeks w
    JOIN fct_orders f ON f.purchase_ts >= w.wk - INTERVAL 135 DAY AND f.purchase_ts < w.wk - INTERVAL 45 DAY
),
lane_w AS (
    SELECT wk, seller_state, customer_state,
           QUANTILE_CONT(actual_days, 0.90) AS p90, QUANTILE_CONT(actual_days, 0.95) AS p95
    FROM hist GROUP BY 1, 2, 3 HAVING COUNT(*) >= 30
),
state_w AS (
    SELECT wk, customer_state,
           QUANTILE_CONT(actual_days, 0.90) AS p90, QUANTILE_CONT(actual_days, 0.95) AS p95
    FROM hist GROUP BY 1, 2
),
scored AS (
    SELECT t.actual_days, t.promised_days AS olist_promise,
           CEIL(COALESCE(l.p90, s.p90)) AS p90_promise,
           CEIL(COALESCE(l.p95, s.p95)) AS p95_promise
    FROM test t
    LEFT JOIN lane_w  l ON l.wk = DATE_TRUNC('week', t.purchase_ts)
                       AND l.seller_state = t.seller_state AND l.customer_state = t.customer_state
    LEFT JOIN state_w s ON s.wk = DATE_TRUNC('week', t.purchase_ts) AND s.customer_state = t.customer_state
),
policies AS (
    SELECT '0 Olist actual promise' AS policy, olist_promise AS promise, actual_days FROM scored
    UNION ALL SELECT '1 Adaptive lane P90', p90_promise, actual_days FROM scored
    UNION ALL SELECT '2 Adaptive lane P95', p95_promise, actual_days FROM scored
)
SELECT policy, COUNT(*) AS test_orders, COUNT(promise) AS orders_with_promise,
       AVG((actual_days <= promise)::INT) AS on_time_rate,
       AVG(promise) AS avg_promised_days
FROM policies
GROUP BY policy
ORDER BY policy;

-- name: delivery_time_spread
-- Why the buffer exists: typical delivery vs the delivery time you can hit 92% of the time
-- (Olist's on-time rate), by distance.
SELECT CASE WHEN distance_km < 100  THEN '1 <100 km'
            WHEN distance_km < 500  THEN '2 100-500 km'
            WHEN distance_km < 1000 THEN '3 500-1,000 km'
            WHEN distance_km < 2000 THEN '4 1,000-2,000 km'
            ELSE '5 2,000+ km' END                    AS distance_band,
       COUNT(*)                                       AS orders,
       QUANTILE_CONT(actual_days, 0.50)               AS p50_actual_days,
       QUANTILE_CONT(actual_days, 0.92)               AS p92_actual_days,
       QUANTILE_CONT(actual_days, 0.92) - QUANTILE_CONT(actual_days, 0.50) AS spread_days,
       MEDIAN(promised_days)                          AS median_promised_days
FROM fct_orders
WHERE distance_km IS NOT NULL
GROUP BY 1
ORDER BY 1;
