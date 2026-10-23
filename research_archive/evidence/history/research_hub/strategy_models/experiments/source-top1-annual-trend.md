> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Source Top1 annual trend result

**Primary historical record:** `source-top1-annual-trend`. This is the single main card for this registry ID; cross-links are navigation only.

- Category: `strategy`; registry version pin: `V1_1X_per_year_decision.md`.
- Market / symbols / timeframe: `spot` / `spot source universe` / `multiple`.
- Registry verdict: `LEGACY_RESEARCH`; recommendation: `retain_benchmark`.
- Primary directory: `strategy_models`; linked factors with direct evidence: `source-top1-annual-trend-rule-v1`.

## Evidence and bounded conclusion

retain_benchmark

### Registry result rows (historical text retained)

- **Top1 updated 1x spot full-history account return**: `1119.75` account_return_percent; population `full cited history`. MDD 69.95%; recent 2024-01 through 2026-09 result -19.54%. This is the 1x spot Top1 result, not the BB benchmark.

### Windows and exposure

- `evaluation`: None, None); exposure=`exposed`. Report gives full date span 2020-10-15 through 2026-09-22, but exact UTC boundary semantics are unknown. Recent 2024-01 through 2026-09 period is development-exposed.

- Sample unit / count: `annual trend strategy account result` / `None`. Historical periods exposed; 2021 dominates the full-history result.
- Cost and accounting evidence: Legacy 1x spot account simulation; do not transfer this result to perpetuals. Other leverage tables are not represented by this result.
- Audit scope: Existing source reports and provenance docs; spot reference separated from perpetual claims.; replayed for this hub: `False`.

## Model inputs / factor definitions

These links record only direct source evidence; absence of a known link is not filled from the experiment name. `binding_scope` distinguishes frozen columns from a named input family.

- Factor `source-top1-annual-trend-rule-v1`: Direct report/source evidence: one-position BTC/asset EMA200 gate, momentum ranking and ATR14 x 1.5 stop. Exact historic run-parameter/source binding remains partial. Evidence: [`V1_1X_per_year_decision.md` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/reports/V1_1X_per_year_decision.md%3E`), `top1_decision_engine.py` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/crypto_quant/core/top1_decision_engine.py%3E`). Factor card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_source_top1_annual_trend_rule.md%3E`).

### Related evidence only (not asserted as consumed input)

- None recorded.

### Explicit unknowns and next evidence

- **complete historical run pin and source-bar availability contract — UNKNOWN.** Rule family is identified, but all parameters/source identity and publication timing are not bound by the historical summary. Check: `The complete historical run manifest and source implementation hash.`.

## Target label and maturity

Deterministic annual trend result; no supervised label asserted.

No label factor card assigned in the bounded evidence pass.

## Study-specific bounded notes

No extra sub-study note was added in this bounded docs-only pass.

## Source references

- `V1_1X_per_year_decision.md` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/reports/V1_1X_per_year_decision.md%3E`) — `READ_SUMMARY_OR_METADATA`; Updated source trend result and recent period.

## Related primary records

- None recorded.

- Unchanged registry record (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/experiment_registry.json%3E`); the registry's `relative_path` base is `research_hub/`.
- LEGACY_RESEARCH is the historical registry status; this card does not promote its evidence.

See the DRAFT session workflow (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/SESSION_WORKFLOW_DRAFT.md%3E`) and machine map (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/research_map.json%3E`).
