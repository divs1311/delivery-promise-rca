# When the Delivery Promise Breaks
### A SQL root-cause analysis of late deliveries and review scores in ${n_orders} real e-commerce orders

**Stack:** SQL (DuckDB) · Python (pandas for independent verification, matplotlib) · **Data:** Olist Brazilian e-commerce, Jan 2017 – Aug 2018

> **Why I built this.** In a marketplace, the delivery date shown at checkout is a promise. Myntra's
> Supply Chain Outbound team owns the parts of the journey that keep it: inventory, fulfilment,
> delivery, returns. I wanted to measure what a broken promise costs, find *where* in the journey it
> breaks, and decide what a PM should fix first. All analysis is in SQL, on real order data.

---

## TL;DR

1. **A late delivery wrecks the review.** Late orders average **${late_avg}** against **${ontime_avg}** for on-time orders, and are **${rr12}× more likely** to get a 1–2★ review (${late_pct12} vs ${ontime_pct12}). They are ${share_late_reviewed} of reviewed orders but **${share12_from_late} of all 1–2★ reviews**. Lateness drags the platform's average review score down by **${rating_drag} stars**.
2. **It isn't a mix effect.** Comparing late and on-time orders inside the same state × product category leaves the gap almost unchanged (**${adj_gap_sc}** vs ${gap} stars).
3. **Most delays happen in transit, not at the seller.** Of ${attr_total} late orders, **${attr_carrier_share} were late purely because of the carrier leg**. Sellers who miss their hand-over deadline are involved in ${attr_seller_any_share}.
4. **Seller hand-over failures are concentrated.** The worst **${top5_n} sellers (top 5%)** account for **${top5_share}** of late orders where the seller also handed over late, against ${top5_vol} of order volume. That's a short list to manage, not a platform-wide problem.
5. **Promises are long because delivery is unpredictable, not because they're careless.** Olist's promise sits at roughly the 92nd percentile of actual delivery time. In a 2018 backtest, no history-based promise rule beat it on both speed and reliability. **Cutting transit variance is what would allow faster promises.**

---

## Findings

### 1 · Lateness wrecks reviews

![Share of 1–2 star reviews by arrival vs promise](outputs/charts/01_lateness_vs_reviews.png)

- Arriving on the promised day already gives ${b_onday_pct12} 1–2★ reviews. **One to three days late jumps that to ${b_late13_pct12}**, 4–7 days late to ${b_late47_pct12}, and 8–14 days late to ${b_late814_pct12}.
- Early delivery helps, with diminishing returns: ${b_onday_avg} on the day, ${b_early17_avg} at 1–7 days early, ${b_early15_avg} at 15+ days early.
- **Score gap:** ${gap} stars (95% CI ${gap_lo}–${gap_hi}). **Rating drag:** share of late orders × gap = **${rating_drag} stars** off the average review score. That's how much the average would rise if late orders were rated like on-time ones.
- **Robustness:** stratifying by customer state × product category (${adj_cells_sc} cells, ${adj_cov_sc} of late orders covered) gives an adjusted gap of **${adj_gap_sc}**. Stratifying by distance × order value × single/multi-item gives **${adj_gap_dv}**. Where the customer is and what they bought doesn't explain the gap.
- **What customers say:** among 1–2★ reviews with text, **${tx_deliv_late}** of those on late orders mention delivery (vs ${tx_deliv_ok} on on-time orders), and **${tx_notrec_late}** say some version of "not received" (vs ${tx_notrec_ok}).
- **Customers review before the parcel arrives:** ${late_review_before_share} of late-order reviews are written *before* delivery, averaging **${late_review_before_avg}** vs ${late_review_after_avg} for those written after. That suggests much of the anger is about uncertainty ("where is my order?"), which proactive communication can address even when the delay itself can't be prevented. That's a hypothesis to test, not a finding.

### 2 · Where the delay happens: seller hand-over vs carrier transit

![Root-cause attribution of late orders](outputs/charts/02_root_cause.png)

Every seller has a **shipping limit**, a deadline to hand the parcel to the carrier. For each late order I asked: *if the seller had handed over exactly on the deadline, would it still have been late?*

| Root cause | Share of late orders | Avg days late |
|---|---|---|
| Carrier leg only (seller on time) | **${attr_carrier_share}** (${attr_carrier_n}) | ${attr_carrier_days} |
| Seller hand-over + carrier | ${attr_both_share} | ${attr_both_days} |
| Seller hand-over only (on time with a timely hand-over) | ${attr_seller_only_share} (${attr_seller_only_n}) | ${attr_seller_only_days} |

- Late orders spend **${transit_late} days** in carrier transit on average, against **${transit_ok}** for on-time orders. Time to hand-over roughly doubles (${to_carrier_late} vs ${to_carrier_ok} days), but transit is where most of the extra time goes.

![Seller hand-over effect](outputs/charts/03_handover_effect.png)

