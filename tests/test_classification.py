from kis_portfolio.services.classification import classify_domestic_holding


def test_master_group_code_fe_maps_to_overseas_indirect():
    result = classify_domestic_holding("000001", "국내상장해외ETF", master={"group_code": "FE"})

    assert result["exposure_type"] == "overseas_indirect"
    assert result["confidence"] == "high"


def test_etf_name_with_global_keywords_maps_to_overseas_indirect():
    result = classify_domestic_holding("0015B0", "KoAct 미국나스닥성장기업액티브", master={"group_code": "EF"})

    assert result["exposure_type"] == "overseas_indirect"
    assert result["confidence"] == "medium"


def test_group_e_with_global_keywords_maps_to_overseas_indirect():
    result = classify_domestic_holding("426030", "TIME 미국나스닥100액티브", master={"group_code": "E"})

    assert result["exposure_type"] == "overseas_indirect"


def test_domestic_keyword_etf_stays_domestic_direct():
    result = classify_domestic_holding("0074K0", "KoAct K수출핵심기업TOP30액티브", master={"group_code": "EF"})

    assert result["exposure_type"] == "domestic_direct"


def test_group_e_domestic_keyword_etf_stays_domestic_direct():
    result = classify_domestic_holding("0162Y0", "TIME 코스닥액티브", master={"group_code": "E"})

    assert result["exposure_type"] == "domestic_direct"


def test_override_wins_over_master_and_heuristic():
    result = classify_domestic_holding(
        "0015B0",
        "KoAct 미국나스닥성장기업액티브",
        master={"group_code": "EF"},
        override={
            "exposure_type": "domestic_direct",
            "exposure_region": "kr",
            "asset_subtype": "etf",
        },
    )

    assert result["exposure_type"] == "domestic_direct"
    assert result["source"] == "override"


def test_ambiguous_etf_becomes_unknown_with_warning():
    result = classify_domestic_holding("999999", "TIME 액티브", master={"group_code": "EF"})

    assert result["exposure_type"] == "unknown"
    assert result["warning"] is not None
