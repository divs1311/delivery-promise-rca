-- 10_review_text_trend.sql — what unhappy customers write, and how it moves over time.

-- name: low_score_comment_topics
-- 1–2★ reviews that have text. Reviews are in Portuguese; patterns:
--   delivery terms: entreg(a/ue), receb(i), cheg(ou), atras(o), prazo, correio(s), transportadora, rastrei(o)
--   not received:   "não recebi", "não chegou", "não foi entregue", "ainda não"
WITH t AS (
    SELECT is_late,
           LOWER(COALESCE(review_comment_title, '') || ' ' || COALESCE(review_comment_message, '')) AS txt
    FROM fct_reviewed
    WHERE review_score <= 2
      AND (review_comment_message IS NOT NULL OR review_comment_title IS NOT NULL)
)
SELECT is_late,
       COUNT(*)                                                                                     AS low_score_reviews_with_text,
       AVG(REGEXP_MATCHES(txt, 'entreg|receb|cheg|atras|prazo|correio|transportadora|rastrei')::INT) AS share_mention_delivery,
       AVG(REGEXP_MATCHES(txt, 'n[aã]o (recebi|chegou|foi entregue)|ainda n[aã]o')::INT)             AS share_not_received
FROM t
GROUP BY is_late
ORDER BY is_late;

-- name: monthly_trend
SELECT DATE_TRUNC('month', purchase_ts)::DATE  AS month,
       COUNT(*)                                AS orders,
       AVG(is_late::INT)                       AS late_rate,
       AVG(review_score)                       AS avg_score,
       AVG(promised_days)                      AS avg_promised_days,
       AVG(actual_days)                        AS avg_actual_days
FROM fct_orders
GROUP BY 1
ORDER BY 1;