- When a seller misses the hand-over deadline (${ho_share} of orders), the order is late **${ho_late_rate_late}** of the time, vs **${ho_late_rate_ok}** when they hand over on time: **${ho_ratio}× likelier**.

### 3 · Seller failures are concentrated in a few sellers

- Only **${sellers_any_share}** of ${sellers_total} sellers ever caused a late order with a late hand-over.
- The **top 1% (${top1_n} sellers)** account for **${top1_share}** of those orders while handling ${top1_vol} of volume. The **top 5% (${top5_n})** account for **${top5_share}** with ${top5_vol} of volume. They're big sellers, but over-represented in late hand-overs relative to their size.
- Sellers with ≥30 orders who miss the deadline on 20%+ of orders: **${card20_sellers} sellers, ${card20_vol} of orders**, a late rate of **${card20_late}** (vs ${card5_late} for sellers under 5%) and **${card20_score}** average score (vs ${card5_score}).

### 4 · Geography: distance, region and lanes

![Late rate by customer state](outputs/charts/06_state_late_rate.png)

- The late rate climbs with distance: **${d100_late}** under 100 km to **${d2000_late}** over 2,000 km.
- São Paulo (${sp_orders_share} of orders) runs at ${sp_rate}. **${worst_state}** is the worst state at ${worst_state_rate}.
- **${big_lane}** is the problem lane: ${big_lane_late_n} late orders (${big_lane_share_of_late} of all late orders), second only to ${top_lane_by_count}, which has ${lane_vol_ratio}× the volume but a ${top_lane_by_count_rate} late rate. At the platform-average late rate it would have had about ${big_lane_expected}, so it carries **${big_lane_excess} excess late orders, the most of any lane**. It's only ~${big_lane_km} km (median), yet runs at ${big_lane_late} late against ${d100_500_late} for all 100–500 km orders. Distance doesn't explain it, so this one lane deserves a dedicated carrier review.
- Across the 15 biggest categories, late rates only range from ${cat_late_min} to ${cat_late_max}, and the score penalty from ${cat_gap_min} to ${cat_gap_max} stars. **Lateness hurts every category about equally, so the fix belongs in logistics, not in category management.**

### 5 · The promise: why it's long, and why you can't just shorten it

![Delivery time spread vs promise](outputs/charts/04_delivery_time_spread.png)

- Olist promises **${avg_promised} days** on average and delivers in **${avg_actual}**. ${padding_8plus} of orders arrive 8+ days early.
- But in every distance band the median promise sits within ${promise_vs_p92_maxdiff} days of the **92nd percentile** of actual delivery time. The gap between a typical delivery and one you can keep 92% of the time is **${spread_min}–${spread_max} days**.
- **Backtest** (rules learned on 2017 orders, tested on ${bt_n} orders from 2018):

| Promise policy | On-time rate | Avg promise |
|---|---|---|
| Olist's actual promise | ${bt_olist_ot} | ${bt_olist_days} days |
| Lane P90 learned from 2017 | ${bt_p90_ot} | ${bt_p90_days} days |
| Lane P95 learned from 2017 | ${bt_p95_ot} | ${bt_p95_days} days |
| Adaptive weekly lane P90 (orders 45–135 days back) | ${bt_ad90_ot} | ${bt_ad90_days} days (Olist on same orders: ${bt_ad_olist_ot}, ${bt_ad_olist_days}) |

- **No history-based rule beats Olist's promise on both speed and reliability.** Shorter promises break more often, and reliable ones are just as long. **The lever is variance:** shrinking the carrier tail is what would let the promise come down.

### 6 · Peaks break the promise

![Monthly late rate and review score](outputs/charts/05_monthly_trend.png)

- Monthly late rate and average score move almost in lockstep (correlation **${trend_corr}**).
- The late rate hit **${nov17_late}** in November 2017 (the month of Black Friday) and **${mar18_late}** in March 2018, when the average score fell to **${mar18_score}** (vs ${aug17_score} in August 2017). Promises didn't widen to absorb these peaks.

---

## What I'd do as a PM on an outbound / fulfilment team

| # | Recommendation | Why (evidence) | Success metric | Guardrail |
|---|---|---|---|---|
| 1 | **Lane-level carrier SLA monitoring and re-allocation**, starting with ${big_lane} | ${attr_carrier_share} of late orders are transit-only; ${big_lane} alone carries ${big_lane_excess} excess late orders (${big_lane_share_of_late} of all late orders) | Late rate and P92 transit days on the lane | Cost per shipment |
| 2 | **Proactive delay communication**: when a parcel is predicted to miss its date, notify the customer with a new ETA before they ask | ${late_review_before_share} of late reviews are written before arrival; ${tx_notrec_late} of 1–2★ late-order texts say "not received" | 1–2★ share on late orders; "where is my order" tickets | Notification opt-outs |
| 3 | **Seller hand-over scorecard** for the worst ${top5_n} sellers: alerts before the shipping limit, then listing demotion for repeat misses | Top 5% of sellers cause ${top5_share} of seller-involved late orders; a late hand-over makes lateness ${ho_ratio}× likelier | Seller hand-over-late rate | Seller churn, catalogue depth |
| 4 | **Peak-season playbook**: widen promises and pre-book carrier capacity before sale events | Late rate reached ${nov17_late} (Nov 2017) and ${mar18_late} (Mar 2018) | Peak-month late rate | Checkout conversion during sales |
| 5 | **Reduce variance before shortening promises**, then A/B test tighter promises on low-variance lanes (e.g. under 100 km) | Promises sit near P92; naive tightening loses on-time rate in the backtest | Conversion with a shorter promise | On-time rate ≥ current |

