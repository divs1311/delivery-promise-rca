-- 01_build_fact.sql — cleaning rules + one row per delivered order (fct_orders).
--
-- Cleaning rules (each is checked in 02_data_quality.sql and tests/):
--   R1  Analysis window: purchases 2017-01-01 .. 2018-08-31 (2016 and Sep–Oct 2018 have < 350 orders in total).
--   R2  Delivered orders only, with a customer delivery timestamp (lateness is undefined otherwise).
--   R3  One review per order: the most recently answered review (547 orders have 2–3 reviews).
--   R4  Days late = calendar days between the promised date and the delivery date
--       (promised dates carry no time of day). Delivered ON the promised date = on time.
--   R5  Leg timestamps (carrier hand-over) are used only when the sequence is valid:
--       purchase <= carrier hand-over <= customer delivery. Invalid sequences are kept for
--       outcome analysis but excluded from seller-vs-carrier attribution.
--   R6  Seller attribution only for single-seller orders (~98% of orders); multi-seller orders
--       have one order-level carrier timestamp, so the responsible seller is ambiguous.
--   R7  Geolocation: median lat/lng per zip prefix, inside Brazil's bounding box only. Zip prefixes are
--       left-padded to 5 digits everywhere (customer/seller files drop leading zeros: '9790' = '09790').

-- R3: latest review per order
CREATE OR REPLACE TABLE stg_reviews AS
SELECT order_id, review_score, review_comment_title, review_comment_message,
       review_creation_date, review_answer_timestamp
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY order_id
                                 ORDER BY review_answer_timestamp DESC, review_creation_date DESC, review_id) AS rn
    FROM raw_reviews
)
WHERE rn = 1;

-- R7: zip-prefix centroids
CREATE OR REPLACE TABLE stg_geo AS
SELECT LPAD(geolocation_zip_code_prefix, 5, '0') AS zip_prefix,
       MEDIAN(geolocation_lat) AS lat, MEDIAN(geolocation_lng) AS lng
FROM raw_geolocation
WHERE geolocation_lat BETWEEN -34 AND 5.5 AND geolocation_lng BETWEEN -74 AND -34
GROUP BY 1;

-- category per product, English where a translation exists
CREATE OR REPLACE TABLE stg_products AS
SELECT p.product_id,
       COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
       p.product_weight_g
FROM raw_products p
LEFT JOIN raw_category_translation t USING (product_category_name);

-- order-level item rollup
CREATE OR REPLACE TABLE stg_order_items AS
WITH ranked AS (
    SELECT i.*, sp.category, sp.product_weight_g,
           ROW_NUMBER() OVER (PARTITION BY i.order_id ORDER BY i.price DESC, i.order_item_id) AS price_rank
    FROM raw_order_items i
    LEFT JOIN stg_products sp USING (product_id)
)
SELECT order_id,
       COUNT(*)                                   AS n_items,
       COUNT(DISTINCT seller_id)                  AS n_sellers,
       CASE WHEN COUNT(DISTINCT seller_id) = 1 THEN MIN(seller_id) END AS seller_id,   -- R6
       MAX(shipping_limit_date)                   AS shipping_limit_ts,
       SUM(price)                                 AS items_value,
       SUM(freight_value)                         AS freight_value,
       SUM(product_weight_g)                      AS weight_g,
       MAX(CASE WHEN price_rank = 1 THEN category END) AS primary_category          -- category of the priciest item
FROM ranked
GROUP BY order_id;

