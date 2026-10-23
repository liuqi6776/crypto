> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Volatility forecast causal leakage repair — 2026-09-30

**Status: REPAIRED IN CODE; PRIOR NUMERIC OUTPUTS INVALIDATED; NO MARKET FORECAST RERUN.**

This is a versioned implementation audit, not a strategy-validation pass. The strategy-validation protocol requires causal timing evidence before a model can be evaluated; see the workspace gate protocol (`provenance:nonincluded/crypto-leverage/.agents/skills/strategy-validation-gates/SKILL.md`) and research integrity rules (`provenance:nonincluded/crypto-leverage/docs/RESEARCH_INTEGRITY.md`). No strategy or trading-readiness claim is supported.

## Findings and repair

1. **GARCH used future realized innovations.** In the prior implementation, `model_garch11` generated `garch11_variance_path` over the entire return vector and averaged entries after each forecast row. Those entries included future squared returns. The path seed also used the mean of the complete input series. The code now fits parameters on the historical prefix, reconstructs the conditional variance using only observations available through the current open, then recursively forecasts expected future variance using `omega + (alpha + beta) * h`. The forecast for label row `t` records `available_time = index[t+1]`, consistent with `r_t = log(open[t+1]/open[t])` becoming known at the next open.

2. **OLS/HAR trained on labels whose forward window had not matured.** At forecast row `t`, the fit now ends at target row `t-H`, inclusive: that label's last return is `r[t]`, which becomes observable at open `t+1`, the forecast's availability time. The same bound is used for scalar OLS/EWMA and HAR. `fit_window_end_bar` records the last usable paired row (or the last valid HAR row), not merely the preceding forecast row.

3. **Other model timing was inspected.** EWMA and HAR predictors at label row `t` use returns through `r[t]`, which are available at the recorded next-open time. The expanding baseline consumes trailing realized values only through the prior row, and the random-walk baseline is indexed on the realized trailing window. Every public model frame now includes `available_time`, including empty frames. The evaluator is blocked because its legacy window slices still use label-row dates.

Forecast frames now carry `available_time`: EWMA/HAR/GARCH and the random-walk reference use the next open when they consume `r_t`; the expanding baseline is available at the current open because its history ends at `r_(t-1)`. The existing evaluator (`provenance:nonincluded/crypto-leverage/scripts/evaluate_volatility_predictability.py`) rejects execution before output directory creation unless both a versioned origin contract and availability-aware evaluator are implemented. The unchanged frozen spec does not declare the new origin contract.

## Invalidated artifacts and claims

Do not cite or reuse any prior forecast values, model rankings, loss/skill metrics, calibration tables, or conclusions derived from the volatility forecast outputs. This includes the generated Round 4 results report (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volatility/VOLATILITY_PREDICTABILITY_RESULTS.md`) and results JSON (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volatility/volatility_results.json`), as well as downstream sizing analyses that consumed those forecasts. The frozen study specification (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volatility/study_spec_volatility_predictability.json`) is retained unchanged as the historical preregistration; it is not evidence that the old forecasts were causal. Existing published result files were deliberately left byte-for-byte untouched.

This notice invalidates forecast-derived claims because the GARCH lookahead affected forecast rows and the OLS/HAR fit windows admitted immature labels. It does not assert that the corrected models have predictive value. No corrected market numbers have been produced.

## Synthetic verification and bounded procedure

Executed only:

```text
.venv\Scripts\python -m pytest tests/test_volatility_predictability.py -q
25 passed in 1.89s
```

The tests use synthetic return/price series plus static study-spec metadata. New checks establish that (a) open-to-open `r_t` becomes observable only at the next open, (b) changing immature labels cannot affect scalar OLS or HAR fits, including when warmup is shorter than the target horizon, (c) EWMA forecasts are invariant to returns after the forecast origin, (d) GARCH forecasts are future-invariant and match the analytic multistep conditional expectation, and (e) every public model frame exposes `available_time`. A guard test confirms that the unchanged legacy spec is rejected before numeric execution.

No 2026-or-later numeric market values were decoded. No market forecast, source-copy verification, importer, inventory/report builder, full test suite, data download, trading command, service, scheduler, or external source write was run. The broad maintenance chain in workspace `AGENTS.md` would invoke source-copy/data import/report regeneration and can decode or rewrite 2026 market data and frozen outputs; that conflicts with the user-specified no-2026-value and preserve-published-results boundaries for this repair. This scoped synthetic/hash-only check is recorded instead. Root review is required before any market-data run.

## Frozen implementation identity

SHA256 values below identify the reviewed code and tests only; no dataset was read to produce them.

| File | SHA256 |
| --- | --- |
| `volatility.py` (`provenance:nonincluded/crypto-leverage/tools/perptools/volatility.py`) | `46F0C00ABA6066F3166B30E298626869B2E26931D712879E4F3339BE5EC78731` |
| `test_volatility_predictability.py` (`provenance:nonincluded/crypto-leverage/tests/test_volatility_predictability.py`) | `033B6D9D34BE0BA7F386436AC576418C895E98FB0A23E4B09759A0C88663EF6F` |
| `evaluate_volatility_predictability.py` (`provenance:nonincluded/crypto-leverage/scripts/evaluate_volatility_predictability.py`) | `34D44A24F1F5EA02E7C0B33417E1537DD9A3FF542CD6407FFF9886A842436288` |

The following digests were checked after the repair to confirm the frozen preregistration and published outputs stayed unchanged:

| Preserved artifact | SHA256 |
| --- | --- |
| `study_spec_volatility_predictability.json` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volatility/study_spec_volatility_predictability.json`) | `7279757833CBA7E8DA1216FA58189FD807F45B08F3DCA56D10A1E5461FF52FFF` |
| `volatility_results.json` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volatility/volatility_results.json`) | `DD223BCA9F9F8445E38695256587A0F89E1FEF6C664F6DF7047B00D94D557E03` |
| `VOLATILITY_PREDICTABILITY_RESULTS.md` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volatility/VOLATILITY_PREDICTABILITY_RESULTS.md`) | `6B2E4313478090ADC6EF5E3ED1C52625AAC7367C14E9C9F32E095C51C2468A60` |
| `volatility_predictability_evidence.json` (`provenance:nonincluded/crypto-leverage/archive/inventory/volatility_predictability_evidence.json`) | present; hash not read to avoid decoding its numeric result payload |

## Remaining review items

- Independently review the new availability timestamp and conditional-variance recursion before permitting any market forecast run.
- Audit all downstream volatility-sizing consumers for explicit use of the recorded `available_time` and ensure they do not treat the label-row timestamp as the forecast availability time.
- Root review accepted the synthetic repair conditionally; downstream origin-aware numeric evaluation remains **BLOCKED**. Existing 2024–2026 windows are exposed development data, and a genuinely future test window is **NOT_RUN / NOT_AVAILABLE** under the frozen protocol. Any later authorized numeric rerun must respect the applicable warmup and development bounds, preserve prior outputs, and remain exploratory.
- No strategy-validation gate is passed by these synthetic tests.
