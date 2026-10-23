> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Channel ML R4 resume, selected CatBoost D6/I500

**Primary historical record:** `channel-ml-maker-2024-25`. This is the single main card for this registry ID; cross-links are navigation only.

- Category: `model`; registry version pin: `R4 resume; selected_catboost_d6_i500_20261008T132354Z`.
- Market / symbols / timeframe: `perpetual` / `ETH, SOL` / `multiple / action rows`.
- Registry verdict: `EXPLORATORY_UNVERIFIED`; recommendation: `pause_current_version`.
- Primary directory: `strategy_models`; linked factors with direct evidence: `channel-ml-d6i500-feature-set`.

## Evidence and bounded conclusion

pause_current_version

### Registry result rows (historical text retained)

- **R4 action rows**: `397205` prediction_row_count; population `selected CatBoost D6/I500 run`. No eligible positive in 2023 selection; exposed 2024/25 base and stress all negative.

### Windows and exposure

- `train`: 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z); exposure=`exposed`. R4 training.
- `validation`: [2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z); exposure=`reused_validation`. Selection year had no eligible positive result.
- `evaluation`: [2024-01-01T00:00:00Z, 2026-01-01T00:00:00Z); exposure=`exposed`. 2024/25 are exposed evaluation windows; selection occurred in 2023, not in these evaluation years.

- Sample unit / count: `action row in selected CatBoost run` / `397205`. 397205 action rows are not independent account samples. 2023 selection had no eligible positive; 2024/25 are exposed evaluation, not stated as selection windows.
- Cost and accounting evidence: Base and stress results reported negative for exposed ETH/SOL windows; inspect cited reports for variant details. Candidate row counts do not indicate performance.
- Audit scope: Existing selected run summary and completion artifact; no replay.; replayed for this hub: `False`.

## Model inputs / factor definitions

These links record only direct source evidence; absence of a known link is not filled from the experiment name. `binding_scope` distinguishes frozen columns from a named input family.

- Factor `channel-ml-d6i500-feature-set`: The selected CatBoost descriptor lists 29 named feature columns and importance weights; names are known but several definitions/formulas/availability fields need the frozen feature/code manifest. Evidence: [`model_feature_and_action_summary_20261008T132354Z.json` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/channel_ml_validation_resume_v1/model_feature_and_action_summary_20261008T132354Z.json%3E`). Factor card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_channel_ml_d6i500_features.md%3E`).

### Related evidence only (not asserted as consumed input)

- None recorded.

### Explicit unknowns and next evidence

- **exact supervised action-label formula and per-feature transforms/availability — UNKNOWN.** The report gives hourly action-label sampling and selected feature names/importance, but not the complete label-generation or every source-column formula. Check: `linked frozen R4 feature and label-generation code/config manifest.`.

## Target label and maturity

The selected descriptor samples hourly action labels; exact action-label generation formula remains UNKNOWN. Purpose is descriptive only and does not validate profit-based selection.

No label factor card assigned in the bounded evidence pass.

## Study-specific bounded notes

The selected descriptor exposes 29 named features. Its purpose is `descriptive_only_no_validation_profit_based_selection`; 513 actual base fills include an unknown-execution ledger, and stress fills are excluded. This is not new validation or selection.

## Source references

- `selected_catboost_d6_i500_20261008T132354Z.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/channel_ml_validation_resume_v1/selected_catboost_d6_i500_20261008T132354Z.md%3E`) — `READ_SUMMARY_OR_METADATA`; Selected channel ML run.

## Related primary records

- None recorded.

- Unchanged registry record (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/experiment_registry.json%3E`); the registry's `relative_path` base is `research_hub/`.
- EXPLORATORY_UNVERIFIED is the historical registry status; this card does not promote its evidence.

See the DRAFT session workflow (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/SESSION_WORKFLOW_DRAFT.md%3E`) and machine map (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/research_map.json%3E`).
