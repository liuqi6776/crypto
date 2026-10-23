> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Strategy Validation Report

## Identity and pre-registration

| Field | Value |
| :--- | :--- |
| Strategy / model and version | Action-aware CatBoost policy catboost_d6_i500, threshold 0.0 bps; R4 validation-only runner |
| Research hypothesis and economic mechanism | A pooled action-value model ranks a frozen set of legal channel/entry/stop/target actions using causal channel context. It is a fixed-notional historical policy simulation. |
| Code commit or file hashes; config hash | `scripts/run_channel_ml_2024_2025_v1r4.py` SHA `d38beb3cbbce6cc62dbf9b00ffbd9250c0e7f4c64fa18747429350b06fbf121e`; `scripts/channel_ml_2024_2025_v1r4_framework.py` SHA `351fa6e9c676692645b844e8a1f3c80468d55b95933e542312026d45805a5785`; R4 prereg `fb6177cf89c200583a46b70ada5b3156e7b754681b26794c38bc63f23ed4050b`; frozen model identity `60bd155f50e22e4267572ecb2ff4797f1f220cd92a40e4d4a1687be2d2ce6c95` |
| Data manifest/hash; exchange; perpetual label | local minute copies in `source_data/channel_ml_2024_2025_v1/`; validation manifest `2533daab643010398d0a5f0c5d988989933f7d8e4bcc6578e8a9140ec041c871`; source label evidence `VERIFIED_PERPETUAL_LABEL`; frozen parent model/freeze files in `reports/strategy_validation/channel_ml_2024_2025_v1r2/` |
| Symbols, timeframe, UTC decision/fill semantics | ETHUSDT and SOLUSDT; 1-minute OHLCV with 5-minute decision cadence and 5m/15m channels. Decision and availability are UTC; fill is a strict trade-through OHLC proxy with within-minute timing interval, not observed exchange execution. |
| Previously inspected windows and searches | 2022–2023 used for model development/tuning; 2024–2025 were previously touched in legacy research; 2024 price files were opened by an earlier failed reader before PnL. Pre-2024 training and 2023-only tuning selected the frozen CatBoost depth-6/500-iteration model and 0 bps threshold for display. The 2023 search had no positive eligible candidate, so this is the sample-eligible least-bad candidate, not a qualified profitable strategy. No validation outcomes were used for selection. The supervised action labels were sampled every 60 minutes for resource control while policy replay decides every 5 minutes; this may underrepresent some 5-minute situations. These windows are not untouched holdouts. |
| Frozen train / validation / untouched test windows (UTC) | Warm-up 2021-12; train 2022-01-01, 2023-01-01) UTC; tune [2023-01-01, 2024-01-01) UTC; final fit 2022–2023, frozen before validation; validation 2024 [2024-01-01, 2025-01-01) and 2025 [2025-01-01, 2026-01-01) UTC. No untouched test claim. |
| Primary metric, acceptance thresholds and risk limits, set before Test | 2023 policy cumulative net lower bound at fixed quote notional; positive eligibility required at least 30 price-known trades per symbol, complete price paths, and positive aggregate two-symbol net lower bound. No candidate qualified positive; threshold 0.0 bps candidate is display-only least-bad. Frozen geometry: entry edge 5%/10% of channel width; TP 0.6/0.8/0.9 of width from trade-side edge; stop distance 0.0125/0.025/0.05/0.075 of width; planned stop risk <=1% of entry price, gross reward/risk >=1, TP gross reward >6 bps, and SL strictly inside channel. |
| Fee, funding, spread, slippage, capacity and margin assumptions | Fixed quote notional $1,000. Base: maker 2 bps entry/TP, taker 5 bps stop/time exits, 2 bps slippage; 5-minute decisions, 1-minute delay, 60-minute max hold, 5-minute cooldown, pending TTL 5/15 minutes. Stress: fees/slippage doubled, 2 bps trade-through, TTL halved with 2-minute minimum. Actual funding event times use hourly mark-open proxy with charge/not-charge bounds. No verified spread, queue, exact fill, capacity, or margin model. |
| Report date and reviewer | 20261008T132354Z; independent Codex audit: PASS for 40 saved-ledger accounting checks ([audit (`provenance:nonincluded/crypto-leverage/docs/CHANNEL_ML_2024_2025_CODEX_FINAL_40_LEDGER_AUDIT_20261008.json`)); overall strategy verdict remains UNVERIFIED |

## Gate evidence

| Gate | Status | Evidence / window | Failure, blocker, or next evidence needed |
| :--- | :--- | :--- | :--- |
| 1 Data integrity and causal availability | BLOCKED | Validation local price-copy SHA, UTC, and minute-grid checks are recorded in `source_data/channel_ml_2024_2025_v1/validation_minute_manifest.json` and `reports/strategy_validation/channel_ml_2024_2025_v1r4/validation_input_verification.json`; 2024–2025 | Exact mark-time valuation and complete causal execution/fill evidence are unavailable. |
| 2 Implementation, lookahead and recursive analysis | BLOCKED | 45 focused tests passed per `docs/CHANNEL_ML_2024_2025_CODEX_FOCUSED_TESTS_20261008.json`; frozen R4 runner/framework hashes | Standard full-suite collection remains blocked by a missing existing `r3i` module; Freqtrade lookahead/recursive analysis and genuine exchange fill-timing validation were not run. |
| 3 In-sample mechanism and search disclosure | PASS | `reports/strategy_validation/channel_ml_2024_2025_v1r2/preregistration.json`, `prevalidation_training_audit.json`, `prevalidation_selection.json`, and `final_model_freeze.json`; pre-2024 only | Exploratory only; supervised labels sampled hourly while policy decisions are 5-minute. Does not generalize to all ML or the user's discretionary 1-minute method. |
| 4 Untouched walk-forward OOS and ML leakage | BLOCKED | Final model was frozen before these R4 validation outputs; 2024 and 2025 reported separately | The years were touched in legacy research and cannot be called untouched. |
| 5 Both-side fees, observed funding, spread, slippage and fills | BLOCKED | Ledgers include fee cashflows and funding event accounting bounds | No observed spread, queue position, exact fill, or genuine mark-time valuation; hourly mark-open is a proxy. |
| 6 Regime, symbol and parameter robustness | BLOCKED | ETH/SOL; 2024/2025; base/stress rows below | Historical regimes and execution assumptions are limited; no parameter-neighborhood pass. |
| 7 Leverage, margin and liquidation stress | BLOCKED | No leverage multiplier applied | No account-level margin or mark-price liquidation path; do not multiply these fixed-notional results by 10. |
| 8 Dry-run observation and reconciliation | NOT_RUN | No authorized dry-run records | No exchange observations were used. |
| 9 Small-capital live observation and reconciliation | BLOCKED | Research-only workspace | No live execution records; no live orders are authorized. |

## OOS results

This table merges 29 original R4 ledgers whose SHA and trade accounting were independently audited with 11 separately frozen resume cases. Original request/no-fill counters were not saved and are `N/A`; the report recomputes only the metrics possible from saved ledgers and preserves exact counts for the 11 resumed cases. Values are fixed-$1,000 quote-notional basis points. Lower/upper include only price-known exits and bound whether ambiguous funding events were charged under the declared hourly mark-open proxy; they are not overall execution-risk bounds. Win rate, profit factor, and worst-month values below use only the complete-cashflow subset shown in column five.

| Year | Symbol | Cost case | Price-known exits | Complete cashflow N | Unknown cashflow N | Net lower bps | Net upper bps | Unknown open paths | Complete-subset win rate | Complete-subset PF | Complete-subset worst month |
|---:|:---|:---|---:|---:|---:|---:|---:|---:|---:|---:|:---|
| 2024 | ETHUSDT | base | 55 | 55 | 0 | -712.226 bps | -712.226 bps | 0 | 7.27273% | 0.382782 | {'month': '2024-12', 'net_bps': -288.45445016708237} |
| 2024 | ETHUSDT | stress | 30 | 30 | 0 | -711.205 bps | -711.205 bps | 0 | 10% | 0.306179 | {'month': '2024-08', 'net_bps': -213.22229737913844} |
| 2024 | SOLUSDT | base | 164 | 164 | 0 | -997.43 bps | -997.43 bps | 0 | 15.2439% | 0.742137 | {'month': '2024-03', 'net_bps': -318.53346002958256} |
| 2024 | SOLUSDT | stress | 107 | 107 | 0 | -2307.17 bps | -2307.17 bps | 0 | 13.0841% | 0.356734 | {'month': '2024-04', 'net_bps': -530.95305992161} |
| 2025 | ETHUSDT | base | 124 | 124 | 0 | -1720.76 bps | -1720.76 bps | 0 | 11.2903% | 0.35522 | {'month': '2025-02', 'net_bps': -355.6836255638221} |
| 2025 | ETHUSDT | stress | 74 | 74 | 0 | -1500.44 bps | -1500.44 bps | 0 | 12.1622% | 0.288598 | {'month': '2025-04', 'net_bps': -440.715889277406} |
| 2025 | SOLUSDT | base | 170 | 170 | 0 | -2474.95 bps | -2474.95 bps | 0 | 10.5882% | 0.372944 | {'month': '2025-01', 'count': 24, 'sum': -486.107941311345, 'mean': -20.254497554639375} |
| 2025 | SOLUSDT | stress | 118 | 118 | 0 | -2510.88 bps | -2510.88 bps | 0 | 11.0169% | 0.333104 | {'month': '2025-01', 'count': 22, 'sum': -641.3471740021891, 'mean': -29.152144272826778} |

base aggregate across the four symbol-year slices: -5905.37/-5905.37 bps lower/upper; stress aggregate across the four symbol-year slices: -7029.69/-7029.69 bps lower/upper. These sums combine separate fixed-notional slices; they are not a compounded account return.



Post-hoc fee-only sensitivity: charging maker fees of 2.00 bps per side on the same 513 saved fills yields -443.796580 USDT aggregate at fixed $1,000 quote notional per trade, versus -590.536705 USDT under baseline fees. Fills, exits, slippage, and model are unchanged; stop executions as maker are not established. This is a fee-only what-if, not proof of maker execution. See fee sensitivity evidence (`provenance:nonincluded/crypto-leverage/docs/CHANNEL_ML_2024_2025_CODEX_MAKER_FEE_SENSITIVITY_20261008.json`).

| Metric | Fold/window values | Aggregate / definition |
| :--- | :--- | :--- |
| Net OOS return | See annual/symbol/base/stress table; fixed quote-notional bps | See lower/upper totals above; no account return conversion. |
| OOS Sharpe | N/A | Not computed by the frozen evaluator; serial dependence and sparse events make an unsupported reconstruction inappropriate. |
| Max drawdown | Account-equity MaxDD: N/A; supplemental trade-bps drawdown: Largest fixed-notional cumulative-bps drawdown across complete-cashflow slices: 2530.73 bps (catboost_d6_i500_SOLUSDT_2025_stress). | No account equity path, compounding, or margin model was evaluated; the supplemental cumulative fixed-notional trade-bps drawdown uses complete-cashflow ledgers only and is not account drawdown. |
| Win rate | Complete-cashflow subset per row | Subset denominator is explicitly shown; unknown-cashflow trades are excluded. |
| Profit factor | Complete-cashflow subset per row | Subset denominator is explicitly shown; unknown-cashflow trades are excluded. |
| Trade count | Price-known exits and complete-cashflow N per row | Pending/no-fill/open-path counts are available for the 11 resume cases; original 29-case runner counters were not saved and are `N/A`. |
| MAE / MFE | N/A | Not computed by the frozen evaluator. |
| Worst month | Complete-cashflow subset per row | Lower/upper annual totals include priced unknown-cashflow trades. |
| Worst trade | Worst complete-cashflow trade across the listed slices: -88.9865 bps. | Complete-cashflow subset only; event-bounded and unknown-path trades are separate. |
| Minimum liquidation distance by leverage tier | N/A | No leverage or liquidation path was modeled. |

## Decision

**Verdict:** `EXPLORATORY / UNVERIFIED`

**Frozen-model feature/action description:** model summary (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/channel_ml_validation_resume_v1/model_feature_and_action_summary_20261008T132354Z.json`) (descriptive only; not used for selection).
**Reason and limiting evidence:** Gate 1 is BLOCKED overall; execution and mark-price assumptions remain proxies, and 2024–2025 are contaminated historical windows. The original R4 segment's old request/no-fill counters were not preserved; their unavailable values are `N/A`. Hourly mark-open funding bounds cover only event cashflow ambiguity, not fill, spread, queue, or liquidation uncertainty.

**Next permissible research step:** Independent review of the completed frozen ledgers and report; a later study would need genuinely untouched future data, verified mark-time series, exact execution evidence, and an account-level margin model.

No verdict promises future returns or authorizes orders.
