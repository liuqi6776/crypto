> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Regime, event and meta-account families

**Primary historical record:** `event-meta-2021-23`. This is the single main card for this registry ID; cross-links are navigation only.

- Category: `model`; registry version pin: `round1/round2 and meta_account v5 independent audit`.
- Market / symbols / timeframe: `perpetual` / `multiple; see referenced reports` / `multiple; see referenced reports`.
- Registry verdict: `EXPLORATORY_UNVERIFIED`; recommendation: `pause_current_version`.
- Primary directory: `strategy_models`; linked factors with direct evidence: none established.

## Evidence and bounded conclusion

pause_current_version

### Registry result rows (historical text retained)

- **Regime baseline 2023 return**: `24.53` account_return_percent; population `43 trades`. 2023 baseline account return. Probabilistic route had 3 trades and about 10.4-10.6%; incremental CI crosses zero.
- **Meta CatBoost 135 CAGR**: `6.89` account_cagr_percent; population `2022-23 evaluation`. Below E0 reported 17.09%; its primary cost ledger was structurally reconciled. E4_unfiltered financing failure blocks complete incremental comparison.
- **Meta Ridge 123 CAGR**: `7.23` account_cagr_percent; population `2022-23 evaluation`. Below E0 reported 17.09%; its primary cost ledger was structurally reconciled. E4_unfiltered financing failure blocks complete incremental comparison.
- **Event round trades**: `461` trade_count; population `2021-23 event family`. 2022 negative.

### Windows and exposure

- `train`: 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z); exposure=`exposed`. Meta family training window.
- `evaluation`: [2022-01-01T00:00:00Z, 2024-01-01T00:00:00Z); exposure=`exposed`. 2022-23 exposed evaluation; multiple family results.

- Sample unit / count: `trade/case/account depending on cited sub-study` / `461`. Event round reports 461 trades; regime route has only 3 trades; counts across families are not pooled independent samples.
- Cost and accounting evidence: Meta CatBoost 135 and Ridge 123 primary cost ledgers were structurally reconciled with 5 bp fee plus 5 bp slippage each side and observed funding proxy. Financing failures are specific to E4_unfiltered primary/stress; they block the complete incremental comparison, not those two model ledgers. Sub-study units differ.
- Audit scope: Existing review documents; 10/12 ledgers pass, two financing failures; structural review only.; replayed for this hub: `False`.

## Model inputs / factor definitions

The fixed 2021 `meta_fit2021_v2` model has an artifact-verified 24-column schema: own/BTC/relative returns at 1h/4h/24h/168h; own and BTC EMA50 slope, ER24 and ATR14 fraction at 4h; reference stop gap, max-entry gap, setup age hours, own funding rate/age, and `is_H2`. H1/H2 share a model. BTC-state tags are descriptive metadata only. See the [fixed-schema card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_event_meta_fixed24_features_v2.md%3E`) and fit_results_v2 (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/regime_event_round2_20260930/meta_fit2021_v2/fit_results_v2.json%3E`).

The registry also groups deterministic round1 regime routes and round2 event-family account comparisons; the fixed 24-column schema is not assigned to those arms. The readable v5 event-feature artifact carries a similar schema and source clocks, but by itself does not prove every field was consumed by every sub-study.

### Explicit unknowns and next evidence

- Exact input/threshold binding for each round1 route and non-meta round2 event-rule arm remains UNKNOWN; inspect each arm-specific frozen contract separately instead of generalizing this meta schema.
- Real external feature publication latency remains UNKNOWN even where artifact availability clocks are recorded; verify at source level before reuse.

## Study-specific bounded notes

Fixed fit_results_v2 records split-train n=149 and validation n=139 after overlap purge. A separate full-2021 refit uses n=300 and explicitly sets `full_2021_refit_is_not_validation_evidence=true`. Decision passes predicted net_R >= 0.1, maps below threshold to CASH, and maps missing/nonfinite features or prediction to ABSTAIN. The 300-row refit is not OOS evidence. The target is counterfactual shadow net_R, mature at native natural exit +1s; 2022-23 evaluation is exposed. This does not describe the separate round1 route arms.

Evidence: `fit_results_v2.json` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/regime_event_round2_20260930/meta_fit2021_v2/fit_results_v2.json%3E`).

## Source references

- `README_CN.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/README_CN.md%3E`) — `READ_SUMMARY_OR_METADATA`; Regime round 1 conclusion.
- `ROOT_REVIEW_CN_v2_WITH_ALPHA.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/regime_event_round2_20260930/evaluation2023_v1/ROOT_REVIEW_CN_v2_WITH_ALPHA.md%3E`) — `READ_SUMMARY_OR_METADATA`; Event round 2 review.
- `README_AUDIT_RESULTS_CN_v1.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/regime_event_round2_20260930/meta_account_2022_2023_v5_independent_audit_v1/README_AUDIT_RESULTS_CN_v1.md%3E`) — `READ_SUMMARY_OR_METADATA`; Meta-account audit and financing blockers.

## Related primary records

- `factor-calibration-causal-2023` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/factor-calibration-causal-2023.md%3E`)

- Unchanged registry record (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/experiment_registry.json%3E`); the registry's `relative_path` base is `research_hub/`.
- EXPLORATORY_UNVERIFIED is the historical registry status; this card does not promote its evidence.

See the DRAFT session workflow (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/SESSION_WORKFLOW_DRAFT.md%3E`) and machine map (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/research_map.json%3E`).
