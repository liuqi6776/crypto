> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Ridge 1h/24 risk prediction arithmetic audit

**Primary historical record:** `ridge-1h24-risk-2021`. This is the single main card for this registry ID; cross-links are navigation only.

- Category: `model`; registry version pin: `V1R2; derived_arithmetic_audit_v1r3`.
- Market / symbols / timeframe: `perpetual` / `BTC, ETH, SOL, BNB` / `1h prediction, 24h target`.
- Registry verdict: `EXPLORATORY_UNVERIFIED`; recommendation: `priority_validation`.
- Primary directory: `strategy_models`; linked factors with direct evidence: `core4-ridge-1h24-feature-schema-v1`.

## Evidence and bounded conclusion

priority_validation

### Registry result rows (historical text retained)

- **Pooled MSE improvement versus EWMA**: `13.7937` prediction_metric; population `4228 scored overlapping origins`. BTC did not improve; 75 arithmetic checks.

### Windows and exposure

- `train`: 2021-01-01T00:00:00Z, 2021-07-01T00:00:00Z); exposure=`exposed`. 7-day embargo before validation.
- `validation`: [2021-07-08T00:00:00Z, 2022-01-01T00:00:00Z); exposure=`exposed`. Historical validation; no position PnL evidence.

- Sample unit / count: `overlapping forecast origin` / `4228`. 4248 prediction rows, 4228 scored; forecast origins overlap and are dependent.
- Cost and accounting evidence: Prediction-only arithmetic audit; no position sizing, funding account cashflows, or PnL evidence.
- Audit scope: Derived-only; no refit and no raw data read.; replayed for this hub: `False`.

## Model inputs / factor definitions

These links record only direct source evidence; absence of a known link is not filled from the experiment name. `binding_scope` distinguishes frozen columns from a named input family.

- Factor `core4-ridge-1h24-feature-schema-v1`: The run-manifest-bound training-only descriptor names the independent nine-column Core4 Ridge schema; lambda=10, 4,324 training rows (1,081 each for BTC/ETH/SOL/BNB), train-only mean/scale, geometric exp(log forecast) with no clipping/smearing. Evidence: [`model_descriptors_train_only.json` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/trend_vol_1h_risk2021_v1/model_descriptors_train_only.json%3E`), `run_manifest.json` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/trend_vol_1h_risk2021_v1/run_manifest.json%3E`). Factor card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_core4_ridge_1h24_features.md%3E`).

### Related evidence only (not asserted as consumed input)

- None recorded.

### Explicit unknowns and next evidence

- **per-feature upstream publication timing — UNKNOWN.** Descriptor enumerates the feature columns and train-only scaler but does not establish real exchange publish timestamps. Check: `source timestamp/publication evidence for each source series in the run manifest.`.

## Target label and maturity

Known label from its own Core4 contract: V_1h24 = mean of the next 24 completed H1 close log returns squared, non-annualized; label becomes mature only after all 24 future H1 bars are observed. This is a target, not a feature. Its independent nine-column Core4 input schema is enumerated above and does not inherit Core3's schema.

Label definition cards: `forward-realized-variance-1h24-label` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_forward_realized_variance_1h24.md%3E`)

## Study-specific bounded notes

No extra sub-study note was added in this bounded docs-only pass.

## Source references

- `derived_arithmetic_audit_v1r3.json` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/trend_vol_1h_risk2021_v1/derived_arithmetic_audit_v1r3.json%3E`) — `READ_LIMITED_ARTIFACT`; Derived arithmetic checks and metrics.
- `core_run_contract.json` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/trend_vol_1h_risk2021_v1/core_run_contract.json%3E`) — `READ_LIMITED_ARTIFACT`; Run contract and declared windows.

## Related primary records

- `factor-calibration-causal-2023` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/factor-calibration-causal-2023.md%3E`)

- Unchanged registry record (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/experiment_registry.json%3E`); the registry's `relative_path` base is `research_hub/`.
- EXPLORATORY_UNVERIFIED is the historical registry status; this card does not promote its evidence.

See the DRAFT session workflow (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/SESSION_WORKFLOW_DRAFT.md%3E`) and machine map (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/research_map.json%3E`).
