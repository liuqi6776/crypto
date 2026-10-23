> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Factor calibration, volatility and causal-timing evidence

**Primary historical record:** `factor-calibration-causal-2023`. This is the single main card for this registry ID; cross-links are navigation only.

- Category: `factor`; registry version pin: `EOH/BVOL/foundation/follow-up/six-factor/timing summaries`.
- Market / symbols / timeframe: `perpetual` / `BTC, ETH, multiple; see reports` / `multiple`.
- Registry verdict: `EXPLORATORY_UNVERIFIED`; recommendation: `retain_hypothesis`.
- Primary directory: `factor_research`; linked factors with direct evidence: none established.

## Evidence and bounded conclusion

retain_hypothesis

### Registry result rows (historical text retained)

- **EOH ATM loss calibration**: `improved; publication-unit gap` descriptive_text; population `261 scores`. Skew did not help; publication timing remains a limitation.
- **Binance BVOL metrics**: `QLIKE better; MSE worse` descriptive_text; population `1346 rows`. Availability assumed.
- **BTC strength trend residual CI**: `crosses zero` descriptive_text; population `focused follow-up`. No residual increment established.
- **Six-factor basket**: `low-funding basket no advantage; basis clock unresolved; OI/book continuity insufficient` descriptive_text; population `six-factor study`. Lead-lag timing inference is separately invalidated due to incomplete matched controls.

### Windows and exposure

- `evaluation`: None, None); exposure=`unknown`. Per-study windows and availability details are in source artifacts; limited audit does not infer them.

- Sample unit / count: `score row / event, varies by study` / `261`. EOH has 261 scores; BVOL has 1346 rows. Rows are not independent trades; several feature availability and causal controls unresolved.
- Cost and accounting evidence: Prediction/calibration studies are not account ledgers. BVOL availability was assumed. Funding/basis/OI/book timing or continuity is unresolved in cited work.
- Audit scope: Existing factor summaries and validity notices; invalidated results remain explicitly invalidated.; replayed for this hub: `False`.

## Model inputs / factor definitions

These links record only direct source evidence; absence of a known link is not filled from the experiment name. `binding_scope` distinguishes frozen columns from a named input family.

- No direct factor input relation established for this record.

### Related evidence only (not asserted as consumed input)

- Related evidence only (`sixfactor-support-event-family`): Support/event evidence is one of six study directions; event semantics include reported failure cases and are not a validated strategy input. [Definition card (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/factor_cards/%3Cshared_support_event_family.md%3E`). Evidence: `SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md` (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/reports/strategy_validation/sixfactor_longcycle_v1/SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md%3E`)
- Related evidence only (`sixfactor-option-eoh-atm-volatility`): EOH/ATM calibration and its limited exposed-sample result are explicitly summarized. Definition card (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/factor_cards/%3Cshared_option_eoh_atm_volatility.md%3E`). Evidence: `SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md` (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/reports/strategy_validation/sixfactor_longcycle_v1/SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md%3E`)
- Related evidence only (`sixfactor-trend-ema-macd-bollinger-family`): EMA/MACD/Bollinger trend account family is one documented direction; formulas remain rule-specific. Definition card (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/factor_cards/%3Cshared_sixfactor_trend_family.md%3E`). Evidence: `SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md` (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/reports/strategy_validation/sixfactor_longcycle_v1/SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md%3E`)
- Related evidence only (`sixfactor-btc-relative-strength-family`): BTC direction/relative-strength family is described, with exact transforms varying by sub-study. Definition card (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/factor_cards/%3Cshared_btc_relative_strength_family.md%3E`). Evidence: `SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md` (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/reports/strategy_validation/sixfactor_longcycle_v1/SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md%3E`)
- Related evidence only (`basis-cross-venue-price-spread`): Cross-venue spread is explicitly BLOCKED/NOT TESTED; clock and units unresolved, not an invalid factor finding. Definition card (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/factor_cards/%3Cshared_basis_cross_venue_spread.md%3E`). Evidence: `SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md` (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/reports/strategy_validation/sixfactor_longcycle_v1/SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md%3E`)
- Related evidence only (`observed-funding-event-features`): Report documents event rate/age/7-day sum/count and the event+5m, age<=16h research availability assumption; no OHLC-grid fill. Definition card (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/factor_cards/%3Cshared_observed_funding_events.md%3E`). Evidence: `SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md` (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/reports/strategy_validation/sixfactor_longcycle_v1/SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md%3E`)

### Explicit unknowns and next evidence

- **per-direction model/rule input map — UNKNOWN.** The six-direction summary is a research inventory; these associations do not imply all methods consume all six factors. Check: `Each direction-specific report/protocol independently; preserve unknown per-substudy links.`.

## Target label and maturity

UNKNOWN for this study/registry cluster; check the linked protocol/config separately for each sub-study. This card does not infer a target from its name.

No label factor card assigned in the bounded evidence pass.

## Study-specific bounded notes

The associated six-factor evidence describes six research directions: support events, EOH/ATM IV, EMA/MACD/Bollinger trend, BTC relative strength, cross-exchange spread, and observed Core4 funding. This registry cluster is factor research; these directions are not asserted as inputs to an unrelated model.
The spread direction is BLOCKED/NOT_TESTED, not a negative factor result. EOH publication timing, units and point-in-time availability remain UNKNOWN. A calibration MSE improvement is limited calibration evidence, not alpha.
Funding evidence uses the last observed event rate and age plus observed 7-day sum/count and cross-section; event+5m and age<=16h are study assumptions. Reported daily gross-return difference is negative and there is no account-cost validation.

## Source references

- `calibration_metrics.json` (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/reports/strategy_validation/eoh_train_scale_calibration_v1/calibration_metrics.json%3E`) — `READ_LIMITED_ARTIFACT`; Calibration metrics summary.
- `core_run_contract.json` (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/reports/strategy_validation/binance_bvol_increment_2023/core_run_contract.json%3E`) — `READ_LIMITED_ARTIFACT`; BVOL contract and row count.
- `FOCUSED_FOLLOWUP_RESULTS_CN_20261003_v1r2.md` (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/reports/strategy_validation/focused_followup_v1/FOCUSED_FOLLOWUP_RESULTS_CN_20261003_v1r2.md%3E`) — `READ_SUMMARY_OR_METADATA`; Focused residual follow-up.
- `SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md` (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/reports/strategy_validation/sixfactor_longcycle_v1/SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md%3E`) — `READ_SUMMARY_OR_METADATA`; Six-factor results and data limits.

## Related primary records

- None recorded.

- Unchanged registry record (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/factor_cards/experiment_registry.json%3E`); the registry's `relative_path` base is `research_hub/`.
- EXPLORATORY_UNVERIFIED is the historical registry status; this card does not promote its evidence.

See the DRAFT session workflow (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/factor_cards/SESSION_WORKFLOW_DRAFT.md%3E`) and machine map (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/factor_cards/research_map.json%3E`).
