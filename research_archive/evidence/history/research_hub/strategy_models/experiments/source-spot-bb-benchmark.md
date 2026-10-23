> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Source spot BB120x2 benchmark

**Primary historical record:** `source-spot-bb-benchmark`. This is the single main card for this registry ID; cross-links are navigation only.

- Category: `strategy`; registry version pin: `trend research report`.
- Market / symbols / timeframe: `spot` / `spot source universe` / `multiple`.
- Registry verdict: `LEGACY_RESEARCH`; recommendation: `retain_benchmark`.
- Primary directory: `strategy_models`; linked factors with direct evidence: `spot-bb120x2-rule-v1`.

## Evidence and bounded conclusion

retain_benchmark

### Registry result rows (historical text retained)

- **BB benchmark definition**: `BB120x2, no stop, four slots` descriptive_text; population `spot reference`. Do not conflate with Top1 annual trend results.

### Windows and exposure

- `evaluation`: None, None); exposure=`exposed`. Exact period not established from cited summary; spot-only benchmark.

- Sample unit / count: `strategy benchmark configuration` / `None`. Spot-only reference; no perpetual inference. Performance not asserted by this entry.
- Cost and accounting evidence: Benchmark definition only; no performance values asserted in this record.
- Audit scope: Existing source reports and provenance docs; spot reference separated from perpetual claims.; replayed for this hub: `False`.

## Model inputs / factor definitions

These links record only direct source evidence; absence of a known link is not filled from the experiment name. `binding_scope` distinguishes frozen columns from a named input family.

- Factor `spot-bb120x2-rule-v1`: Direct rule evidence: Bollinger n=120, k=2; EMA200 gate; enter above upper band, exit below middle or when EMA gate fails; fixed_slot with no stop. Historical selected configuration is a deterministic rule, not supervised prediction. Evidence: [`signals.py` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/trend_research/tr/signals.py%3E`), `TREND_RESEARCH_REPORT.md` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/trend_research/reports/TREND_RESEARCH_REPORT.md%3E`). Factor card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_spot_bb120x2_rule.md%3E`).

### Related evidence only (not asserted as consumed input)

- None recorded.

### Explicit unknowns and next evidence

- **complete historical run pin and source-bar availability contract — UNKNOWN.** Rule family is identified, but all parameters/source identity and publication timing are not bound by the historical summary. Check: `The complete historical run manifest and source implementation hash.`.

## Target label and maturity

Deterministic spot BB benchmark; no supervised label asserted.

No label factor card assigned in the bounded evidence pass.

## Study-specific bounded notes

No extra sub-study note was added in this bounded docs-only pass.

## Source references

- `TREND_RESEARCH_REPORT.md` (`provenance:nonincluded/crypto-leverage/research_hub/crypto/trend_research/reports/TREND_RESEARCH_REPORT.md%3E`) — `READ_SUMMARY_OR_METADATA`; Spot BB120x2/no-stop/four-slot benchmark.

## Related primary records

- None recorded.

- Unchanged registry record (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/experiment_registry.json%3E`); the registry's `relative_path` base is `research_hub/`.
- LEGACY_RESEARCH is the historical registry status; this card does not promote its evidence.

See the DRAFT session workflow (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/SESSION_WORKFLOW_DRAFT.md%3E`) and machine map (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/research_map.json%3E`).
