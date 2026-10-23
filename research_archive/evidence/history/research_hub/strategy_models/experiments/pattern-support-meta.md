> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Pattern, execution-horizon, support-rebound and meta candidates

**Primary historical record:** `pattern-support-meta`. This is the single main card for this registry ID; cross-links are navigation only.

- Category: `mixed`; registry version pin: `round2/round3 and 2025 development summaries`.
- Market / symbols / timeframe: `perpetual` / `ETH, four coin family; see reports` / `multiple`.
- Registry verdict: `EXPLORATORY_UNVERIFIED`; recommendation: `pause_current_version`.
- Primary directory: `strategy_models`; linked factors with direct evidence: `support-catboost-dev25-v4-feature-sets`.

## Evidence and bounded conclusion

pause_current_version

### Registry result rows (historical text retained)

- **Pattern combined net bounds**: `negative` descriptive_text; population `24 cases / 18257 closed trades`. 2022-25 exposed.
- **Support rebound mean per-coin compound**: `0.29` account_return_percent; population `89 trades in 2025`. Rule result; exposed development year.
- **CatBoost meta F0/F1/F2**: `all negative` descriptive_text; population `four coins, 2025`. Development validation report.

### Windows and exposure

- `evaluation`: 2022-01-01T00:00:00Z, 2026-01-01T00:00:00Z); exposure=`exposed`. 2022-25 reused/exposed across reported cases.

- Sample unit / count: `case, closed trade, or fixed candidate by sub-study` / `18257`. Pattern family: 24 cases/18257 closed trades; horizon family: 405 candidates, ETH passive 17 small positive but stress-negative; support: 89 trades; candidate counts are not independent samples.
- Cost and accounting evidence: Pattern combined net bounds negative. Horizon small passive positives fail stress. Results are sub-study-specific, do not pool metrics.
- Audit scope: Existing family review reports; no replay.; replayed for this hub: `False`.

## Model inputs / factor definitions

These links record only direct source evidence; absence of a known link is not filled from the experiment name. `binding_scope` distinguishes frozen columns from a named input family.

- Factor `support-catboost-dev25-v4-feature-sets`: For the 2025 CatBoost support/meta sub-study, protocol v4 records the saved F0/F1/F2 feature order and trained-model feature-name check. F0/F1/F2 are distinct whitelists; only F2 adds observed-funding rate/age/summary features. Frozen models were trained on 2024 only and evaluated without refit or threshold tuning in previously exposed 2025 development data. Evidence: [`protocol_dev_2025_v4.json` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/support_rebound_mtf/catboost_meta_dev_2025_v4/protocol_dev_2025_v4.json%3E`), `run_support_rebound_catboost_meta_dev_2025_v4.py` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/scripts/run_support_rebound_catboost_meta_dev_2025_v4.py%3E`), `dev25_v4_manifest.json` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/support_rebound_mtf/catboost_meta_dev_2025_v4/dev25_v4_manifest.json%3E`). Factor card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_support_catboost_dev25_v4_feature_sets.md%3E`).

### Related evidence only (not asserted as consumed input)

- Related evidence only (`sixfactor-support-event-family`): A support/event family is directly described in the six-factor evidence and a support-rebound family is present in this registry cluster; exact per-substudy input/label alignment is still UNKNOWN. Definition card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_support_event_family.md%3E`). Evidence: `SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/sixfactor_longcycle_v1/SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md%3E`)

### Explicit unknowns and next evidence

- **feature/label bindings for the 24-case pattern and 405-candidate execution-horizon sub-studies — UNKNOWN.** The primary registry item groups different families. Reviewed summaries establish exposure and outcomes but do not supply frozen per-case feature and target manifests. Check: `Each sub-study's own pinned protocol and model/runner descriptor; do not transfer the support CatBoost schema to these studies.`.
- **exact support-rule implementation columns and CatBoost event-label arithmetic — UNKNOWN.** The support report/protocol exposes the frozen CatBoost feature order and exit treatment, but the full candidate label arithmetic and every state-machine source definition are not established in this bounded card. Check: `The bound Stage-A v3 and Stage-C v2 protocol/runner source, plus dev25-v4 target-generation code.`.

## Target label and maturity

UNKNOWN for this study/registry cluster; check the linked protocol/config separately for each sub-study. This card does not infer a target from its name.

No label factor card assigned in the bounded evidence pass.

## Study-specific bounded notes

No extra sub-study note was added in this bounded docs-only pass.

## Source references

- `codex_final_review.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/pattern_comparison_round2_20261009/codex_final_review.md%3E`) — `READ_SUMMARY_OR_METADATA`; Pattern family review.
- `codex_final_review_zh.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/b_execution_horizon_round3_20261009/codex_final_review_zh.md%3E`) — `READ_SUMMARY_OR_METADATA`; Execution horizon review.
- `STAGE_C_DEV_VALIDATION_REPORT_V2.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/support_rebound_mtf/STAGE_C_DEV_VALIDATION_REPORT_V2.md%3E`) — `READ_SUMMARY_OR_METADATA`; Support rebound validation report.
- `dev25_validation_report.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/support_rebound_mtf/catboost_meta_dev_2025_v4/dev25_validation_report.md%3E`) — `READ_SUMMARY_OR_METADATA`; Four-coin meta model report.

## Related primary records

- None recorded.

- Unchanged registry record (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/experiment_registry.json%3E`); the registry's `relative_path` base is `research_hub/`.
- EXPLORATORY_UNVERIFIED is the historical registry status; this card does not promote its evidence.

See the DRAFT session workflow (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/SESSION_WORKFLOW_DRAFT.md%3E`) and machine map (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/research_map.json%3E`).
