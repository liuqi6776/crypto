> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Source legacy Transformer/STChan models

**Primary historical record:** `source-transformer-stchan-legacy`. This is the single main card for this registry ID; cross-links are navigation only.

- Category: `model`; registry version pin: `legacy Transformer/STChan; 2024/25 selection and 2026 post-hoc changes (exact artifact dates not extracted)`.
- Market / symbols / timeframe: `spot` / `source-repository studies; exact universe not extracted` / `unknown`.
- Registry verdict: `LEGACY_RESEARCH`; recommendation: `retain_benchmark`.
- Primary directory: `strategy_models`; linked factors with direct evidence: none established.

## Evidence and bounded conclusion

retain_benchmark

### Registry result rows (historical text retained)

- **Stable incremental value**: `not established` descriptive_text; population `legacy Transformer/STChan reports`. Existing provenance/incremental-value docs show no stable increment.

### Windows and exposure

- `validation`: None, None); exposure=`reused_validation`. 2024/25 history was used for selection; exact UTC boundaries not extracted.
- `evaluation`: [None, None); exposure=`exposed`. Changes were made post hoc in 2026; exact UTC boundaries not extracted.

- Sample unit / count: `model evaluation event; exact count not extracted` / `None`. Legacy model evidence; no independent sample count established.
- Cost and accounting evidence: No verified account-level cost or trading result is asserted for the legacy Transformer/STChan artifacts.
- Audit scope: Existing model provenance and incremental-value summaries; no replay.; replayed for this hub: `False`.

## Model inputs / factor definitions

These links record only direct source evidence; absence of a known link is not filled from the experiment name. `binding_scope` distinguishes frozen columns from a named input family.

- No direct factor input relation established for this record.

### Related evidence only (not asserted as consumed input)

- Related evidence only (`neighbor-token-feature-code-family-v1`): Current adjacent-source dataset_builder code defines these candidate token feature families and transforms; model_provenance names generating scripts and train/validation periods. This is not proof of a specific legacy checkpoint's actual consumed columns. [Definition card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_neighbor_token_feature_code_family.md%3E`). Evidence: `dataset_builder.py` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/crypto_quant/dataset_builder.py%3E`), `model_provenance.json` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/docs/model_provenance.json%3E`), `train_transformer.py` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/crypto_quant/train_transformer.py%3E`), `train_chan_transformer.py` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/scripts/train_chan_transformer.py%3E`)

### Explicit unknowns and next evidence

- **checkpoint-specific actual input columns, exact preprocessing binding and warm-start provenance — UNKNOWN.** The source builder is readable, but best_crypto(_augmented) has no verified generator binding and the model provenance flags warm-start risk; truncated sha256_16 values are not full content hashes. Check: `A full checkpoint-bound manifest or reproducible training artifact with complete SHA256.`.
- **untouched holdout exposure — UNKNOWN.** Validation 2024-2025 was used for selection, with 2026 observations followed by rule changes; it is not untouched holdout evidence. Check: `Complete dated selection log and checkpoint provenance.`.

## Target label and maturity

Current builder code defines L=12 and 4h/8h log-return labels for crypto datasets. Channel-wave labels are 3/6/12 days (18/36/72 bars), with 12-day expansion >3%, 72-bar purge and 18-bar embargo. These are code-level candidate protocols, not checkpoint-bound confirmed targets. Provenance names crypto_quant/train_transformer.py and scripts/train_chan_transformer.py; train period is 2020-08 through 2023, while 2024-2025 validation was used for selection and 2026 observations were followed by rule changes.

No label factor card assigned in the bounded evidence pass.

## Study-specific bounded notes

No extra sub-study note was added in this bounded docs-only pass.

## Source references

- `model_provenance.json` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/docs/model_provenance.json%3E`) — `READ_SUMMARY_OR_METADATA`; Legacy Transformer/STChan provenance; 2024/25 selection and post-hoc 2026 changes summarized from existing audit.
- `model_incremental_value.json` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/docs/model_incremental_value.json%3E`) — `READ_SUMMARY_OR_METADATA`; Legacy incremental-value summary; no stable increment reported.

## Related primary records

- None recorded.

- Unchanged registry record (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/experiment_registry.json%3E`); the registry's `relative_path` base is `research_hub/`.
- LEGACY_RESEARCH is the historical registry status; this card does not promote its evidence.

See the DRAFT session workflow (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/SESSION_WORKFLOW_DRAFT.md%3E`) and machine map (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/research_map.json%3E`).
