# KIS Portfolio Workflow Notes

## 전체 계좌 현황

1. Call `get-latest-portfolio-summary` for the latest MotherDuck aggregate.
2. Call `get-portfolio-daily-change` for recent movement.
3. If snapshots are stale or missing, call `refresh-all-account-snapshots`.
4. Re-run `get-latest-portfolio-summary` to answer from stored snapshots.

## 계좌별 분석

1. Map user language to `ria`, `isa`, `brokerage`, `irp`, or `pension`.
2. Use `get-portfolio-history` for stored snapshots.
3. Use `get-account-balance` only when the user needs current live KIS data.
4. Do not expose full account numbers in prose.

## 조회와 주문의 경계

- Portfolio summaries, rebalancing ideas, and risk checks are read-only.
- `submit-stock-order` and `submit-overseas-stock-order` are disabled stubs.
- Do not describe stub calls as successful orders.

## 데이터 출처 표기

- `source=motherduck`: DB-only snapshot/analytics result.
- `source=kis_api`: live KIS API call, usually with `raw` response preserved.
- `source=order_stub`: disabled order stub, no KIS order API call.
