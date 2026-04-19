import duckdb

from kis_portfolio.analytics.asset_overview import (
    get_total_asset_allocation_history,
    get_total_asset_daily_change,
    get_total_asset_history,
    get_total_asset_trend,
)
from kis_portfolio.db.schema import init_schema


def make_connection():
    con = duckdb.connect(":memory:")
    init_schema(con)
    return con


def seed_asset_overview_snapshots(con, count=40):
    for day in range(1, count + 1):
        total = 1_000_000 + day * 10_000
        con.execute(
            """
            INSERT INTO asset_overview_snapshots (
                snapshot_at, base_currency,
                domestic_eval_amt_krw, overseas_stock_eval_amt_krw,
                overseas_cash_amt_krw, overseas_total_asset_amt_krw,
                total_eval_amt_krw, domestic_pct, overseas_pct,
                overseas_stock_pct, overseas_cash_pct,
                domestic_direct_amt_krw, overseas_direct_amt_krw,
                overseas_indirect_amt_krw, cash_amt_krw, unknown_amt_krw,
                allocation_data, classification_summary, overview_data
            )
            VALUES (
                DATE '2024-01-01' + (? * INTERVAL '1 day'),
                'KRW',
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                '{"ok": true}', '{"ok": true}', '{"ok": true}'
            )
            """,
            [
                day - 1,
                600_000 + day * 5_000,
                300_000 + day * 3_000,
                100_000 + day * 2_000,
                400_000 + day * 5_000,
                total,
                60.0,
                40.0,
                30.0,
                10.0,
                500_000,
                300_000,
                100_000,
                100_000,
                0,
            ],
        )


def test_total_asset_history_reads_daily_view():
    con = make_connection()
    seed_asset_overview_snapshots(con)

    result = get_total_asset_history(con, days=3650, limit=5)

    assert result["count"] == 5
    assert result["latest"]["total_eval_amt_krw"] == 1_400_000


def test_total_asset_daily_change_calculates_changes():
    con = make_connection()
    seed_asset_overview_snapshots(con, count=3)

    result = get_total_asset_daily_change(con, days=3)

    assert result["count"] == 3
    assert result["latest"]["change_amt"] == 10_000


def test_total_asset_trend_calculates_moving_averages():
    con = make_connection()
    seed_asset_overview_snapshots(con)

    result = get_total_asset_trend(con, short_window=7, long_window=30, lookback_days=3650)

    assert result["count"] == 11
    assert result["latest"]["trend"] == "상승추세"


def test_total_asset_allocation_history_returns_exposure_columns():
    con = make_connection()
    seed_asset_overview_snapshots(con, count=3)

    result = get_total_asset_allocation_history(con, days=3650)

    assert result["count"] == 3
    assert result["latest"]["overseas_indirect_amt_krw"] == 100_000
