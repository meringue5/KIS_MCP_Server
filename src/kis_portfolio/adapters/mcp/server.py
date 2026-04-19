"""Single public MCP adapter for KIS Portfolio Service."""

from __future__ import annotations

import logging

from dotenv import load_dotenv
from mcp.server.fastmcp.server import FastMCP

from kis_portfolio import db as kisdb
from kis_portfolio.account_registry import (
    get_account,
    load_account_registry,
    scoped_account_env,
)
from kis_portfolio.analytics.bollinger import get_bollinger_bands as analyze_bollinger_bands
from kis_portfolio.analytics.asset_overview import (
    get_total_asset_allocation_history as analyze_total_asset_allocation_history,
    get_total_asset_daily_change as analyze_total_asset_daily_change,
    get_total_asset_history as analyze_total_asset_history,
    get_total_asset_trend as analyze_total_asset_trend,
)
from kis_portfolio.analytics.portfolio import (
    get_latest_portfolio_summary as analyze_latest_portfolio_summary,
    get_portfolio_anomalies as analyze_portfolio_anomalies,
    get_portfolio_daily_change as analyze_portfolio_daily_change,
    get_portfolio_trend as analyze_portfolio_trend,
)
from kis_portfolio.auth import get_token_status as inspect_token_status
from kis_portfolio.services import kis_api
from kis_portfolio.services.account import fetch_balance_snapshot
from kis_portfolio.services.overview import build_total_asset_overview


logger = logging.getLogger("kis-portfolio-mcp")
load_dotenv()

DEFAULT_ACCOUNT_LABEL = "brokerage"
mcp = FastMCP("KIS Portfolio Service", dependencies=["httpx", "xmltodict"])


def _account_label(label: str = "") -> str:
    return (label or DEFAULT_ACCOUNT_LABEL).strip().lower()


def _account_id_from_label(account_label: str = "") -> str:
    if not account_label:
        return ""
    return get_account(account_label).cano


def _wrap_raw(raw: dict, account=None, source: str = "kis_api", **metadata) -> dict:
    payload = {
        "source": source,
        "status": "ok",
        "raw": raw,
    }
    if account is not None:
        payload["account"] = account.public_dict()
    payload.update({k: v for k, v in metadata.items() if v is not None})
    return payload


async def _call_for_account(account_label: str, func, *args, source: str = "kis_api", **kwargs) -> dict:
    account = get_account(_account_label(account_label))
    with scoped_account_env(account):
        raw = await func(*args, **kwargs)
    return _wrap_raw(raw, account=account, source=source)


def _disabled_order_response(order_kind: str) -> dict:
    return {
        "source": "order_stub",
        "status": "disabled",
        "order_kind": order_kind,
        "message": "주문 기능은 현재 stub입니다. 실제 KIS 주문 API는 호출하지 않습니다.",
    }


@mcp.tool(
    name="get-configured-accounts",
    description="등록된 KIS 계좌 목록을 반환합니다. 계좌번호와 secret은 마스킹/비노출합니다.",
)
async def get_configured_accounts():
    accounts = load_account_registry()
    return {
        "source": "account_registry",
        "count": len(accounts),
        "accounts": [account.public_dict() for account in accounts],
    }


@mcp.tool(
    name="get-all-token-statuses",
    description="모든 등록 계좌의 KIS 접근토큰 캐시 상태를 조회합니다. 토큰 값은 반환하지 않습니다.",
)
async def get_all_token_statuses():
    accounts = load_account_registry()
    statuses = []
    for account in accounts:
        with scoped_account_env(account):
            status = inspect_token_status()
        status.pop("token", None)
        statuses.append({"account": account.public_dict(), "token_status": status})
    return {"source": "token_cache", "count": len(statuses), "accounts": statuses}


@mcp.tool(
    name="get-account-balance",
    description="지정한 단일 계좌 라벨의 현재 잔고를 조회하고 MotherDuck에 스냅샷을 저장합니다. 전체 자산현황에는 refresh-all-account-snapshots를 우선 사용합니다.",
)
async def get_account_balance(account_label: str):
    account = get_account(account_label)
    with scoped_account_env(account):
        result = await fetch_balance_snapshot(save_snapshot=True, return_metadata=True)
    saved_snapshot_id = result.get("saved_snapshot_id")
    return _wrap_raw(
        result["raw"],
        account=account,
        source="kis_api",
        saved_snapshot_id=saved_snapshot_id,
        snapshot_status="saved" if saved_snapshot_id else "not_saved",
    )


