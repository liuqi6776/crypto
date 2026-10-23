> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# C3/X3 volatility overlay

**Primary historical record:** `c3-x3-overlay-2023`. This is the single main card for this registry ID; cross-links are navigation only.

- Category: `strategy`; registry version pin: `V1R3 gate report; 2023 overlay`.
- Market / symbols / timeframe: `perpetual` / `BTC, ETH` / `unknown from limited summary`.
- Registry verdict: `EXPLORATORY_UNVERIFIED`; recommendation: `retain_hypothesis`.
- Primary directory: `strategy_models`; linked factors with direct evidence: none established.

## Evidence and bounded conclusion

retain_hypothesis

### Registry result rows (historical text retained)

- **E0 return**: `1.70464` account_return_percent; population `three common trades`. Reported overlay result.
- **EWMA return**: `1.56018` account_return_percent; population `three common trades`. Reported overlay result.
- **ATM return**: `1.08354` account_return_percent; population `three common trades`. Reported overlay result.
- **Saved ledger arithmetic checks**: `24` descriptive_text; population `saved-ledger checks`. Arithmetic pass only, not strategy gate.

### Windows and exposure

- `train`: 2023-06-20T00:00:00Z, 2023-09-01T00:00:00Z); exposure=`exposed`. Constants trained; 7-day embargo.
- `validation`: [2023-09-08T00:00:00Z, 2023-10-24T00:00:00Z); exposure=`reused_validation`. Validation window reused.

- Sample unit / count: `common trade` / `3`. Only three common trades; all positive results derive from one BTC winner.
- Cost and accounting evidence: Primary fee 5 bp and slippage 5 bp; funding uses prior-hour mark proxy, publication-time availability unknown. ATM reduced winner while leaving full size on losses.
- Audit scope: Existing gate report and results summary; no replay.; replayed for this hub: `False`.

## Model inputs / factor definitions

These links record only direct source evidence; absence of a known link is not filled from the experiment name. `binding_scope` distinguishes frozen columns from a named input family.

- No direct factor input relation established for this record.

### Related evidence only (not asserted as consumed input)

- Related evidence only (`sixfactor-option-eoh-atm-volatility`): The cited EOH calibration is part of the volatility-risk evidence; it is not proof that C3/X3 traded on a known, available IV field. Exact C3/X3 factor and label remain UNKNOWN. [Definition card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_option_eoh_atm_volatility.md%3E`). Evidence: `C3_VOL_OVERLAY_2023_V1R3_GATE_REPORT_CN_V1R2.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/c3_vol_overlay2023_v1r3/C3_VOL_OVERLAY_2023_V1R3_GATE_REPORT_CN_V1R2.md%3E`), `SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/sixfactor_longcycle_v1/SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md%3E`)

### Explicit unknowns and next evidence

- **exact C3/X3 forecast inputs/label — UNKNOWN.** The final supplement describes forecast-supported arms and EOH calibration but does not list raw feature columns or exact label formula. Check: `linked C3 report's frozen protocol/config and input/code manifests.`.
- **true forecast publication time — UNKNOWN.** Final report explicitly says actual prediction publication time is unknown. Check: `exchange/provider source timestamp and event publication metadata.`.
- **actual feature/factor columns consumed by each C3/X3 model — UNKNOWN.** The EOH calibration report is related evidence, not direct proof that the C3/X3 forecast or overlay consumes those columns. Check: `C3/X3 frozen model descriptor and input manifest bound to its run.`.

## Target label and maturity

Option/EOH calibration target is discussed; exact target unit, publication clock and point-in-time exposure remain UNKNOWN. The documented exposed calibration result is not a trading label or alpha proof.

No label factor card assigned in the bounded evidence pass.

## Study-specific bounded notes

No extra sub-study note was added in this bounded docs-only pass.

## Source references

- `C3_VOL_OVERLAY_2023_V1R3_GATE_REPORT_CN_V1R2.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/c3_vol_overlay2023_v1r3/C3_VOL_OVERLAY_2023_V1R3_GATE_REPORT_CN_V1R2.md%3E`) — `READ_SUMMARY_OR_METADATA`; Existing limited gate report.
- `C3_VOL_OVERLAY_2023_V1R3_RESULTS_CN.md` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/c3_vol_overlay2023_v1r3/C3_VOL_OVERLAY_2023_V1R3_RESULTS_CN.md%3E`) — `READ_SUMMARY_OR_METADATA`; Existing overlay results.

## Related primary records

- `factor-calibration-causal-2023` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/factor-calibration-causal-2023.md%3E`)

- Unchanged registry record (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/experiment_registry.json%3E`); the registry's `relative_path` base is `research_hub/`.
- EXPLORATORY_UNVERIFIED is the historical registry status; this card does not promote its evidence.

See the DRAFT session workflow (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/SESSION_WORKFLOW_DRAFT.md%3E`) and machine map (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/research_map.json%3E`).
