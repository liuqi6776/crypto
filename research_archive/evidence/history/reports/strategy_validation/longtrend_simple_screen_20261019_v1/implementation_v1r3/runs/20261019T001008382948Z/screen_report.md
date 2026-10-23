> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Long-trend simple screen v1r3

Status: descriptive replay under exact root approval; no OOS claim and no trading readiness. All 2021–2025 data have previous exposure. Perpetual source clocks/values and per-side costs remain assumptions where specified. Spot return matrix slots with source clock exceptions are NOT_RUN. Saved-reference parity `PASS_ALL_SIX` is a code/accounting safeguard, not another strategy candidate.

| Candidate | Frozen screen | Failed criteria | Missing evidence |
|---|---:|---:|---:|
| EMA200_H4_LONG_CASH | PASSES_SIMPLE_EXPOSED_HISTORY_SCREEN | 0 | 0 |
| DONCHIAN120_60_H4_LONG_CASH | PASSES_SIMPLE_EXPOSED_HISTORY_SCREEN | 0 | 0 |
| EMA200_H4_LONG_SHORT | FAIL | 18 | 0 |

## Spot source exception handling

Original ZIP content passed hashes, OHLCV checks and exact monthly open grids. Each of BTC/ETH/SOL contains five close_time identity exceptions in 2021. The strict admission requires close_time = open_time + 4h - 1 native timestamp unit (milliseconds for 2021 millisecond rows; microseconds for 2025 microsecond rows). The matching original anomaly-ledger records are `SHORT_BAR` with `cause_verified=false`; they do not establish halt or corruption causes. These source rows were not changed or normalized. No affected spot universe is prefix-ranked.

| Spot slot | Status | Symbols excluded |
|---|---|---|
| BTCETHSOL|allocation20|base | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT,ETHUSDT,SOLUSDT |
| BTCETHSOL|allocation20|stress | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT,ETHUSDT,SOLUSDT |
| BTCETHSOL|allocation20|severe | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT,ETHUSDT,SOLUSDT |
| BTCETHSOL|allocation100|base | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT,ETHUSDT,SOLUSDT |
| BTCETHSOL|allocation100|stress | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT,ETHUSDT,SOLUSDT |
| BTCETHSOL|allocation100|severe | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT,ETHUSDT,SOLUSDT |
| BTCETH|allocation20|base | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT,ETHUSDT |
| BTCETH|allocation20|stress | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT,ETHUSDT |
| BTCETH|allocation20|severe | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT,ETHUSDT |
| BTCETH|allocation100|base | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT,ETHUSDT |
| BTCETH|allocation100|stress | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT,ETHUSDT |
| BTCETH|allocation100|severe | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT,ETHUSDT |
| BTC|allocation20|base | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT |
| BTC|allocation20|stress | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT |
| BTC|allocation20|severe | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT |
| BTC|allocation100|base | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT |
| BTC|allocation100|stress | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT |
| BTC|allocation100|severe | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | BTCUSDT |
| ETH|allocation20|base | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | ETHUSDT |
| ETH|allocation20|stress | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | ETHUSDT |
| ETH|allocation20|severe | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | ETHUSDT |
| ETH|allocation100|base | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | ETHUSDT |
| ETH|allocation100|stress | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | ETHUSDT |
| ETH|allocation100|severe | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | ETHUSDT |
| SOL|allocation20|base | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | SOLUSDT |
| SOL|allocation20|stress | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | SOLUSDT |
| SOL|allocation20|severe | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | SOLUSDT |
| SOL|allocation100|base | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | SOLUSDT |
| SOL|allocation100|stress | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | SOLUSDT |
| SOL|allocation100|severe | NOT_RUN_SPOT_SOURCE_TIME_IDENTITY_EXCEPTION | SOLUSDT |

The spot comparator uses a different genuine native 4h valuation/fill grid and is not a matched-quote or pure funding attribution. Perpetual constant-long references are complete only where the account itself completed; invalid prefixes remain nonrankable. CASH is a zero-yield analytic comparator.

Nine-gate status for each arm remains UNVERIFIED. See the three per-strategy reports and exact case ledgers. No historical period is described as OOS.
