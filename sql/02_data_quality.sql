-- 02_data_quality.sql — every cleaning decision, quantified. Output: outputs/tables/data_quality.csv
-- name: data_quality
WITH raw AS (SELECT * FROM raw_orders),
checks AS (
    SELECT 'raw orders'                                   AS check_name, COUNT(*)::BIGINT AS value FROM raw
    UNION ALL SELECT 'raw orders: status delivered', COUNT(*) FROM raw WHERE order_status = 'delivered'
    UNION ALL SELECT 'raw orders: delivered but no delivery timestamp (dropped, R2)',
                     COUNT(*) FROM raw WHERE order_status = 'delivered' AND order_delivered_customer_date IS NULL
    UNION ALL SELECT 'raw orders: outside 2017-01..2018-08 window (dropped, R1)',
                     COUNT(*) FROM raw WHERE order_purchase_timestamp < TIMESTAMP '2017-01-01'
                                          OR order_purchase_timestamp >= TIMESTAMP '2018-09-01'
    UNION ALL SELECT 'raw reviews', COUNT(*) FROM raw_reviews
    UNION ALL SELECT 'orders with 2+ reviews (latest kept, R3)',
                     COUNT(*) FROM (SELECT order_id FROM raw_reviews GROUP BY 1 HAVING COUNT(*) > 1)
    UNION ALL SELECT 'fct_orders rows (analysis base)', COUNT(*) FROM fct_orders
    UNION ALL SELECT 'fct_orders: duplicate order_id (must be 0)', COUNT(*) - COUNT(DISTINCT order_id) FROM fct_orders
    UNION ALL SELECT 'fct_orders: with a review', COUNT(*) FROM fct_orders WHERE has_review
    UNION ALL SELECT 'fct_orders: review written before delivery date', COUNT(*) FROM fct_orders WHERE review_before_delivery
    UNION ALL SELECT 'fct_orders: invalid leg sequence (excluded from attribution, R5)', COUNT(*) FROM fct_orders WHERE NOT legs_valid
    UNION ALL SELECT 'fct_orders: multi-seller (no seller attribution, R6)', COUNT(*) FROM fct_orders WHERE n_sellers > 1
    UNION ALL SELECT 'fct_orders: missing distance (zip not geocoded)', COUNT(*) FROM fct_orders WHERE distance_km IS NULL
    UNION ALL SELECT 'fct_orders: promised_days <= 0 (must be 0)', COUNT(*) FROM fct_orders WHERE promised_days <= 0
)
SELECT * FROM checks;
