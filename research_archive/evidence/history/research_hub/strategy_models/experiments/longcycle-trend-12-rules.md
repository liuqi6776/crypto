> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Long-cycle trend catalog, twelve rules

**Primary historical record:** `longcycle-trend-12-rules`. This is the single main card for this registry ID; cross-links are navigation only.

- Category: `strategy`; registry version pin: `ACCOUNT_RESULTS_V3_20261003`.
- Market / symbols / timeframe: `perpetual` / `BTC, ETH, SOL` / `4h, 1d`.
- Registry verdict: `EXPLORATORY_UNVERIFIED`; recommendation: `retain_benchmark`.
- Primary directory: `strategy_models`; linked factors with direct evidence: `sixfactor-trend-ema-macd-bollinger-family`.

## Evidence and bounded conclusion

retain_benchmark

### Registry result rows (historical text retained)

- **EMA200 4h 2025 account return**: `21.65` account_return_percent; population `95 completed trades`. Sharpe 0.759; MDD -19.86%.
- **MACD plus EMA200 4h 2025 account return**: `14.96` account_return_percent; population `155 trades`. Sharpe 0.706; MDD -19.11%.
- **Donchian55/20 4h 2025 account return**: `8.16` account_return_percent; population `41 trades`. Sharpe 0.433; MDD -21.69%.
- **BB120 plus EMA200 plus ATR3 4h 2025 account return**: `16.81` account_return_percent; population `19 completed trades`. Sharpe 1.269; MDD -7.62%; ETH contributed heavily, and top three winners contributed 81.2%.

### Windows and exposure

- `train`: 2020-09-15T00:00:00Z, 2025-01-01T00:00:00Z); exposure=`exposed`. Training/search history; repeated legacy use.
- `validation`: [2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z); exposure=`reused_validation`. 2025 reused validation; 2026 values were not numerically read in this audit.

- Sample unit / count: `rule arm` / `12`. Twelve rule arms share data and selection history. NO_BORROW_FAIL training results are not zero.
- Cost and accounting evidence: 5 bp fee per side plus 5 bp slippage; observed funding via prior-hour mark proxy. 100000 USDT segmented wallet, fixed initial slots, no compounding; capacity and margin path absent.
- Audit scope: Existing full account-results report; all twelve arms remain report-linked, no replay.; replayed for this hub: `False`.

## Model inputs / factor definitions

These links record only direct source evidence; absence of a known link is not filled from the experiment name. `binding_scope` distinguishes frozen columns from a named input family.

- Factor `sixfactor-trend-ema-macd-bollinger-family`: Older code and its account report define six rule families, each at 4h and 1d: EMA200, EMA20_60, MACD(hist>0), MACD_EMA200, shifted DONCHIAN55_20, and BB120_EMA200_ATR3. Indicators include EMA20/60/200, MACD(12,26,9), BB120 +/-2 std, ATR14; do not conflate this catalog with Core3 benchmarks. Evidence: [`longcycle_signal_cases_luna_v1.py` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/trend_or_2026_v1/audit_snapshots/pre_pipeline_snapshot_20261004_v1/files/scripts/longcycle_signal_cases_luna_v1.py%3E`), `ACCOUNT_RESULTS_V3_20261003.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/longcycle_trend_catalog_v1/ACCOUNT_RESULTS_V3_20261003.md%3E`), `SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/sixfactor_longcycle_v1/SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md%3E`). Factor card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_sixfactor_trend_family.md%3E`).

### Related evidence only (not asserted as consumed input)

- None recorded.

### Explicit unknowns and next evidence

- No additional model input unknown is recorded in the bounded sources reviewed; this is not a claim of complete verification.

## Target label and maturity

Deterministic rule catalog, not a supervised prediction label.

No label factor card assigned in the bounded evidence pass.

## Study-specific bounded notes

No extra sub-study note was added in this bounded docs-only pass.

## Source references

- `ACCOUNT_RESULTS_V3_20261003.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/longcycle_trend_catalog_v1/ACCOUNT_RESULTS_V3_20261003.md%3E`) — `READ_SUMMARY_OR_METADATA`; Twelve rule account-result summary and shared assumptions.

## Related primary records

- `core3-trend-risk-v1` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/%3Ccore3-trend-risk-v1.md%3E`)

- Unchanged registry record (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/experiment_registry.json%3E`); the registry's `relative_path` base is `research_hub/`.
- EXPLORATORY_UNVERIFIED is the historical registry status; this card does not promote its evidence.

See the DRAFT session workflow (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/SESSION_WORKFLOW_DRAFT.md%3E`) and machine map (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/research_map.json%3E`).
