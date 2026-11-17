"""Download the 9 raw Olist CSVs into data/raw/ (about 125 MB).

    python src/get_data.py

Source: Olist's own public mirror of the Brazilian E-Commerce dataset,
https://github.com/olist/work-at-olist-data (MIT licence) — the same files as
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/"
FILES = [
    "olist_customers_dataset.csv", "olist_geolocation_dataset.csv", "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv", "olist_order_reviews_dataset.csv", "olist_orders_dataset.csv",
    "olist_products_dataset.csv", "olist_sellers_dataset.csv", "product_category_name_translation.csv",
]
EXPECTED_ROWS = {"olist_orders_dataset.csv": 99441, "olist_order_items_dataset.csv": 112650}


def main() -> int:
    out = Path(__file__).resolve().parents[1] / "data" / "raw"
    out.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        dest = out / f
        if dest.exists() and dest.stat().st_size > 0:
            print(f"• {f} already present")
            continue
        print(f"↓ {f}")
        urllib.request.urlretrieve(BASE + f, dest)
    for f, n in EXPECTED_ROWS.items():
        with open(out / f, encoding="utf-8") as fh:
            rows = sum(1 for _ in fh) - 1
        if rows != n:
            print(f"✗ {f}: expected {n} rows, found {rows}")
            return 1
    print("✓ data ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
