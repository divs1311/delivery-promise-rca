-- 06_root_cause.sql — where does the delay come from: the seller or the carrier?
--
-- Labels come from view v_late_root_cause (sql/01_build_fact.sql).
-- Each seller has a shipping limit (deadline to hand the parcel to the carrier).
--   * Seller hand-over late = carrier pickup after the shipping limit.
-- Categories:
--   Seller hand-over only        seller late, counterfactual on time
--   Seller hand-over + carrier   seller late, still late even with an on-time hand-over
--   Carrier leg only             seller on time, delay happened in transit

-- name: late_attribution
SELECT root_cause,
       COUNT(*)                              AS late_orders,
       COUNT(*) / SUM(COUNT(*)) OVER ()      AS share_of_late,
       AVG(days_late)                        AS avg_days_late,
       AVG(review_score)                     AS avg_score,
       AVG((review_score <= 2)::INT)         AS pct_1_2_star
FROM v_late_root_cause
GROUP BY root_cause
ORDER BY root_cause;

-- name: handover_effect
-- How much more likely is an order to be late when the seller misses the hand-over deadline?
SELECT seller_handover_late,
       COUNT(*)                     AS orders,
       COUNT(*) / SUM(COUNT(*)) OVER () AS share_of_orders,
       AVG(is_late::INT)            AS late_rate,
       AVG(review_score)            AS avg_score
FROM fct_orders
WHERE n_sellers = 1 AND legs_valid
GROUP BY seller_handover_late
ORDER BY seller_handover_late;

-- name: leg_durations
-- Average time spent in each leg, on-time vs late orders (valid legs only).
SELECT is_late,
       COUNT(*)                                                                         AS orders,
       AVG(DATE_DIFF('hour', purchase_ts, approved_ts)) / 24.0                         AS avg_days_to_approve,
       AVG(DATE_DIFF('hour', purchase_ts, carrier_ts)) / 24.0                          AS avg_days_to_carrier,
       AVG(carrier_transit_days)                                                        AS avg_carrier_transit_days,
       AVG(actual_days)                                                                 AS avg_total_days,
       AVG(promised_days)                                                               AS avg_promised_days
FROM fct_orders
WHERE legs_valid AND approved_ts IS NOT NULL
GROUP BY is_late
ORDER BY is_late;
