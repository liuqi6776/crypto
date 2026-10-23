> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Minute-return prediction and dynamic strategy

**Primary historical record:** `minute-return-2026`. This is the single main card for this registry ID; cross-links are navigation only.

- Category: `mixed`; registry version pin: `static minute_return_2026_v1; dynamic minute_return_dynamic_2026_v1`.
- Market / symbols / timeframe: `perpetual` / `see source reports` / `minute`.
- Registry verdict: `EXPLORATORY_UNVERIFIED`; recommendation: `pause_current_version`.
- Primary directory: `strategy_models`; linked factors with direct evidence: `minute-return-2026-price-flow-v1`.

## Evidence and bounded conclusion

pause_current_version

### Registry result rows (historical text retained)

- **Fixed-exit cumulative net PnL**: `-752.75` account_simulation_cumulative_usdt; population `Jan-Aug 2026; 393 trades; reset-fold arithmetic cumulative account simulation`. Observed result; funding cash accounting missing.
- **Dynamic cumulative net PnL**: `-783.06` account_simulation_cumulative_usdt; population `Jan-Aug 2026; 413 trades; reset-fold arithmetic cumulative account simulation`. Observed result; eight negative months; funding cash accounting missing.
- **Fixed-exit trade count**: `393` trade_count; population `Jan-Aug 2026 fixed-exit simulation ledger`. Count is separate from the dynamic ledger.
- **Dynamic trade count**: `413` trade_count; population `Jan-Aug 2026 dynamic simulation ledger`. Count is separate from the fixed-exit ledger.
- **Stable predictive increment**: `not found` descriptive_text; population `static study`. Reported no stable predictive increment.

### Windows and exposure

- `evaluation`: 2026-01-01T00:00:00Z, 2026-09-01T00:00:00Z); exposure=`exposed`. Jan-Aug fixed-window results have been examined.

- Sample unit / count: `separate reset-fold simulation ledger` / `None`. Fixed and dynamic results come from different simulated ledgers/windows; cumulative totals are not daily observations or independent samples. Eight negative months; no stable predictive increment.
- Cost and accounting evidence: Primary 0.05% fee and 0.05% slippage each side; observed funding cash accounting missing.
- Audit scope: Existing results and review summaries; no replay.; replayed for this hub: `False`.

## Model inputs / factor definitions

These links record only direct source evidence; absence of a known link is not filled from the experiment name. `binding_scope` distinguishes frozen columns from a named input family.

- Factor `minute-return-2026-price-flow-v1`: Frozen protocol and builder bind P=18 named price/volume/count features and F=P+7 named flow features; HistGB uses the P arm for saved predictions. Ridge alpha=10 with StandardScaler; HistGB has 100 iterations, depth 3, learning rate .05, L2=1, no early stopping, random_state=20261004. Train stride 5 and evaluation stride 1. Evidence: [`protocol.py` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/tools/perptools/minute_return_2026_v1/protocol.py%3E`), `features.py` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/tools/perptools/minute_return_2026_v1/features.py%3E`), `experiment.py` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/tools/perptools/minute_return_2026_v1/experiment.py%3E`). Factor card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_minute_return_2026_price_flow.md%3E`).

### Related evidence only (not asserted as consumed input)

- Related evidence only (`minute-return-2026-price-flow-v1`): The dynamic-policy protocol reuses the P-arm saved predictions.npz/index rather than retraining; four policies compare original/frequency-cutoff crossed with fixed/dynamic sizing. Definition card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_minute_return_2026_price_flow.md%3E`). Evidence: `protocol.py` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/tools/perptools/minute_return_dynamic_2026_v1/protocol.py%3E`), `bars.py` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/tools/perptools/minute_return_dynamic_2026_v1/bars.py%3E`)

### Explicit unknowns and next evidence

- **raw source lineage and point-in-time publication latency for each feature input — UNKNOWN.** Protocol and feature builder establish derived column names and decision indexing, but not all upstream exchange publication clocks. Check: `Bound source manifest and per-source timestamp metadata for the frozen minute-return snapshot.`.
- **historical validation exposure beyond the documented folds — UNKNOWN.** The report uses expanding folds and multiple 2026 evaluation periods; no untouched future holdout is asserted. Check: `The cited result report and run manifest for each snapshot.`.

## Target label and maturity

Label=(open[t+2m+h]/open[t+2m])-1 for h={5,15,30}; three expanding folds start at 2022, calibrate on the prior quarter and evaluate 2026Q1, Q2, and partial Q3 (July-August). MSE comparison F versus P uses Holm correction over six comparisons and did not show stable significant improvement. Dynamic policy comparison reuses P-arm saved predictions without retraining.

Label definition cards: `minute-return-2026-forward-open-return-label-v1` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_minute_return_2026_forward_open_label.md%3E`)

## Study-specific bounded notes

No extra sub-study note was added in this bounded docs-only pass.

## Source references

- `EMPIRICAL_RESULTS_CN_minute_return_2026_v1_20261004.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/minute_return_2026_v1/EMPIRICAL_RESULTS_CN_minute_return_2026_v1_20261004.md%3E`) — `READ_SUMMARY_OR_METADATA`; Static minute-return results.
- `CODEX_REVIEW_20261004.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/minute_return_dynamic_2026_v1/CODEX_REVIEW_20261004.md%3E`) — `READ_SUMMARY_OR_METADATA`; Dynamic strategy review.

## Related primary records

- None recorded.

- Unchanged registry record (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/experiment_registry.json%3E`); the registry's `relative_path` base is `research_hub/`.
- EXPLORATORY_UNVERIFIED is the historical registry status; this card does not promote its evidence.

See the DRAFT session workflow (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/SESSION_WORKFLOW_DRAFT.md%3E`) and machine map (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/research_map.json%3E`).
