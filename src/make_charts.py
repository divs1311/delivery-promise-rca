"""Charts for the README, drawn from outputs/tables/*.csv.

    python src/make_charts.py

Style: one colour job per chart (blue = on time / neutral, orange = late), thin bars, light grid,
no dual axes, values labelled selectively, text in ink colours rather than series colours.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter, PercentFormatter

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "outputs" / "tables"
OUT = ROOT / "outputs" / "charts"

BLUE, ORANGE, GREEN, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e8e7e3"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10.5, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.titlecolor": INK, "axes.titlelocation": "left", "figure.dpi": 150, "savefig.bbox": "tight",
    "legend.frameon": False,
})


def t(name: str) -> pd.DataFrame:
    return pd.read_csv(T / f"{name}.csv")


def label(s: str) -> str:
    return s.split(" ", 1)[1]  # drop the sort prefix "01 "


def subtitle(ax, text: str) -> None:
    ax.text(0, 1.02, text, transform=ax.transAxes, color=INK2, fontsize=9.5, va="bottom")


def dose_response() -> None:
    b = t("lateness_buckets")
    fig, ax = plt.subplots(figsize=(9, 4.2))
    late = b.lateness_bucket.str.contains("late")
    x = range(len(b))
    ax.bar(x, b.pct_1_2_star, width=0.62, color=[ORANGE if l else BLUE for l in late], zorder=2)
    for i, (v, sc) in enumerate(zip(b.pct_1_2_star, b.avg_score)):
        ax.text(i, v + 0.015, f"{v:.0%}", ha="center", color=INK, fontsize=9.5, fontweight="bold")
        ax.text(i, -0.075, f"{sc:.2f}★", ha="center", color=INK2, fontsize=8.5)
    ax.set_xticks(list(x), [label(s).replace(" days", "d") for s in b.lateness_bucket], fontsize=9)
    ax.tick_params(axis="x", pad=18)
    ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_ylim(0, 0.92)
    ax.set_ylabel("Share of reviews rated 1–2★")
    on_day = b.set_index("lateness_bucket").pct_1_2_star
    ax.set_title(f"Just 1–3 days late and the 1–2★ share jumps from {on_day['04 on the day']:.0%} "
                 f"to {on_day['05 1-3 days late']:.0%}", pad=22)
    subtitle(ax, "Delivered orders, Jan 2017–Aug 2018, by arrival vs promised date · avg score under each bar")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=BLUE, label="Early / on the day"), Patch(color=ORANGE, label="Late")],
              loc="upper left")
    fig.savefig(OUT / "01_lateness_vs_reviews.png")
    plt.close(fig)


def root_cause() -> None:
    a = t("late_attribution")
    fig, ax = plt.subplots(figsize=(9, 2.9))
    names = [label(s) for s in a.root_cause][::-1]
    ax.barh(names, a.share_of_late[::-1], color=BLUE, height=0.55, zorder=2)
    for i, (sh, n, d) in enumerate(zip(a.share_of_late[::-1], a.late_orders[::-1], a.avg_days_late[::-1])):
        ax.text(sh + 0.01, i, f"{sh:.0%}  ({n:,} orders, avg {d:.1f} days late)", va="center", color=INK, fontsize=9.5)
    ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_xlim(0, 1.05)
    ax.grid(axis="y", visible=False)
    carrier = a.set_index("root_cause").share_of_late["3 Carrier leg only"]
    ax.set_title(f"{carrier:.0%} of late orders are lost in transit, not at the seller", pad=22)
    subtitle(ax, "Late single-seller orders with valid timestamps, attributed by counterfactual hand-over")
    fig.savefig(OUT / "02_root_cause.png")
    plt.close(fig)


def handover() -> None:
    h = t("handover_effect").sort_values("seller_handover_late")
    fig, ax = plt.subplots(figsize=(6.2, 3.3))
    shares = list(h.share_of_orders)
    names = [f"Seller handed over on time\n({shares[0]:.0%} of orders)",
             f"Seller missed hand-over deadline\n({shares[1]:.0%} of orders)"]
    ax.bar(names, h.late_rate, color=[BLUE, ORANGE], width=0.5, zorder=2)
    for i, v in enumerate(h.late_rate):
        ax.text(i, v + 0.006, f"{v:.1%} late", ha="center", color=INK, fontweight="bold")
    ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_ylim(0, 0.25)
    ax.set_ylabel("Orders delivered late")
    ratio = h.late_rate.iloc[1] / h.late_rate.iloc[0]
    ax.set_title(f"A late hand-over makes a late delivery {ratio:.1f}× likelier", pad=22)
    subtitle(ax, "Single-seller orders with valid timestamps")
    fig.savefig(OUT / "03_handover_effect.png")
    plt.close(fig)


def spread() -> None:
    s = t("delivery_time_spread")
    fig, ax = plt.subplots(figsize=(9, 4.2))
    y = range(len(s))[::-1]
    names = [label(x) for x in s.distance_band]
    for yi, a, b in zip(y, s.p50_actual_days, s.p92_actual_days):
        ax.plot([a, b], [yi, yi], color=GRID, linewidth=6, solid_capstyle="round", zorder=1)
    ax.scatter(s.p50_actual_days, list(y), s=70, color=BLUE, zorder=3, label="Typical delivery (median)")
    ax.scatter(s.p92_actual_days, list(y), s=70, color=ORANGE, zorder=3, label="Delivery time hit 92% of the time")
    ax.scatter(s.median_promised_days, list(y), s=90, marker="|", color=INK, linewidths=2.2, zorder=4,
               label="Olist's median promise")
    for yi, a, b in zip(y, s.p50_actual_days, s.p92_actual_days):
        ax.text((a + b) / 2, yi + 0.2, f"{b - a:.0f} days of uncertainty", ha="center", va="bottom",
                color=INK2, fontsize=8.5)
    ax.set_yticks(list(y), names)
    ax.set_ylim(-0.5, len(s) - 0.35)
    ax.set_xlabel("Days from purchase")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, 40)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3, fontsize=9)
    ax.set_title("Promises sit at the 92nd percentile: the buffer is the price of variance", pad=22)
    subtitle(ax, "Seller-to-customer distance · the gap between typical and worst-case delivery sets the promise")
    fig.savefig(OUT / "04_delivery_time_spread.png")
    plt.close(fig)


def trend() -> None:
    m = t("monthly_trend")
    m["month"] = pd.to_datetime(m.month)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 5), sharex=True, gridspec_kw={"hspace": 0.35})
    a1.plot(m.month, m.late_rate, color=ORANGE, linewidth=2, marker="o", markersize=4)
    a1.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    a1.set_ylim(0, m.late_rate.max() * 1.3)
    a1.set_ylabel("Late rate")
    a1.set_title("When late deliveries spike, review scores fall the same month", pad=22)
    subtitle(a1, "Monthly, by purchase month · Black Friday 2017 and Feb–Mar 2018 stand out")
    for d, txt in [("2017-11-01", "Black Friday"), ("2018-03-01", "Feb–Mar 2018")]:
        r = m[m.month == d].iloc[0]
        a1.annotate(txt, (r.month, r.late_rate), xytext=(8, 2), textcoords="offset points", ha="left",
                    color=INK2, fontsize=8.5)
    a2.plot(m.month, m.avg_score, color=BLUE, linewidth=2, marker="o", markersize=4)
    a2.set_ylabel("Avg review score")
    a2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.1f}★"))
    fig.savefig(OUT / "05_monthly_trend.png")
    plt.close(fig)


def states() -> None:
    s = t("state_performance").sort_values("late_rate")
    fig, ax = plt.subplots(figsize=(9, 5.4))
    overall = t("kpi_summary").late_rate.iloc[0]
    colors = [ORANGE if v > overall else BLUE for v in s.late_rate]
    ax.barh(s.customer_state, s.late_rate, color=colors, height=0.6, zorder=2)
    ax.axvline(overall, color=INK2, linestyle="--", linewidth=1)
    ax.text(overall, len(s) - 0.3, f" overall {overall:.1%}", color=INK2, fontsize=9, va="bottom")
    for i, (v, n) in enumerate(zip(s.late_rate, s.orders)):
        ax.text(v + 0.003, i, f"{v:.0%} · {n:,} orders", va="center", color=INK2, fontsize=8)
    ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_xlim(0, 0.27)
    ax.grid(axis="y", visible=False)
    ax.set_title("Late rate by customer state", pad=22)
    sp = s.set_index("customer_state").late_rate["SP"]
    worst5 = s.tail(5).late_rate / sp
    subtitle(ax, f"States with ≥300 orders · the 5 worst states run {worst5.min():.0f}–{worst5.max():.0f}× São Paulo's late rate")
    fig.savefig(OUT / "06_state_late_rate.png")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in (dose_response, root_cause, handover, spread, trend, states):
        f()
        print(f"✓ {f.__name__}")


if __name__ == "__main__":
    main()
