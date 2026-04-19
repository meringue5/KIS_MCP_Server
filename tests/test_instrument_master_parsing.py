from pathlib import Path

from kis_portfolio.services.instrument_master import _parse_market_file


def test_parse_market_file_uses_byte_width_for_cp949_name(tmp_path):
    spec = {
        "market": "KRX",
        "tail_len": 4,
        "field_specs": [2, 2],
        "field_names": ["group_code", "etp_code"],
    }
    head = b"123456789" + b"STD123456789" + "한글ETF".encode("cp949")
    tail = b"FE01"
    path = tmp_path / "sample.mst"
    path.write_bytes(head + tail + b"\n")

    rows = _parse_market_file(path, spec)

    assert rows == [{
        "symbol": "123456789",
        "market": "KRX",
        "standard_code": "STD123456789",
        "name": "한글ETF",
        "group_code": "FE",
        "etp_code": "01",
        "idx_large_code": None,
        "idx_mid_code": None,
        "idx_small_code": None,
    }]
