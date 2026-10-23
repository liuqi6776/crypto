> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Source MA/ML legacy

**Primary historical record:** `source-ma-ml-legacy`. This is the single main card for this registry ID; cross-links are navigation only.

- Category: `model`; registry version pin: `legacy summary and provenance records`.
- Market / symbols / timeframe: `mixed_reference` / `spot source universe` / `multiple`.
- Registry verdict: `LEGACY_RESEARCH`; recommendation: `retain_benchmark`.
- Primary directory: `strategy_models`; linked factors with direct evidence: `neighbor-ml-microstructure-24d-v1`.

## Evidence and bounded conclusion

retain_benchmark

### Registry result rows (historical text retained)

- **XGB selected result**: `0.095` r_multiple; population `7199 evaluation events; 16 selected`. Reported +0.095R; gate FAILED.

### Windows and exposure

- `evaluation`: None, None); exposure=`exposed`. Exact evaluation window not extracted from cited MA/ML summary.

- Sample unit / count: `evaluation event` / `7199`. Selected events/models are not independent samples; source summary does not establish exact UTC bounds.
- Cost and accounting evidence: Legacy MA/ML result; account/transaction costs are not established by this summary.
- Audit scope: Existing source reports and provenance docs; spot reference separated from perpetual claims.; replayed for this hub: `False`.

## Model inputs / factor definitions

These links record only direct source evidence; absence of a known link is not filled from the experiment name. `binding_scope` distinguishes frozen columns from a named input family.

- Factor `neighbor-ml-microstructure-24d-v1`: The source feature constant exposes all 24 names listed on its factor card, and the study runner imports the matching congestion dataset, purged CV and model modules. The report records close-time features/T+1-open execution, synchronized four-symbol five-fold evaluation and fixed/LR/XGBoost families. Saved-run-to-current-code identity remains UNKNOWN; this is adjacent spot research, not a perp contract. Evidence: [`models.py` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/crypto_quant/ml/models.py%3E`), `run_ma_ml_study.py` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/scripts/run_ma_ml_study.py%3E`), `congestion_dataset.py` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/crypto_quant/ml/congestion_dataset.py%3E`), `purged_cv.py` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/crypto_quant/ml/purged_cv.py%3E`), `ML_RESEARCH_SUMMARY.md` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/reports/ma_ml/ML_RESEARCH_SUMMARY.md%3E`). Factor card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_neighbor_ml_microstructure_24d.md%3E`).

### Related evidence only (not asserted as consumed input)

- None recorded.

### Explicit unknowns and next evidence

- **saved-run binding to the currently readable 24-column constant and exact fold-specific preprocessing — UNKNOWN.** Runner imports the defining modules, but a full saved-run code/config pin was not established. Check: `Original run manifest and fold-specific model descriptor.`.
- **real observed funding settlement series in historical short-side account costs — UNKNOWN.** The adjacent code hardcodes funding_drag=0.0001 and does not consume the passed funding_series; this is not an observed settlement ledger. Check: `A verified per-run settlement-event input and account ledger, if one exists.`.

## Target label and maturity

Code-level action construction uses T+1 open with slippage, minimum risk distance 0.5% of entry, 2R take-profit, at most 12 bars, and stop-first ordering. A direction is BUY/SELL when return reaches at least 0.3R; otherwise FLAT. Long side reports spot 8bp; short side reports futures 5bp plus a hardcoded 0.0001 funding drag. The hardcoded drag is not observed funding. Saved-run binding is not fully confirmed.

No label factor card assigned in the bounded evidence pass.

## Study-specific bounded notes

No extra sub-study note was added in this bounded docs-only pass.

## Source references

- `ML_RESEARCH_SUMMARY.md` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/reports/ma_ml/ML_RESEARCH_SUMMARY.md%3E`) — `READ_SUMMARY_OR_METADATA`; Legacy ML summary.

## Related primary records

- None recorded.

- Unchanged registry record (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/experiment_registry.json%3E`); the registry's `relative_path` base is `research_hub/`.
- LEGACY_RESEARCH is the historical registry status; this card does not promote its evidence.

See the DRAFT session workflow (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/SESSION_WORKFLOW_DRAFT.md%3E`) and machine map (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/research_map.json%3E`).
