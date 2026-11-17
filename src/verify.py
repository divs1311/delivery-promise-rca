"""Independent re-computation of every headline number, in pandas, straight from the raw CSVs.

Shares no code or tables with the SQL pipeline — it re-implements the cleaning rules from
scratch — then compares its results with outputs/tables/*.csv. Any mismatch fails loudly.

    python src/verify.py
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
TABLES = ROOT / "outputs" / "tables"


def load() -> pd.DataFrame:
    ts = ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
          "order_delivered_customer_date", "order_estimated_delivery_date"]
    o = pd.read_csv(RAW / "olist_orders_dataset.csv", parse_dates=ts)
    o = o[(o.order_status == "delivered") & o.order_delivered_customer_date.notna()
          & (o.order_purchase_timestamp >= "2017-01-01") & (o.order_purchase_timestamp < "2018-09-01")]

    c = pd.read_csv(RAW / "olist_customers_dataset.csv", dtype={"customer_zip_code_prefix": str})
    s = pd.read_csv(RAW / "olist_sellers_dataset.csv", dtype={"seller_zip_code_prefix": str})
    p = pd.read_csv(RAW / "olist_products_dataset.csv")
    tr = pd.read_csv(RAW / "product_category_name_translation.csv")
    p = p.merge(tr, on="product_category_name", how="left")
    p["category"] = p.product_category_name_english.fillna(p.product_category_name).fillna("unknown")

    it = pd.read_csv(RAW / "olist_order_items_dataset.csv", parse_dates=["shipping_limit_date"])
    it = it.merge(p[["product_id", "category"]], on="product_id", how="left")
    it = it.sort_values(["order_id", "price", "order_item_id"], ascending=[True, False, True])
    agg = it.groupby("order_id").agg(n_items=("order_item_id", "size"), n_sellers=("seller_id", "nunique"),
                                     any_seller=("seller_id", "first"), shipping_limit=("shipping_limit_date", "max"),
                                     items_value=("price", "sum"), primary_category=("category", "first"))
    agg["seller_id"] = np.where(agg.n_sellers == 1, agg.any_seller, None)

    r = pd.read_csv(RAW / "olist_order_reviews_dataset.csv",
                    parse_dates=["review_creation_date", "review_answer_timestamp"])
    r = (r.sort_values(["order_id", "review_answer_timestamp", "review_creation_date", "review_id"],
                       ascending=[True, False, False, True])
          .drop_duplicates("order_id"))

    df = (o.merge(c, on="customer_id").merge(agg.reset_index(), on="order_id")
           .merge(s, on="seller_id", how="left").merge(r, on="order_id", how="left"))
    df["primary_category"] = df.primary_category.fillna("unknown")
    d_deliv = df.order_delivered_customer_date.dt.normalize()
    d_prom = df.order_estimated_delivery_date.dt.normalize()
    d_purch = df.order_purchase_timestamp.dt.normalize()
    df["days_late"] = (d_deliv - d_prom).dt.days
    df["is_late"] = df.days_late > 0
    df["promised_days"] = (d_prom - d_purch).dt.days
    df["actual_days"] = (d_deliv - d_purch).dt.days
    car = df.order_delivered_carrier_date
    df["legs_valid"] = car.notna() & (car >= df.order_purchase_timestamp) & (car <= df.order_delivered_customer_date)
    df["handover_late"] = np.where((df.n_sellers == 1) & df.legs_valid, car > df.shipping_limit, np.nan)
    return df


def check(name: str, ours, theirs, tol: float = 1e-9) -> bool:
    ok = (ours == theirs) if isinstance(ours, (int, np.integer)) and isinstance(theirs, (int, np.integer)) \
        else math.isclose(float(ours), float(theirs), rel_tol=tol, abs_tol=tol)
    print(f"{'✓' if ok else '✗'} {name:<58} pandas={ours!s:<22} sql={theirs!s}")
    return ok


def t(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES / f"{name}.csv")


def main() -> int:
    df = load()
    rv = df[df.review_score.notna()]
    results = []

    # --- base + headline impact ---------------------------------------------------------------
    k = t("kpi_summary").iloc[0]
    results += [check("delivered orders in analysis base", len(df), int(k.delivered_orders)),
                check("late rate", df.is_late.mean(), k.late_rate),
                check("avg promised days", df.promised_days.mean(), k.avg_promised_days),
                check("avg actual days", df.actual_days.mean(), k.avg_actual_days)]
    rd = t("rating_drag").iloc[0]
    late, ontime = rv[rv.is_late], rv[~rv.is_late]
    share_late = len(late) / len(rv)
    gap = ontime.review_score.mean() - late.review_score.mean()
    results += [check("late avg score", late.review_score.mean(), rd.late_avg_score),
                check("on-time avg score", ontime.review_score.mean(), rd.ontime_avg_score),
                check("late % 1-2 star", (late.review_score <= 2).mean(), rd.late_pct_1_2_star),
                check("on-time % 1-2 star", (ontime.review_score <= 2).mean(), rd.ontime_pct_1_2_star),
                check("rating drag", share_late * gap, rd.rating_drag),
                check("share of all 1-2 star reviews from late orders",
                      (late.review_score <= 2).sum() / (rv.review_score <= 2).sum(), rd.share_of_all_1_2_star_from_late)]
    b = t("lateness_buckets").set_index("lateness_bucket")
    results.append(check("avg score, 8-14 days late", rv[rv.days_late.between(8, 14)].review_score.mean(),
                         b.loc["07 8-14 days late", "avg_score"]))

    # --- confounder control ---------------------------------------------------------------------
    cells = rv.groupby(["customer_state", "primary_category"]).apply(
        lambda g: pd.Series({"late_n": g.is_late.sum(), "ontime_n": (~g.is_late).sum(),
                             "late_avg": g[g.is_late].review_score.mean(),
                             "ontime_avg": g[~g.is_late].review_score.mean()}), include_groups=False)
    el = cells[(cells.late_n >= 5) & (cells.ontime_n >= 5)]
    adj = (el.late_n * (el.ontime_avg - el.late_avg)).sum() / el.late_n.sum()
    results.append(check("adjusted gap (state × category)", adj, t("stratified_gap_state_category").iloc[0].adjusted_gap))

    # --- root cause -------------------------------------------------------------------------------
    sc = df[df.is_late & (df.n_sellers == 1) & df.legs_valid].copy()
    hl = sc.order_delivered_carrier_date > sc.shipping_limit
    cf = (sc.order_delivered_customer_date - (sc.order_delivered_carrier_date - sc.shipping_limit)).dt.normalize()
    sc["root"] = np.select([hl & (cf <= sc.order_estimated_delivery_date.dt.normalize()), hl],
                           ["1 Seller hand-over only", "2 Seller hand-over + carrier"], "3 Carrier leg only")
    la = t("late_attribution").set_index("root_cause")
    for cause, n in sc.root.value_counts().items():
        results.append(check(f"late orders: {cause}", int(n), int(la.loc[cause, "late_orders"])))
    he = t("handover_effect").set_index("seller_handover_late")
    scope = df[(df.n_sellers == 1) & df.legs_valid]
    results += [check("late rate when seller hand-over late",
                      scope[scope.handover_late == 1].is_late.mean(), he.loc[True, "late_rate"]),
                check("late rate when seller hand-over on time",
                      scope[scope.handover_late == 0].is_late.mean(), he.loc[False, "late_rate"])]

    # --- seller concentration (top 10%) ----------------------------------------------------------
    per = scope.groupby("seller_id").apply(lambda g: pd.Series({
        "orders": len(g), "sl": int((g.is_late & (g.handover_late == 1)).sum())}), include_groups=False).reset_index()
    per = per.sort_values(["sl", "orders", "seller_id"], ascending=[False, False, True])
    top = per.head(math.ceil(0.10 * len(per)))
    results.append(check("top 10% sellers: share of seller-late orders", top.sl.sum() / per.sl.sum(),
                         t("seller_concentration").set_index("top_pct_of_sellers").loc[0.10, "share_of_seller_late_orders"]))

    # --- promise backtest (static lane P90) ---------------------------------------------------------
    train = df[df.order_purchase_timestamp < "2018-01-01"]
    test = df[df.order_purchase_timestamp >= "2018-01-01"].copy()
    lane = train[train.seller_state.notna()].groupby(["seller_state", "customer_state"]).actual_days
    lane_p = lane.quantile(0.90)[lane.size() >= 30].rename("lane_p90").reset_index()
    state_p = train.groupby("customer_state").actual_days.quantile(0.90).rename("state_p90").reset_index()
    test = test.merge(lane_p, on=["seller_state", "customer_state"], how="left").merge(state_p, on="customer_state", how="left")
    test["p90"] = np.ceil(test.lane_p90.fillna(test.state_p90).fillna(train.actual_days.quantile(0.90)))
    pb = t("promise_backtest").set_index("policy")
    results += [check("backtest: Olist on-time rate (2018)", (test.actual_days <= test.promised_days).mean(),
                      pb.loc["0 Olist actual promise", "on_time_rate"]),
                check("backtest: lane P90 on-time rate (2018)", (test.actual_days <= test.p90).mean(),
                      pb.loc["3 Lane P90 (history)", "on_time_rate"]),
                check("backtest: lane P90 avg promise (2018)", test.p90.mean(), pb.loc["3 Lane P90 (history)", "avg_promised_days"])]

    # --- review text --------------------------------------------------------------------------------
    low = rv[(rv.review_score <= 2) & (rv.review_comment_message.notna() | rv.review_comment_title.notna())].copy()
    low["txt"] = (low.review_comment_title.fillna("") + " " + low.review_comment_message.fillna("")).str.lower()
    pat = re.compile(r"n[aã]o (recebi|chegou|foi entregue)|ainda n[aã]o")
    tx = t("low_score_comment_topics").set_index("is_late")
    results.append(check("late 1-2★ reviews saying 'not received'",
                         low[low.is_late].txt.map(lambda x: bool(pat.search(x))).mean(), tx.loc[True, "share_not_received"]))

    # --- sizing scenario A --------------------------------------------------------------------------
    a = sc[(sc.root == "1 Seller hand-over only") & sc.review_score.notna()]
    uplift = len(a) / len(rv) * (ontime.review_score.mean() - a.review_score.mean())
    op = t("opportunity_sizing").iloc[0]
    results += [check("scenario A: orders fixed", len(a), int(op.orders_fixed)),
                check("scenario A: avg score uplift (naive)", uplift, op.avg_score_uplift_naive)]

    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
