"""Data-quality and verification tests.   Run:  pytest -q   (after src/run_analysis.py)"""
import re
import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "outputs" / "tables"


@pytest.fixture(scope="module")
def con():
    db = ROOT / "outputs" / "olist.duckdb"
    if not db.exists():
        pytest.skip("run `python src/run_analysis.py` first")
    c = duckdb.connect(str(db), read_only=True)
    yield c
    c.close()


def one(con, sql):
    return con.execute(sql).fetchone()[0]


def test_one_row_per_order(con):
    assert one(con, "SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM fct_orders") == 0


def test_window_and_status(con):
    assert one(con, "SELECT MIN(purchase_ts) >= TIMESTAMP '2017-01-01' AND MAX(purchase_ts) < TIMESTAMP '2018-09-01' FROM fct_orders")
    assert one(con, "SELECT COUNT(*) FROM fct_orders WHERE delivered_ts IS NULL") == 0


def test_day_arithmetic_is_consistent(con):
    # days_late must equal actual_days - promised_days for every order
    assert one(con, "SELECT COUNT(*) FROM fct_orders WHERE days_late <> actual_days - promised_days") == 0
    assert one(con, "SELECT COUNT(*) FROM fct_orders WHERE is_late <> (days_late > 0)") == 0


def test_review_scores_valid(con):
    assert one(con, "SELECT COUNT(*) FROM fct_orders WHERE has_review AND review_score NOT BETWEEN 1 AND 5") == 0


def test_attribution_scope(con):
    # every root-cause row is a late, single-seller order with a valid leg sequence
    assert one(con, "SELECT COUNT(*) FROM v_late_root_cause WHERE NOT is_late OR n_sellers <> 1 OR NOT legs_valid") == 0
    # categories partition the scope
    total = one(con, "SELECT COUNT(*) FROM fct_orders WHERE is_late AND n_sellers = 1 AND legs_valid")
    assert pd.read_csv(T / "late_attribution.csv").late_orders.sum() == total


def test_zip_codes_padded(con):
    assert one(con, "SELECT COUNT(*) FROM fct_orders WHERE LENGTH(customer_zip) <> 5") == 0
    # nearly every order should be geocoded once zips are padded (multi-seller orders have no seller zip)
    missing = one(con, "SELECT AVG((distance_km IS NULL AND n_sellers = 1)::INT) FROM fct_orders")
    assert missing < 0.01


def test_bucket_shares_sum_to_one():
    assert abs(pd.read_csv(T / "lateness_buckets.csv").share_of_orders.sum() - 1) < 1e-9


def test_rating_drag_identity():
    r = pd.read_csv(T / "rating_drag.csv").iloc[0]
    assert abs(r.rating_drag - r.share_late * r.score_gap) < 1e-12
    assert r.score_gap_ci_low < r.score_gap < r.score_gap_ci_high


def test_independent_verification_passes():
    res = subprocess.run([sys.executable, str(ROOT / "src" / "verify.py")], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout[-2000:]
    assert re.search(r"(\d+)/\1 checks passed", res.stdout)


def test_readme_fully_rendered():
    text = (ROOT / "README.md").read_text()
    assert "${" not in text
