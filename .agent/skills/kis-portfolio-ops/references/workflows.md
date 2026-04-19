# KIS Portfolio Workflow Notes

## 전체 계좌 현황

1. If the user asks for current total assets, all accounts, or "내 전체 자산현황",
   call `get-total-asset-overview`.
2. Use its `totals`, `allocation`, `classification_summary`, and `chart_data` fields for tables and charts.
3. Confirm `refresh.snapshot_status_counts.not_saved` is zero when freshness matters.
4. Use `classification_summary.by_economic_exposure` for domestic direct / overseas direct / overseas indirect / cash questions.
5. Call `get-total-asset-daily-change` when recent total-asset movement is useful.
6. Mention the tool names used when the user asks for provenance.

Do not replace step 1 with five separate `get-account-balance` calls unless the
overview and full refresh tools are unavailable.

## 계좌별 분석

1. Map user language to `ria`, `isa`, `brokerage`, `irp`, or `pension`.
2. Use `get-portfolio-history` for stored snapshots.
3. Use `get-account-balance` only when the user needs current live KIS data.
4. Do not expose full account numbers in prose.

## 국내/연금 feeder vs 글로벌 총자산

- `get-latest-portfolio-summary`, `get-portfolio-daily-change`, `get-portfolio-trend`, `get-portfolio-anomalies`
  are feeder analytics over domestic/retirement snapshots.
- For anything the user could read as "총자산", "전체 비중", "해외 포함", "환율 반영", or dashboard data,
  use the global total-asset tools instead.

## 조회와 주문의 경계

- Portfolio summaries, rebalancing ideas, and risk checks are read-only.
- `submit-stock-order` and `submit-overseas-stock-order` are disabled stubs.
- Do not describe stub calls as successful orders.

## 데이터 출처 표기

- `source=motherduck`: DB-only snapshot/analytics result.
- `source=kis_api`: live KIS API call, usually with `raw` response preserved.
- `source=order_stub`: disabled order stub, no KIS order API call.