@mcp.tool(
    name="refresh-all-account-snapshots",
    description="전체 자산현황/전체 계좌/내 포트폴리오 요청에 우선 사용할 도구입니다. 모든 등록 계좌 잔고를 순차 조회하고 MotherDuck에 스냅샷을 저장합니다.",
)
async def refresh_all_account_snapshots():
    results = []
    for account in load_account_registry():
        try:
            with scoped_account_env(account):
                result = await fetch_balance_snapshot(save_snapshot=True, return_metadata=True)
            saved_snapshot_id = result.get("saved_snapshot_id")
            results.append(
                _wrap_raw(
                    result["raw"],
                    account=account,
                    source="kis_api",
                    saved_snapshot_id=saved_snapshot_id,
                    snapshot_status="saved" if saved_snapshot_id else "not_saved",
                )
            )
        except Exception as e:
            logger.warning("Account refresh failed for %s: %s", account.label, e)
            results.append({
                "source": "kis_api",
                "status": "error",
                "account": account.public_dict(),
                "error": str(e),
            })
    return {
        "source": "kis_api",
        "count": len(results),
        "success_count": sum(1 for row in results if row["status"] == "ok"),
        "error_count": sum(1 for row in results if row["status"] == "error"),
        "accounts": results,
    }


@mcp.tool(
    name="get-total-asset-overview",
    description="전체 자산현황, 국내/해외 비중, 환율 반영 총자산, 파이차트용 allocation 데이터를 반환합니다. raw KIS 응답 대신 요약/비율을 우선 제공합니다.",
)
async def get_total_asset_overview(
    refresh: bool = True,
    save_snapshot: bool = True,
    overseas_account_label: str = DEFAULT_ACCOUNT_LABEL,
    top_n: int = 10,
    include_raw: bool = False,
):
    accounts = load_account_registry()
    refresh_status = {"requested": refresh}
    if refresh:
        refresh_result = await refresh_all_account_snapshots()
        refresh_status.update({
            "count": refresh_result.get("count", 0),
            "success_count": refresh_result.get("success_count", 0),
            "error_count": refresh_result.get("error_count", 0),
            "snapshot_status_counts": {
                "saved": sum(
                    1 for row in refresh_result.get("accounts", [])
                    if row.get("snapshot_status") == "saved"
                ),
                "not_saved": sum(
                    1 for row in refresh_result.get("accounts", [])
                    if row.get("snapshot_status") == "not_saved"
                ),
            },
        })

    con = kisdb.get_connection()
    portfolio_summary = analyze_latest_portfolio_summary(con, "", 30)
    overseas_account = get_account(_account_label(overseas_account_label), accounts)
    domestic_snapshot_rows = []
    domestic_symbols: list[str] = []
    for account in accounts:
        rows = kisdb.get_portfolio_snapshots(account.cano, limit=1)
        if not rows:
            continue
        row = rows[0]
        row["account"] = account.public_dict()
        row["account_label"] = account.label
        domestic_snapshot_rows.append(row)
        for holding in row.get("balance_data", {}).get("output1") or []:
            if isinstance(holding, dict) and holding.get("pdno"):
                domestic_symbols.append(str(holding["pdno"]).strip())
    instrument_map = kisdb.get_instrument_master_map(sorted(set(domestic_symbols)))
    override_map = kisdb.get_classification_override_map(sorted(set(domestic_symbols)))

    errors = []
    overseas_balance = {}
    overseas_deposit = {}
    with scoped_account_env(overseas_account):
        try:
            overseas_balance = await kis_api.inquery_overseas_balance("ALL")
        except Exception as e:
            logger.warning("Overseas balance fetch failed for overview: %s", e)
            errors.append({"tool": "get-overseas-balance", "error": str(e)})
        try:
            overseas_deposit = await kis_api.inquery_overseas_deposit("01", "000")
        except Exception as e:
            logger.warning("Overseas deposit fetch failed for overview: %s", e)
            errors.append({"tool": "get-overseas-deposit", "error": str(e)})

    overview = build_total_asset_overview(
        portfolio_summary=portfolio_summary,
        overseas_balance=overseas_balance,
        overseas_deposit=overseas_deposit,
        accounts=accounts,
        overseas_account=overseas_account,
        top_n=top_n,
        include_raw=include_raw,
        domestic_snapshot_rows=domestic_snapshot_rows,
        instrument_map=instrument_map,
        override_map=override_map,
    )
    normalized_holdings = overview.pop("_normalized_holdings", [])
    overview["refresh"] = refresh_status
    overview["status"] = "partial_error" if errors else "ok"
    if errors:
        overview["errors"] = errors
    if save_snapshot:
        overseas_snapshot_id = kisdb.insert_overseas_asset_snapshot(
            overseas_account.cano,
            overseas_account.label,
            overview["totals"].get("overseas_stock_eval_amt_krw"),
            overview["totals"].get("overseas_cash_amt_krw"),
            overview["totals"].get("overseas_total_asset_amt_krw"),
            overview["overseas"].get("fx_rates"),
            overseas_balance,
            overseas_deposit,
        )
        overview_snapshot_id = kisdb.insert_asset_overview_snapshot(
            overview["totals"],
            overview["allocation"],
            overview["classification_summary"],
            overview,
        )
        holding_count = kisdb.insert_asset_holding_snapshots(overview_snapshot_id, normalized_holdings)
        overview["saved_snapshot_id"] = overview_snapshot_id
        overview["overseas_snapshot_id"] = overseas_snapshot_id
        overview["holding_snapshot_count"] = holding_count
        overview["snapshot_status"] = "saved"
    else:
        overview["snapshot_status"] = "not_saved"
    overview["used_tools"] = [
        "refresh-all-account-snapshots" if refresh else None,
        "get-latest-portfolio-summary",
        "get-overseas-balance",
        "get-overseas-deposit",
    ]
    overview["used_tools"] = [tool for tool in overview["used_tools"] if tool]
    return overview


