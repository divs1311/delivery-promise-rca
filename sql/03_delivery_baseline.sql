-- 03_delivery_baseline.sql — how often is the promise broken, and what does it do to reviews?

-- name: kpi_summary
SELECT
    COUNT(*)                                                         AS delivered_orders,
    AVG(is_late::INT)                                                AS late_rate,
    AVG(CASE WHEN is_late THEN days_late END)                        AS avg_days_late_when_late,
    MEDIAN(days_late)                                                AS median_days_vs_promise,      -- negative = early
    AVG(promised_days)                                               AS avg_promised_days,
    AVG(actual_days)                                                 AS avg_actual_days,
    AVG(has_review::INT)                                             AS review_coverage,
    AVG(review_score)                                                AS avg_review_score,
    AVG(CASE WHEN has_review THEN (review_score <= 2)::INT END)      AS pct_1_2_star
FROM fct_orders;

-- name: lateness_buckets
-- Dose-response: review outcome by how early/late the order arrived vs the promise.
SELECT
    lateness_bucket,
    COUNT(*)                                          AS reviewed_orders,
    COUNT(*) / SUM(COUNT(*)) OVER ()                  AS share_of_orders,
    AVG(review_score)                                 AS avg_score,
    AVG((review_score <= 2)::INT)                     AS pct_1_2_star,
    AVG((review_score = 5)::INT)                      AS pct_5_star
FROM fct_reviewed
GROUP BY lateness_bucket
ORDER BY lateness_bucket;
