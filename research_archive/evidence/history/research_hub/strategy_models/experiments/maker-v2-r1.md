> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# MTF trend-range Maker v2_r1

**Primary historical record:** `maker-v2-r1`. This is the single main card for this registry ID; cross-links are navigation only.

- Category: `model`; registry version pin: `v2_r1 completion`.
- Market / symbols / timeframe: `perpetual` / `ETH, SOL` / `multiple / action rows`.
- Registry verdict: `EXPLORATORY_UNVERIFIED`; recommendation: `pause_current_version`.
- Primary directory: `strategy_models`; linked factors with direct evidence: none established.

## Evidence and bounded conclusion

pause_current_version

### Registry result rows (historical text retained)

- **Maker candidates / ledger rows / eligible positives**: `72 / 60374 / 0` descriptive_text; population `Maker v2_r1 completion`. Not an account sample count.

### Windows and exposure

- `evaluation`: None, None); exposure=`not_established_untouched`. Version-specific window not established in the limited summary.

- Sample unit / count: `candidate ledger row` / `60374`. 72 candidates and 60374 ledger rows are not independent account samples; zero eligible positive.
- Cost and accounting evidence: Base and stress results reported negative for exposed ETH/SOL windows; inspect cited reports for variant details. Candidate row counts do not indicate performance.
- Audit scope: Existing selected run summary and completion artifact; no replay.; replayed for this hub: `False`.

## Model inputs / factor definitions

This is a deterministic candidate grid, not a supervised ML task. The frozen rule contract uses completed 5m/15m channel bars; Bollinger 20/2 (`ddof=0`); width/mid stability and outside-close checks; EMA20/50 trend with 3-bar momentum; and optional EMA5/20 or SMA5/10 cross. Three families are `edge_prepositioned`, `ma_crossover`, and `edge_plus_cross`; the bound candidate grid contains 72 choices of edge/stop/target fractions and execution timings. See the [rule-contract card (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/factor_research/factor_cards/shared_maker_v2_channel_rule_contract.md%3E`) and frozen config (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/mtf_trend_range_maker_v2_r1/frozen_config.json%3E`).

### Known execution limits

The replay has configured fees/slippage, post-only rejection, trade-through threshold, stop-first same-minute barrier handling, funding-event clock and mark tolerance. Actual maker queue position, quoted spread/capacity, exact funding mark at calc_time and intraminute event order remain unavailable; there is no account margin/liquidation/10x model. No supervised target or “model features UNKNOWN” template applies here.

## Study-specific bounded notes

The bound completion reports 72 candidates, zero qualified-positive family winners and no global winner. Development selection required at least 50 trades per symbol and a positive mean on each symbol. Run, runner, framework, config and grid identities are SHA-bound. The deterministic rule contract and execution limits are described above; no supervised label exists.

## Source references

- `completion.json` (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/reports/strategy_validation/mtf_trend_range_maker_v2_r1/completion.json%3E`) — `READ_LIMITED_ARTIFACT`; Maker v2_r1 candidate/ledger completion counts.

## Related primary records

- None recorded.

- Unchanged registry record (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/experiment_registry.json%3E`); the registry's `relative_path` base is `research_hub/`.
- EXPLORATORY_UNVERIFIED is the historical registry status; this card does not promote its evidence.

See the DRAFT session workflow (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/SESSION_WORKFLOW_DRAFT.md%3E`) and machine map (`provenance:nonincluded/crypto-leverage/research_hub/strategy_models/experiments/research_map.json%3E`).