@mcp.tool(name="get-stock-price", description="국내주식 현재가를 조회합니다.")
async def get_stock_price(symbol: str, account_label: str = DEFAULT_ACCOUNT_LABEL):
    return await _call_for_account(account_label, kis_api.inquery_stock_price, symbol)


@mcp.tool(name="get-stock-ask", description="국내주식 호가를 조회합니다.")
async def get_stock_ask(symbol: str, account_label: str = DEFAULT_ACCOUNT_LABEL):
    return await _call_for_account(account_label, kis_api.inquery_stock_ask, symbol)


@mcp.tool(name="get-stock-info", description="국내주식 일별 기본 가격 정보를 조회합니다.")
async def get_stock_info(
    symbol: str,
    start_date: str,
    end_date: str,
    account_label: str = DEFAULT_ACCOUNT_LABEL,
):
    return await _call_for_account(account_label, kis_api.inquery_stock_info, symbol, start_date, end_date)


@mcp.tool(name="get-stock-history", description="국내주식 가격 이력을 조회하고 DB에 캐시합니다.")
async def get_stock_history(
    symbol: str,
    start_date: str,
    end_date: str,
    account_label: str = DEFAULT_ACCOUNT_LABEL,
):
    return await _call_for_account(account_label, kis_api.inquery_stock_history, symbol, start_date, end_date)


@mcp.tool(name="get-overseas-stock-price", description="해외주식 현재가를 조회합니다.")
async def get_overseas_stock_price(
    symbol: str,
    market: str,
    account_label: str = DEFAULT_ACCOUNT_LABEL,
):
    return await _call_for_account(account_label, kis_api.inquery_overseas_stock_price, symbol, market)


@mcp.tool(name="get-overseas-balance", description="해외주식 잔고를 조회합니다.")
async def get_overseas_balance(
    exchange: str = "ALL",
    account_label: str = DEFAULT_ACCOUNT_LABEL,
):
    return await _call_for_account(account_label, kis_api.inquery_overseas_balance, exchange)


@mcp.tool(name="get-overseas-deposit", description="해외주식 예수금과 적용환율을 조회합니다.")
async def get_overseas_deposit(
    wcrc_frcr_dvsn_cd: str = "02",
    natn_cd: str = "000",
    account_label: str = DEFAULT_ACCOUNT_LABEL,
):
    return await _call_for_account(
        account_label,
        kis_api.inquery_overseas_deposit,
        wcrc_frcr_dvsn_cd,
        natn_cd,
    )


