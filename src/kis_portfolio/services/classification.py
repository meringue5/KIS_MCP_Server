"""Instrument classification for portfolio exposure summaries."""

from __future__ import annotations

from typing import Any


ETF_BRANDS = (
    "KODEX",
    "TIGER",
    "ACE",
    "RISE",
    "TIME",
    "KoAct",
    "KOACT",
    "PLUS",
    "SOL",
    "HANARO",
    "KBSTAR",
    "ARIRANG",
    "WOORI",
)

OVERSEAS_HINTS = (
    "미국",
    "나스닥",
    "S&P",
    "글로벌",
    "GLOBAL",
    "해외",
    "선진국",
    "신흥국",
    "중국",
    "일본",
    "인도",
    "베트남",
)

DOMESTIC_HINTS = (
    "KOREA",
    "코리아",
    "코스피",
    "코스닥",
    "K수출",
    "K제조업",
    "제조업",
    "삼성전자",
    "SK하이닉스",
    "밸류업",
)

REIT_HINTS = ("REIT", "리츠", "부동산")


def _normalized_text(value: Any) -> str:
    return str(value or "").strip()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    upper = text.upper()
    return any(keyword.upper() in upper for keyword in keywords)


def is_etf_or_reit(name: str, master: dict | None) -> bool:
    group_code = _normalized_text((master or {}).get("group_code"))
    if group_code in {"E", "EF", "FE", "R", "RT"}:
        return True
    return _contains_any(name, ETF_BRANDS) or _contains_any(name, REIT_HINTS)


def classify_domestic_holding(
    symbol: str,
    name: str,
    master: dict | None = None,
    override: dict | None = None,
) -> dict:
    """Classify domestic holdings into direct/indirect/cash/unknown exposure."""
    symbol = _normalized_text(symbol)
    name = _normalized_text(name)
    master = master or {}

    if override:
        return {
            "symbol": symbol,
            "name": name,
            "exposure_type": override.get("exposure_type", "unknown"),
            "exposure_region": override.get("exposure_region"),
            "asset_subtype": override.get("asset_subtype"),
            "confidence": "high",
            "source": "override",
            "warning": None,
        }

    group_code = _normalized_text(master.get("group_code"))
    if group_code == "FE":
        return {
            "symbol": symbol,
            "name": name,
            "exposure_type": "overseas_indirect",
            "exposure_region": "global",
            "asset_subtype": "etf",
            "confidence": "high",
            "source": "instrument_master",
            "warning": None,
        }

    domestic_keyword = _contains_any(name, DOMESTIC_HINTS)
    overseas_keyword = _contains_any(name, OVERSEAS_HINTS)

    if group_code in {"R", "RT"}:
        if overseas_keyword and not domestic_keyword:
            exposure_type = "overseas_indirect"
            warning = None
        elif domestic_keyword and not overseas_keyword:
            exposure_type = "domestic_direct"
            warning = None
        else:
            exposure_type = "unknown"
            warning = "REIT 상품의 투자지역이 모호합니다."
        return {
            "symbol": symbol,
            "name": name,
            "exposure_type": exposure_type,
            "exposure_region": "global" if exposure_type == "overseas_indirect" else "kr",
            "asset_subtype": "reit",
            "confidence": "medium" if exposure_type != "unknown" else "low",
            "source": "heuristic",
            "warning": warning,
        }

    if group_code in {"E", "EF"} or is_etf_or_reit(name, master):
        if overseas_keyword and not domestic_keyword:
            return {
                "symbol": symbol,
                "name": name,
                "exposure_type": "overseas_indirect",
                "exposure_region": "global",
                "asset_subtype": "etf",
                "confidence": "medium",
                "source": "heuristic",
                "warning": None,
            }
        if domestic_keyword and not overseas_keyword:
            return {
                "symbol": symbol,
                "name": name,
                "exposure_type": "domestic_direct",
                "exposure_region": "kr",
                "asset_subtype": "etf",
                "confidence": "medium",
                "source": "heuristic",
                "warning": None,
            }
        return {
            "symbol": symbol,
            "name": name,
            "exposure_type": "unknown",
            "exposure_region": None,
            "asset_subtype": "etf",
            "confidence": "low",
            "source": "heuristic",
            "warning": "ETF/REIT 해외노출 분류가 애매합니다.",
        }

    return {
        "symbol": symbol,
        "name": name,
        "exposure_type": "domestic_direct",
        "exposure_region": "kr",
        "asset_subtype": "equity",
        "confidence": "high",
        "source": "default",
        "warning": None,
    }
