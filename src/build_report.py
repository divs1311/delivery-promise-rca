"""Render README.md from docs/README.template.md using numbers read from outputs/tables/*.csv.

No figure in the README is typed by hand: every number is a ${placeholder} filled here, so the
write-up can't drift from the analysis. Fails if any placeholder is left unfilled.

    python src/build_report.py
"""
from __future__ import annotations

import string
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "outputs" / "tables"


def t(name: str) -> pd.DataFrame:
    return pd.read_csv(T / f"{name}.csv")


pct = lambda x, d=0: f"{x * 100:.{d}f}%"
num = lambda x: f"{int(round(x)):,}"
f1 = lambda x: f"{x:.1f}"
f2 = lambda x: f"{x:.2f}"
star = lambda x: f"{x:.2f}★"


def metrics() -> dict[str, str]:
    m: dict[str, str] = {}
    k = t("kpi_summary").iloc[0]
    m |= {"n_orders": num(k.delivered_orders), "late_rate": pct(k.late_rate, 1),
          "avg_days_late_when_late": f1(k.avg_days_late_when_late), "median_days_early": num(-k.median_days_vs_promise),
          "avg_promised": f1(k.avg_promised_days), "avg_actual": f1(k.avg_actual_days),
          "review_coverage": pct(k.review_coverage, 1), "avg_score": star(k.avg_review_score)}

    rd = t("rating_drag").iloc[0]
    m |= {"n_reviewed": num(rd.late_n + rd.ontime_n), "late_n": num(rd.late_n), "late_avg": star(rd.late_avg_score),
          "ontime_avg": star(rd.ontime_avg_score), "gap": f2(rd.score_gap), "gap_lo": f2(rd.score_gap_ci_low),
          "gap_hi": f2(rd.score_gap_ci_high), "late_pct12": pct(rd.late_pct_1_2_star), "ontime_pct12": pct(rd.ontime_pct_1_2_star),
          "rr12": f1(rd.relative_risk_1_2_star), "share12_from_late": pct(rd.share_of_all_1_2_star_from_late),
          "share_late_reviewed": pct(rd.share_late, 1), "rating_drag": f2(rd.rating_drag)}

    b = t("lateness_buckets").set_index("lateness_bucket")
    m |= {"b_early15_pct12": pct(b.loc["01 15+ days early", "pct_1_2_star"]),
          "b_onday_pct12": pct(b.loc["04 on the day", "pct_1_2_star"]),
          "b_late13_pct12": pct(b.loc["05 1-3 days late", "pct_1_2_star"]),
          "b_late47_pct12": pct(b.loc["06 4-7 days late", "pct_1_2_star"]),
          "b_late814_pct12": pct(b.loc["07 8-14 days late", "pct_1_2_star"]),
          "b_early15_avg": star(b.loc["01 15+ days early", "avg_score"]),
          "b_early17_avg": star(b.loc["03 1-7 days early", "avg_score"]),
          "b_onday_avg": star(b.loc["04 on the day", "avg_score"])}

    rt = t("review_timing_late_orders").set_index("review_before_delivery")
    m |= {"late_review_before_share": pct(rt.loc[True, "share"]), "late_review_before_avg": star(rt.loc[True, "avg_score"]),
          "late_review_after_avg": star(rt.loc[False, "avg_score"])}

    s1 = t("stratified_gap_state_category").iloc[0]
    s2 = t("stratified_gap_distance_value_items").iloc[0]
    m |= {"adj_gap_sc": f2(s1.adjusted_gap), "adj_cells_sc": num(s1.cells_used), "adj_cov_sc": pct(s1.late_orders_covered),
          "adj_gap_dv": f2(s2.adjusted_gap), "adj_cells_dv": num(s2.cells_used)}

    la = t("late_attribution").set_index("root_cause")
    late_attr_total = la.late_orders.sum()
    m |= {"attr_total": num(late_attr_total),
          "attr_carrier_share": pct(la.loc["3 Carrier leg only", "share_of_late"]),
          "attr_carrier_n": num(la.loc["3 Carrier leg only", "late_orders"]),
          "attr_seller_only_share": pct(la.loc["1 Seller hand-over only", "share_of_late"]),
          "attr_seller_only_n": num(la.loc["1 Seller hand-over only", "late_orders"]),
          "attr_both_share": pct(la.loc["2 Seller hand-over + carrier", "share_of_late"]),
          "attr_seller_any_share": pct(la.loc[["1 Seller hand-over only", "2 Seller hand-over + carrier"], "share_of_late"].sum()),
          "attr_seller_only_days": f1(la.loc["1 Seller hand-over only", "avg_days_late"]),
          "attr_both_days": f1(la.loc["2 Seller hand-over + carrier", "avg_days_late"]),
          "attr_carrier_days": f1(la.loc["3 Carrier leg only", "avg_days_late"])}

    he = t("handover_effect").set_index("seller_handover_late")
    m |= {"ho_late_rate_late": pct(he.loc[True, "late_rate"], 1), "ho_late_rate_ok": pct(he.loc[False, "late_rate"], 1),
          "ho_ratio": f1(he.loc[True, "late_rate"] / he.loc[False, "late_rate"]), "ho_share": pct(he.loc[True, "share_of_orders"])}

    ld = t("leg_durations").set_index("is_late")
    m |= {"transit_late": f1(ld.loc[True, "avg_carrier_transit_days"]), "transit_ok": f1(ld.loc[False, "avg_carrier_transit_days"]),
          "to_carrier_late": f1(ld.loc[True, "avg_days_to_carrier"]), "to_carrier_ok": f1(ld.loc[False, "avg_days_to_carrier"])}

    reach = t("seller_late_handover_reach").iloc[0]
    sc = t("seller_concentration").set_index("top_pct_of_sellers")
    m |= {"sellers_any_share": pct(reach.share_with_any), "sellers_total": num(reach.sellers),
          "top1_share": pct(sc.loc[0.01, "share_of_seller_late_orders"]), "top1_n": num(sc.loc[0.01, "sellers"]),
          "top1_vol": pct(sc.loc[0.01, "share_of_all_orders"]),
          "top5_share": pct(sc.loc[0.05, "share_of_seller_late_orders"]), "top5_n": num(sc.loc[0.05, "sellers"]),
          "top5_vol": pct(sc.loc[0.05, "share_of_all_orders"])}
    card = t("seller_scorecard").set_index("seller_band")
    m |= {"card20_sellers": num(card.loc["4 20%+", "sellers"]), "card20_vol": pct(card.loc["4 20%+", "share_of_orders"]),
          "card20_late": pct(card.loc["4 20%+", "late_rate"], 1), "card5_late": pct(card.loc["1 <5% late hand-overs", "late_rate"], 1),
          "card20_score": star(card.loc["4 20%+", "avg_score"]), "card5_score": star(card.loc["1 <5% late hand-overs", "avg_score"])}

    st = t("state_performance").set_index("customer_state")
    worst = st.late_rate.idxmax()
    m |= {"worst_state": worst, "worst_state_rate": pct(st.loc[worst, "late_rate"]), "sp_rate": pct(st.loc["SP", "late_rate"], 1),
          "sp_orders_share": pct(st.loc["SP", "orders"] / k.delivered_orders), "rj_rate": pct(st.loc["RJ", "late_rate"], 1),
          "rj_orders": num(st.loc["RJ", "orders"])}
    db = t("distance_bands").set_index("distance_band")
    m |= {"d100_late": pct(db.loc["1 <100 km", "late_rate"], 1), "d2000_late": pct(db.loc["5 2,000+ km", "late_rate"], 1),
          "d100_500_late": pct(db.loc["2 100-500 km", "late_rate"], 1)}
    le = t("lane_excess_late")
    big = le.iloc[0]                                   # largest excess late orders
    top_by_count = le.sort_values("rank_by_late_orders").iloc[0]
    m |= {"big_lane": big.lane, "big_lane_orders": num(big.orders), "big_lane_late": pct(big.late_rate, 1),
          "big_lane_late_n": num(big.late_orders), "big_lane_share_of_late": pct(big.late_orders / (k.late_rate * k.delivered_orders)),
          "big_lane_km": num(big.median_distance_km), "big_lane_excess": num(big.excess_late_orders),
          "big_lane_expected": num(big.expected_late_at_platform_rate),
          "big_lane_rank": num(big.rank_by_late_orders), "top_lane_by_count": top_by_count.lane,
          "top_lane_by_count_orders": num(top_by_count.orders), "top_lane_by_count_rate": pct(top_by_count.late_rate, 1),
          "lane_vol_ratio": f1(top_by_count.orders / big.orders)}
    assert int(big.rank_by_late_orders) == 2 and top_by_count.lane != big.lane, "README wording assumes rank 2 by count"
    cat = t("category_performance")
    m |= {"cat_gap_min": f2(cat.score_gap.min()), "cat_gap_max": f2(cat.score_gap.max()),
          "cat_late_min": pct(cat.late_rate.min(), 1), "cat_late_max": pct(cat.late_rate.max(), 1)}

    pp = t("promise_padding").set_index("buffer_band")
    m |= {"padding_8plus": pct(pp.loc[["4 8-14 days spare", "5 15+ days spare"], "share"].sum())}
    pb = t("promise_backtest").set_index("policy")
    pa = t("promise_backtest_adaptive").set_index("policy")
    m |= {"bt_n": num(pb.loc["0 Olist actual promise", "test_orders"]),
          "bt_olist_ot": pct(pb.loc["0 Olist actual promise", "on_time_rate"], 1),
          "bt_olist_days": f1(pb.loc["0 Olist actual promise", "avg_promised_days"]),
          "bt_p90_ot": pct(pb.loc["3 Lane P90 (history)", "on_time_rate"], 1),
          "bt_p90_days": f1(pb.loc["3 Lane P90 (history)", "avg_promised_days"]),
          "bt_p95_ot": pct(pb.loc["4 Lane P95 (history)", "on_time_rate"], 1),
          "bt_p95_days": f1(pb.loc["4 Lane P95 (history)", "avg_promised_days"]),
          "bt_ad90_ot": pct(pa.loc["1 Adaptive lane P90", "on_time_rate"], 1),
          "bt_ad90_days": f1(pa.loc["1 Adaptive lane P90", "avg_promised_days"]),
          "bt_ad_olist_ot": pct(pa.loc["0 Olist actual promise", "on_time_rate"], 1),
          "bt_ad_olist_days": f1(pa.loc["0 Olist actual promise", "avg_promised_days"])}
    sp = t("delivery_time_spread")
    m |= {"spread_min": num(sp.spread_days.min()), "spread_max": num(sp.spread_days.max()),
          "promise_vs_p92_maxdiff": num((sp.median_promised_days - sp.p92_actual_days).abs().max())}

    tx = t("low_score_comment_topics").set_index("is_late")
    m |= {"tx_deliv_late": pct(tx.loc[True, "share_mention_delivery"]), "tx_deliv_ok": pct(tx.loc[False, "share_mention_delivery"]),
          "tx_notrec_late": pct(tx.loc[True, "share_not_received"]), "tx_notrec_ok": pct(tx.loc[False, "share_not_received"])}

    mt = t("monthly_trend")
    mt["month"] = pd.to_datetime(mt.month)
    by = mt.set_index("month")
    m |= {"trend_corr": f2(np.corrcoef(mt.late_rate, mt.avg_score)[0, 1]),
          "nov17_late": pct(by.loc["2017-11-01", "late_rate"], 1), "mar18_late": pct(by.loc["2018-03-01", "late_rate"], 1),
          "mar18_score": star(by.loc["2018-03-01", "avg_score"]), "aug17_score": star(by.loc["2017-08-01", "avg_score"])}

    op = t("opportunity_sizing").set_index("scenario")
    a = op.iloc[0]
    bb = op.iloc[1]
    m |= {"szA_orders": num(a.orders_fixed), "szA_uplift": f"{a.avg_score_uplift_naive:.3f}",
          "szA_uplift_adj": f"{a.avg_score_uplift_adjusted:.3f}", "szA_12": num(a.one_two_star_reviews_avoided_naive),
          "szA_12_share": pct(a.share_of_all_1_2_star_avoided_naive, 1),
          "szB_uplift": f2(bb.avg_score_uplift_naive), "szB_uplift_adj": f2(bb.avg_score_uplift_adjusted),
          "szB_12": num(bb.one_two_star_reviews_avoided_naive), "szB_12_share": pct(bb.share_of_all_1_2_star_avoided_naive)}

    dq = t("data_quality").set_index("check_name").value
    m |= {"dq_raw": num(dq["raw orders"]), "dq_window": num(dq["raw orders: outside 2017-01..2018-08 window (dropped, R1)"]),
          "dq_nodate": num(dq["raw orders: delivered but no delivery timestamp (dropped, R2)"]),
          "dq_multirev": num(dq["orders with 2+ reviews (latest kept, R3)"]),
          "dq_invalid": num(dq["fct_orders: invalid leg sequence (excluded from attribution, R5)"]),
          "dq_multiseller": num(dq["fct_orders: multi-seller (no seller attribution, R6)"]),
          "dq_nodist": num(dq["fct_orders: missing distance (zip not geocoded)"]),
          "dq_revbefore": num(dq["fct_orders: review written before delivery date"])}
    return m


def main() -> int:
    tpl = string.Template((ROOT / "docs" / "README.template.md").read_text())
    vals = metrics()
    try:
        out = tpl.substitute(vals)
    except KeyError as e:
        print(f"✗ placeholder with no value: {e}")
        return 1
    (ROOT / "README.md").write_text(out)
    print(f"✓ README.md rendered with {len(vals)} computed values")
    return 0


if __name__ == "__main__":
    sys.exit(main())