@mcp.tool(name="get-exchange-rate-history", description="환율 이력을 조회하고 DB에 캐시합니다.")
async def get_exchange_rate_history(
    currency: str = "USD",
    start_date: str = "",
    end_date: str = "",
    period: str = "D",
    account_label: str = DEFAULT_ACCOUNT_LABEL,
):
    return await _call_for_account(
        account_label,
        kis_api.inquery_exchange_rate_history,
        currency,
        start_date,
        end_date,
        period,
    )


@mcp.tool(name="get-overseas-stock-history", description="해외주식 가격 이력을 조회하고 DB에 캐시합니다.")
async def get_overseas_stock_history(
    symbol: str,
    exchange: str = "NAS",
    end_date: str = "",
    period: str = "0",
    account_label: str = DEFAULT_ACCOUNT_LABEL,
):
    return await _call_for_account(
        account_label,
        kis_api.inquery_overseas_stock_history,
        symbol,
        exchange,
        end_date,
        period,
    )


@mcp.tool(name="get-period-trade-profit", description="국내주식 기간별 매매손익을 조회하고 DB에 저장합니다.")
async def get_period_trade_profit(
    start_date: str,
    end_date: str,
    account_label: str = DEFAULT_ACCOUNT_LABEL,
):
    return await _call_for_account(account_label, kis_api.inquery_period_trade_profit, start_date, end_date)


@mcp.tool(name="get-overseas-period-profit", description="해외주식 기간별 손익을 조회하고 DB에 저장합니다.")
async def get_overseas_period_profit(
    start_date: str,
    end_date: str,
    exchange: str = "",
    currency: str = "",
    account_label: str = DEFAULT_ACCOUNT_LABEL,
):
    return await _call_for_account(
        account_label,
        kis_api.inquery_overseas_period_profit,
        start_date,
        end_date,
        exchange,
        currency,
    )


@mcp.tool(name="get-order-list", description="국내주식 주문 내역을 조회합니다. 주문 실행은 하지 않습니다.")
async def get_order_list(
    start_date: str,
    end_date: str,
    account_label: str = DEFAULT_ACCOUNT_LABEL,
):
    return await _call_for_account(account_label, kis_api.inquery_order_list, start_date, end_date)


@mcp.tool(name="get-order-detail", description="국내주식 주문 상세 내역을 조회합니다. 주문 실행은 하지 않습니다.")
async def get_order_detail(
    order_no: str,
    order_date: str,
    account_label: str = DEFAULT_ACCOUNT_LABEL,
):
    return await _call_for_account(account_label, kis_api.inquery_order_detail, order_no, order_date)


@mcp.tool(name="submit-stock-order", description="국내주식 주문 stub입니다. 실제 주문 API를 호출하지 않습니다.")
async def submit_stock_order(symbol: str, quantity: int, price: int, order_type: str):
    return _disabled_order_response("domestic_stock")


@mcp.tool(name="submit-overseas-stock-order", description="해외주식 주문 stub입니다. 실제 주문 API를 호출하지 않습니다.")
async def submit_overseas_stock_order(
    symbol: str,
    quantity: int,
    price: float,
    order_type: str,
    market: str,
):
    return _disabled_order_response("overseas_stock")


@mcp.tool(name="get-portfolio-history", description="MotherDuck DB에서 국내/연금 계좌 feeder 스냅샷 이력을 조회합니다. 글로벌 총자산 이력에는 get-total-asset-history를 사용합니다.")
async def get_portfolio_history(
    account_label: str = DEFAULT_ACCOUNT_LABEL,
    start_date: str = "",
    end_date: str = "",
    limit: int = 50,
):
    account = get_account(_account_label(account_label))
    rows = kisdb.get_portfolio_snapshots(account.cano, start_date or None, end_date or None, limit)
    return {
        "source": "motherduck",
        "account": account.public_dict(),
        "count": len(rows),
        "snapshots": rows,
    }


@mcp.tool(name="get-price-from-db", description="MotherDuck DB에서 캐시된 주가 이력을 조회합니다.")
async def get_price_from_db(
    symbol: str,
    start_date: str,
    end_date: str,
    exchange: str = "KRX",
):
    return await kis_api.get_price_from_db(symbol, start_date, end_date, exchange)


