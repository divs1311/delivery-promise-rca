-- 04_review_impact.sql — size the damage in one number: rating drag.
--
-- rating_drag = share_late × (avg score of on-time orders − avg score of late orders)
-- = exactly how much the average review score would rise if late orders were rated like on-time ones.

-- name: rating_drag
WITH g AS (
    SELECT is_late,
           COUNT(*)                         AS n,
           AVG(review_score)                AS avg_score,
           VAR_SAMP(review_score)           AS var_score,
           AVG((review_score <= 2)::INT)    AS pct_1_2_star,
           SUM((review_score <= 2)::INT)    AS n_1_2_star
    FROM fct_reviewed
    GROUP BY is_late
),
w AS (
    SELECT
        MAX(CASE WHEN is_late     THEN n END)            AS late_n,
        MAX(CASE WHEN NOT is_late THEN n END)            AS ontime_n,
        MAX(CASE WHEN is_late     THEN avg_score END)    AS late_avg_score,
        MAX(CASE WHEN NOT is_late THEN avg_score END)    AS ontime_avg_score,
        MAX(CASE WHEN is_late     THEN pct_1_2_star END) AS late_pct_1_2_star,
        MAX(CASE WHEN NOT is_late THEN pct_1_2_star END) AS ontime_pct_1_2_star,
        MAX(CASE WHEN is_late     THEN n_1_2_star END)   AS late_n_1_2_star,
        SUM(n_1_2_star)                                  AS all_n_1_2_star,
        SQRT(MAX(CASE WHEN is_late THEN var_score / n END) + MAX(CASE WHEN NOT is_late THEN var_score / n END)) AS gap_std_error
    FROM g
)
SELECT *,
       late_n::DOUBLE / (late_n + ontime_n)                                      AS share_late,
       ontime_avg_score - late_avg_score                                         AS score_gap,
       ontime_avg_score - late_avg_score - 1.96 * gap_std_error                  AS score_gap_ci_low,
       ontime_avg_score - late_avg_score + 1.96 * gap_std_error                  AS score_gap_ci_high,
       late_n::DOUBLE / (late_n + ontime_n) * (ontime_avg_score - late_avg_score) AS rating_drag,
       late_pct_1_2_star / ontime_pct_1_2_star                                    AS relative_risk_1_2_star,
       late_n_1_2_star::DOUBLE / all_n_1_2_star                                   AS share_of_all_1_2_star_from_late
FROM w;

-- name: review_timing_late_orders
-- Many late customers review BEFORE the parcel arrives (the survey goes out around the promised date).
SELECT
    review_before_delivery,
    COUNT(*)                         AS late_reviewed_orders,
    COUNT(*) / SUM(COUNT(*)) OVER () AS share,
    AVG(review_score)                AS avg_score,
    AVG((review_score <= 2)::INT)    AS pct_1_2_star
FROM fct_reviewed
WHERE is_late
GROUP BY review_before_delivery
ORDER BY review_before_delivery;
