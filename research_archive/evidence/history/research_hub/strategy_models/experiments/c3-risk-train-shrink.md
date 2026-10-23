> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# C3 risk-training position shrink

**Primary historical record:** `c3-risk-train-shrink`. This is the single main card for this registry ID; cross-links are navigation only.

- Category: `strategy`; registry version pin: `AUDITED V1R3`.
- Market / symbols / timeframe: `perpetual` / `BTC, ETH` / `1h`.
- Registry verdict: `EXPLORATORY_UNVERIFIED`; recommendation: `retain_hypothesis`.
- Primary directory: `strategy_models`; linked factors with direct evidence: `atr14-stop-distance`.

## Evidence and bounded conclusion

retain_hypothesis

### Registry result rows (historical text retained)

- **E0 FIT return**: `2.91` account_return_percent; population `E0 FIT: 34 trades`. FIT has 34 trades; CAL has 10.
- **E0 CAL return**: `-1.952` account_return_percent; population `E0 CAL: 10 trades`. Reported account result.
- **New stop scaled MAE FIT / CAL**: `+0.781 / -0.450` account_return_percent; population `reported risk-shrink result`. Downside FIT/CAL +0.984/-0.463%; not evidence of alpha.

### Windows and exposure

- `train`: 2021-01-01T00:00:00Z, 2022-07-01T00:00:00Z); exposure=`exposed`. FIT window.
- `validation`: [2022-07-08T00:00:00Z, 2023-01-01T00:00:00Z); exposure=`exposed`. CAL window, internal exposure.

- Sample unit / count: `account identity` / `16`. Eight arms and 16 account identities; market E0 has 34 FIT trades and 10 CAL trades. 352 ledger rows are not market samples.
- Cost and accounting evidence: 5 bp fee plus 5 bp slippage, funding proxy. Lower exposure substantial; constant controls do not fully match.
- Audit scope: Saved output audit reported PASS for arithmetic only; not a gate pass.; replayed for this hub: `False`.

## Model inputs / factor definitions

- `atr14-stop-distance`: d_stop = 2*ATR14/reference_close; see [ATR stop card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_atr14_stop_distance.md%3E`).
- Phase-A model inputs are explicitly listed in the 13-column schema card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_c3_phase_a_price_features.md%3E`): ATR-relative, prior upper-55 break and EMA50 gap in ATR units; 24/72-bar realized/downside volatility and log-return sums; 24-bar range and close-to-low fractions; candidate and BTC flags. No IV/skew/OI is in this schema. Evidence: descriptor (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/c3_entry_anchored_risk_v1/phase_a_output_v1r2/phase_a_model_descriptors.json%3E`) and frozen Phase-A runner (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/scripts/run_c3_entry_anchored_risk_phase_a_v1r2.py%3E`).

### Explicit unknowns and next evidence

- Actual upstream publication latency for the input series is UNKNOWN. The runner assigns signal close + 1001 ms as the feature-available clock, which is an implementation assumption rather than verified exchange publication evidence. Check source timestamp/publication records before reuse.

## Target label and maturity

Phase-A target heads are raw MAE q90, terminal log-return q10, and binary initial-stop-touch over the 24 consecutive H1 bars from the strictly later entry open. Entry reference is raw entry open × 1.0005; MAE=max(0,(entry_reference-min future low)/entry_reference), terminal target=log(last future close/entry_reference), and stop-touch is min future low <= signal close - 2*ATR14. Label maturity is the 24th future bar close. Gaps, invalid OHLC and immature split tails are not filled/scored. These risk-sizing labels do not establish alpha.

## Study-specific bounded notes

Saved Phase-A estimator recipe from the descriptor: MAE q90 and terminal-return q10 use GradientBoostingRegressor quantile loss (alpha 0.90/0.10, 100 trees, depth 2, min leaf 100, learning rate 0.05, seed 0); stop-touch uses train-only StandardScaler plus LogisticRegression(C=1, lbfgs, max_iter 2000, seed 0).

The refinement run manifest records `phase_a_model_loaded=false`, `model_fit=false`, and `model_predict=false`. Refinement reuses saved Phase-A prediction outputs for arithmetic diagnostics; it did not refit, predict, or establish untouched validation. Evidence: Phase-A descriptor (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/c3_entry_anchored_risk_v1/phase_a_output_v1r2/phase_a_model_descriptors.json%3E`) and refinement run manifest (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/c3_risk_train_refinement_v1/training_output_v1r1/run_manifest.json%3E`).

## Source references

- `C3_RISK_TRAIN_REFINEMENT_REPORT_AUDITED_V1R3.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/docs/C3_RISK_TRAIN_REFINEMENT_REPORT_AUDITED_V1R3.md%3E`) — `READ_SUMMARY_OR_METADATA`; Existing risk training refinement summary.

## Related primary records

- `factor-calibration-causal-2023` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/factor-calibration-causal-2023.md%3E`)

- Unchanged registry record (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/experiment_registry.json%3E`); the registry's `relative_path` base is `research_hub/`.
- EXPLORATORY_UNVERIFIED is the historical registry status; this card does not promote its evidence.

See the DRAFT session workflow (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/SESSION_WORKFLOW_DRAFT.md%3E`) and machine map (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/research_map.json%3E`).