### Sizing (if a late order became on time, it gets on-time review behaviour)

| Scenario | Orders fixed | Avg score uplift (naive / adjusted*) | 1–2★ reviews avoided |
|---|---|---|---|
| A · Fix seller hand-over (seller-only late orders) | ${szA_orders} | +${szA_uplift} / +${szA_uplift_adj} | ${szA_12} (${szA_12_share} of all 1–2★) |
| B · Every late order on time (upper bound) | ${late_n} | +${szB_uplift} / +${szB_uplift_adj} | ${szB_12} (${szB_12_share} of all 1–2★) |

\*Adjusted = scaled by the state × category stratified gap. **The seller fix is targeted but small. The prize is in transit (scenario B), which is why recommendations 1 and 2 come first.**

---

## Method

**Data:** ${dq_raw} orders from Olist's public dataset (9 tables: orders, items, reviews, customers, sellers, products, payments, geolocation, category names). The analysis base is **${n_orders} delivered orders** (${review_coverage} reviewed).

**Cleaning rules** (each quantified in `outputs/tables/data_quality.csv`):

| Rule | Decision | Rows affected |
|---|---|---|
| R1 | Window Jan 2017 – Aug 2018 (edges are near-empty) | ${dq_window} orders dropped |
| R2 | Delivered orders with a delivery timestamp | ${dq_nodate} dropped |
| R3 | One review per order: the latest answered | ${dq_multirev} orders had 2–3 reviews |
| R4 | Days late = calendar days from promised date to delivery; on the day = on time | — |
| R5 | Leg analysis only where purchase ≤ carrier pickup ≤ delivery | ${dq_invalid} excluded from attribution |
| R6 | Seller attribution only for single-seller orders | ${dq_multiseller} multi-seller orders excluded |
| R7 | Zip prefixes padded to 5 digits (source files drop leading zeros); median coordinates per prefix | ${dq_nodist} orders without a distance |

**Verification:** `src/verify.py` rebuilds the analysis from the raw CSVs in pandas, sharing no code with the SQL, and re-derives 24 headline numbers. **All 24 match the SQL output exactly.** `README.md` itself is rendered from the result tables (`src/build_report.py`), so no number here was typed by hand.

**Limitations**
- Observational data: the stratified comparisons rule out the obvious confounders, but this isn't an experiment.
- Brazil, 2017–18. The method transfers to Indian e-commerce; the specific numbers don't.
- Reviews come from customers who chose to leave one (${review_coverage} coverage here, so the bias is small). ${dq_revbefore} reviews were written before delivery, and they're kept because they capture the late experience.
- Root-cause attribution relies on the carrier pickup timestamp and the seller's shipping limit as recorded by Olist.
- No checkout conversion data, so the cost of long promises is argued, not measured.

---

## Run it

```bash
pip install -r requirements.txt
python src/get_data.py       # downloads the 9 raw CSVs (~125 MB) from Olist's public GitHub mirror
python src/run_analysis.py   # builds DuckDB, runs every query in sql/ → outputs/tables/*.csv
python src/verify.py         # independent pandas re-computation (24 checks)
python src/make_charts.py    # outputs/charts/*.png
python src/build_report.py   # renders this README from the results
pytest -q                    # data-quality and verification tests
```

```
sql/
  00_load.sql               raw tables
  01_build_fact.sql         cleaning rules R1–R7 → fct_orders (1 row per delivered order), root-cause view
  02_data_quality.sql       every rule quantified
  03_delivery_baseline.sql  KPIs, dose-response by lateness bucket
  04_review_impact.sql      rating drag, 95% CI, review timing
  05_confounder_control.sql stratified (within-cell) gaps
  06_root_cause.sql         seller vs carrier attribution, hand-over effect, leg durations
  07_sellers.sql            concentration (Pareto), seller scorecard
  08_region_category.sql    states, distance bands, lanes, categories
  09_promise_backtest.sql   padding, static and adaptive promise backtests, delivery-time spread
  10_review_text_trend.sql  Portuguese review-text topics, monthly trend
  11_opportunity_sizing.sql scenario sizing
```

**Data source:** Olist, [Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), mirrored by Olist at [github.com/olist/work-at-olist-data](https://github.com/olist/work-at-olist-data) (MIT licence). Real, anonymised orders.
