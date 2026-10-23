> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# BTC minute-probability model

**Primary historical record:** `btc-minute-probability-2023`. This is the single main card for this registry ID; cross-links are navigation only.

- Category: `model`; registry version pin: `run_20261007_v3`.
- Market / symbols / timeframe: `perpetual` / `BTC` / `minute, 15m score`.
- Registry verdict: `EXPLORATORY_UNVERIFIED`; recommendation: `retain_benchmark`.
- Primary directory: `strategy_models`; linked factors with direct evidence: `btc-minute-multihorizon-ohlcv-features-v1`.

## Evidence and bounded conclusion

retain_benchmark

### Registry result rows (historical text retained)

- **15m accuracy**: `53` prediction_metric; population `approximately 525k overlapping scores`. Classification accuracy is not trading return.
- **Base trades**: `71` trade_count; population `2023 base`. Negative base result.

### Windows and exposure

- `evaluation`: 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z); exposure=`exposed`. Single historical year.

- Sample unit / count: `overlapping prediction score` / `525000`. About 525k overlapping scores do not represent independent samples; trade count is 71.
- Cost and accounting evidence: Base trading result negative; detailed costs in referenced result artifact.
- Audit scope: Existing Chinese-language results report; no replay.; replayed for this hub: `False`.

## Model inputs / factor definitions

These links record only direct source evidence; absence of a known link is not filled from the experiment name. `binding_scope` distinguishes frozen columns from a named input family.

- Factor `btc-minute-multihorizon-ohlcv-features-v1`: Frozen config enumerates 23 causal OHLCV lag/volatility/range/trend/volume features with completed 5m/15m/60m aggregates as-of joined only after completion. Evidence: [`RESULTS_中文.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/btc_minute_probability_v1/run_20261007_v3/RESULTS_%E4%B8%AD%E6%96%87.md%3E`). Factor card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_btc_minute_ohlcv_feature_set.md%3E`).

### Related evidence only (not asserted as consumed input)

- None recorded.

### Explicit unknowns and next evidence

- **feature generation implementation hash/code equivalence — UNKNOWN.** Config describes the schema and availability policy; this doc pass does not verify every feature implementation against source code. Check: `artifact_manifest.json plus frozen feature-engine source/code pins.`.

## Target label and maturity

Five direction horizons, exact-equality FLAT class, separate Ridge return head, and label-availability/purge rule are defined in frozen config.

Label definition cards: `btc-minute-direction-and-return-labels-v1` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_btc_minute_labels.md%3E`)

## Study-specific bounded notes

No extra sub-study note was added in this bounded docs-only pass.

## Source references

- `RESULTS_中文.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/btc_minute_probability_v1/run_20261007_v3/RESULTS_%E4%B8%AD%E6%96%87.md%3E`) — `READ_SUMMARY_OR_METADATA`; Existing run result summary.

## Related primary records

- None recorded.

- Unchanged registry record (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/experiment_registry.json%3E`); the registry's `relative_path` base is `research_hub/`.
- EXPLORATORY_UNVERIFIED is the historical registry status; this card does not promote its evidence.

See the DRAFT session workflow (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/SESSION_WORKFLOW_DRAFT.md%3E`) and machine map (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/research_map.json%3E`).