CREATE OR REPLACE TABLE fct_orders AS
WITH base AS (
    SELECT o.order_id, o.customer_id,
           o.order_purchase_timestamp       AS purchase_ts,
           o.order_approved_at              AS approved_ts,
           o.order_delivered_carrier_date   AS carrier_ts,
           o.order_delivered_customer_date  AS delivered_ts,
           CAST(o.order_estimated_delivery_date AS DATE) AS promised_date
    FROM raw_orders o
    WHERE o.order_status = 'delivered'                                         -- R2
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'                 -- R1
      AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
)
SELECT b.*,
       c.customer_state, c.customer_city, LPAD(c.customer_zip_code_prefix, 5, '0') AS customer_zip,
       oi.n_items, oi.n_sellers, oi.seller_id, oi.shipping_limit_ts, oi.items_value, oi.freight_value,
       oi.weight_g, COALESCE(oi.primary_category, 'unknown') AS primary_category,
       s.seller_state, LPAD(s.seller_zip_code_prefix, 5, '0') AS seller_zip,
       r.review_score, r.review_comment_title, r.review_comment_message, r.review_creation_date,
       (r.review_score IS NOT NULL)                                                   AS has_review,
       CAST(r.review_creation_date AS DATE) < CAST(b.delivered_ts AS DATE)            AS review_before_delivery,
       -- time metrics (calendar days)
       DATE_DIFF('day', CAST(b.purchase_ts AS DATE), b.promised_date)                 AS promised_days,
       DATE_DIFF('day', CAST(b.purchase_ts AS DATE), CAST(b.delivered_ts AS DATE))    AS actual_days,
       DATE_DIFF('day', b.promised_date, CAST(b.delivered_ts AS DATE))                AS days_late,      -- R4
       DATE_DIFF('day', b.promised_date, CAST(b.delivered_ts AS DATE)) > 0            AS is_late,
       CASE
           WHEN DATE_DIFF('day', b.promised_date, CAST(b.delivered_ts AS DATE)) <= -15 THEN '01 15+ days early'
           WHEN DATE_DIFF('day', b.promised_date, CAST(b.delivered_ts AS DATE)) <= -8  THEN '02 8-14 days early'
           WHEN DATE_DIFF('day', b.promised_date, CAST(b.delivered_ts AS DATE)) <= -1  THEN '03 1-7 days early'
           WHEN DATE_DIFF('day', b.promised_date, CAST(b.delivered_ts AS DATE)) =  0   THEN '04 on the day'
           WHEN DATE_DIFF('day', b.promised_date, CAST(b.delivered_ts AS DATE)) <= 3   THEN '05 1-3 days late'
           WHEN DATE_DIFF('day', b.promised_date, CAST(b.delivered_ts AS DATE)) <= 7   THEN '06 4-7 days late'
           WHEN DATE_DIFF('day', b.promised_date, CAST(b.delivered_ts AS DATE)) <= 14  THEN '07 8-14 days late'
           ELSE '08 15+ days late'
       END AS lateness_bucket,
       -- R5: valid leg sequence
       (b.carrier_ts IS NOT NULL AND b.carrier_ts >= b.purchase_ts AND b.carrier_ts <= b.delivered_ts) AS legs_valid,
       -- seller hand-over vs the seller's shipping limit (single-seller orders, valid legs)
       CASE WHEN oi.n_sellers = 1 AND b.carrier_ts IS NOT NULL AND b.carrier_ts >= b.purchase_ts AND b.carrier_ts <= b.delivered_ts
            THEN b.carrier_ts > oi.shipping_limit_ts END                               AS seller_handover_late,
       CASE WHEN b.carrier_ts IS NOT NULL AND b.carrier_ts >= b.purchase_ts AND b.carrier_ts <= b.delivered_ts
            THEN DATE_DIFF('day', CAST(b.carrier_ts AS DATE), CAST(b.delivered_ts AS DATE)) END AS carrier_transit_days,
       -- haversine distance seller -> customer (km)
       2 * 6371 * ASIN(SQRT(
           POWER(SIN(RADIANS(gs.lat - gc.lat) / 2), 2) +
           COS(RADIANS(gc.lat)) * COS(RADIANS(gs.lat)) * POWER(SIN(RADIANS(gs.lng - gc.lng) / 2), 2)
       ))                                                                              AS distance_km,
       (s.seller_state IS NOT NULL AND s.seller_state <> c.customer_state)            AS is_interstate
FROM base b
JOIN raw_customers c          USING (customer_id)
JOIN stg_order_items oi       USING (order_id)
LEFT JOIN raw_sellers s       ON s.seller_id = oi.seller_id
LEFT JOIN stg_reviews r       USING (order_id)
LEFT JOIN stg_geo gc          ON gc.zip_prefix = LPAD(c.customer_zip_code_prefix, 5, '0')
LEFT JOIN stg_geo gs          ON gs.zip_prefix = LPAD(s.seller_zip_code_prefix, 5, '0');

-- Analysis base for review outcomes: delivered orders that have a review.
CREATE OR REPLACE VIEW fct_reviewed AS SELECT * FROM fct_orders WHERE has_review;

-- Root-cause label for each late order (used by 06_root_cause.sql and 12_opportunity_sizing.sql).
-- Scope: late, single-seller orders with a valid timestamp sequence (R5, R6).
-- Counterfactual: had the seller handed over exactly at the shipping limit, the parcel would have
-- arrived (carrier pickup − shipping limit) earlier. If that arrival is on/before the promised
-- date, the seller alone caused the miss.
CREATE OR REPLACE VIEW v_late_root_cause AS
SELECT *,
       CASE
           WHEN seller_handover_late
                AND CAST(delivered_ts - (carrier_ts - shipping_limit_ts) AS DATE) <= promised_date
                THEN '1 Seller hand-over only'
           WHEN seller_handover_late
                THEN '2 Seller hand-over + carrier'
           ELSE '3 Carrier leg only'
       END AS root_cause
FROM fct_orders
WHERE is_late AND n_sellers = 1 AND legs_valid;
