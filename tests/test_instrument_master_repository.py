import importlib


def test_upsert_instrument_master_bulk_loads_and_updates(tmp_path, monkeypatch):
    monkeypatch.setenv("KIS_DB_MODE", "local")
    monkeypatch.setenv("KIS_DATA_DIR", str(tmp_path))

    import kis_portfolio.db as kisdb

    kisdb = importlib.reload(kisdb)
    try:
        saved = kisdb.upsert_instrument_master([
            {
                "symbol": "A000001",
                "market": "KRX",
                "standard_code": "STD1",
                "name": "테스트ETF",
                "group_code": "EF",
                "etp_code": "1",
                "idx_large_code": "001",
                "idx_mid_code": "002",
                "idx_small_code": "003",
            },
            {
                "symbol": "A000002",
                "market": "KRX",
                "standard_code": "STD2",
                "name": "테스트리츠",
                "group_code": "RT",
                "etp_code": "",
                "idx_large_code": "004",
                "idx_mid_code": "005",
                "idx_small_code": "006",
            },
        ])
        assert saved == 2

        saved = kisdb.upsert_instrument_master([
            {
                "symbol": "A000001",
                "market": "KRX",
                "standard_code": "STD1B",
                "name": "업데이트ETF",
                "group_code": "FE",
                "etp_code": "9",
                "idx_large_code": "101",
                "idx_mid_code": "102",
                "idx_small_code": "103",
            }
        ])
        assert saved == 1

        con = kisdb.get_connection()
        rows = con.execute("""
            SELECT symbol, name, group_code, etp_code
            FROM instrument_master
            ORDER BY symbol
        """).fetchall()
    finally:
        kisdb.close_connection()

    assert rows == [
        ("A000001", "업데이트ETF", "FE", "9"),
        ("A000002", "테스트리츠", "RT", None),
    ]