@mcp.tool(name="get-exchange-rate-from-db", description="MotherDuck DB에서 캐시된 환율 이력을 조회합니다.")
async def get_exchange_rate_from_db(
    currency: str = "USD",
    start_date: str = "",
    end_date: str = "",
    period: str = "D",
):
    return await kis_api.get_exchange_rate_from_db(currency, start_date, end_date, period)


@mcp.tool(name="get-bollinger-bands", description="캐시된 주가 이력으로 볼린저 밴드를 계산합니다.")
async def get_bollinger_bands(
    symbol: str,
    exchange: str = "KRX",
    window: int = 20,
    num_std: float = 2.0,
    limit: int = 60,
):
    con = kisdb.get_connection()
    return analyze_bollinger_bands(con, symbol, exchange, window, num_std, limit)


@mcp.tool(name="get-latest-portfolio-summary", description="최신 MotherDuck 국내/연금 feeder 스냅샷 기준 합산 요약을 반환합니다. 글로벌 총자산 요약에는 get-total-asset-overview를 사용합니다.")
async def get_latest_portfolio_summary(
    account_label: str = "",
    lookback_days: int = 30,
):
    con = kisdb.get_connection()
    return analyze_latest_portfolio_summary(con, _account_id_from_label(account_label), lookback_days)


@mcp.tool(name="get-portfolio-daily-change", description="일별 대표 국내/연금 feeder 스냅샷 기준 평가금액 변화를 계산합니다. 글로벌 총자산 변화에는 get-total-asset-daily-change를 사용합니다.")
async def get_portfolio_daily_change(
    account_label: str = "",
    days: int = 14,
):
    con = kisdb.get_connection()
    return analyze_portfolio_daily_change(con, _account_id_from_label(account_label), days)


@mcp.tool(name="get-portfolio-anomalies", description="일별 국내/연금 feeder 스냅샷 기준 평가금액 변동 이상치를 탐지합니다.")
async def get_portfolio_anomalies(
    account_label: str = "",
    z_threshold: float = 2.0,
    lookback_days: int = 90,
    limit: int = 20,
):
    con = kisdb.get_connection()
    return analyze_portfolio_anomalies(
        con,
        _account_id_from_label(account_label),
        z_threshold,
        lookback_days,
        limit,
    )


@mcp.tool(name="get-portfolio-trend", description="일별 국내/연금 feeder 스냅샷 기준 평가금액 이동평균과 추세를 계산합니다.")
async def get_portfolio_trend(
    account_label: str = "",
    short_window: int = 7,
    long_window: int = 30,
    lookback_days: int = 90,
):
    con = kisdb.get_connection()
    return analyze_portfolio_trend(
        con,
        _account_id_from_label(account_label),
        short_window,
        long_window,
        lookback_days,
    )


@mcp.tool(name="get-total-asset-history", description="canonical 총자산 스냅샷 이력을 조회합니다.")
async def get_total_asset_history(
    days: int = 30,
    limit: int = 60,
):
    con = kisdb.get_connection()
    return analyze_total_asset_history(con, days, limit)


@mcp.tool(name="get-total-asset-daily-change", description="canonical 총자산 일별 변화량을 계산합니다.")
async def get_total_asset_daily_change(
    days: int = 14,
):
    con = kisdb.get_connection()
    return analyze_total_asset_daily_change(con, days)


@mcp.tool(name="get-total-asset-trend", description="canonical 총자산 이동평균과 추세를 계산합니다.")
async def get_total_asset_trend(
    short_window: int = 7,
    long_window: int = 30,
    lookback_days: int = 90,
):
    con = kisdb.get_connection()
    return analyze_total_asset_trend(con, short_window, long_window, lookback_days)


@mcp.tool(name="get-total-asset-allocation-history", description="canonical 총자산의 국내/해외/해외우회투자/현금 비중 이력을 조회합니다.")
async def get_total_asset_allocation_history(
    days: int = 30,
):
    con = kisdb.get_connection()
    return analyze_total_asset_allocation_history(con, days)


def main() -> None:
    logger.info("Starting KIS Portfolio MCP server...")
    mcp.run()
