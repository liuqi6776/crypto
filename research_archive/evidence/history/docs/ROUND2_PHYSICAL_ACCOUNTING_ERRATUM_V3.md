> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Round 2 physical position accounting erratum and revised results (v3)

**Version:** `round2_strategy_eval_20260925_v3_physical`
**Corrected run id:** `round2v3_20260926T010145Z` (generated 2026-09-26T01:01:45Z)
**Active frozen spec:** `reports/strategy_validation/round2/study_spec_v3.json`
sha256 `24d9e45ecce9c12992a1d9c366c596212265c0f43f226092680e46af90fc3278`
**Supersedes (preserved, not edited):**

* `docs/ROUND2_ACCOUNTING_ERRATUM.md` (v2 prose, now carrying a withdrawal banner) and
  `reports/strategy_validation/round2/study_spec_v2.json` sha256
  `18bf9c0f425ee44459a334f8e61613942644998192684af4834d33db5babd9a4`;
* `docs/ROUND2_STRATEGY_NET_RETURN_EVALUATION.md` (v1 prose) and
  `reports/strategy_validation/round2/study_spec.json` sha256
  `a403a266c6a396bb4c04dfb858f501fea5919a3a5f5b32e979021b7305d84ccf`.

**Trigger:** `docs/ROUND2_CODEX_REVIEW_ADDENDUM.md` (physical position accounting).
**Companion findings:** `docs/ROUND2_CODEX_REVIEW_FINDINGS.md` (the five v2 items,
all of which remain fixed).
**Status:** `EXPLORATORY`. Nothing here is validated, tradable or a promise of
future returns. No live/paper order, no download, no scheduler and no external
write was performed.

The v2 numbers were **provisional and are now withdrawn from strategy selection**:
the revised `simulate()` still did not implement the self-financing sleeve it
claimed. This document states what was wrong, what the v3 engine does instead, and
the corrected results. The v1 and v2 machine-readable runs, prose and per-pair
ledgers are preserved under
`reports/strategy_validation/round2/superseded_v1/` and
`reports/strategy_validation/round2/superseded_v2/` (see §11).

---

## 1. What was actually wrong in v2

The addendum's core finding is confirmed, and two further defects were found while
building the replacement. All three are engine defects: the strategy set, the
window, the price grid, the causality rule, the observed funding events, the
primary cost and the acceptance rule are unchanged from v1/v2.

| # | Defect | Consequence | Fix |
| :-- | :-- | :-- | :-- |
| 1 | The v2 drift term scored the *achieved* exposure on **pre-trade** equity: the fee was subtracted from the denominator a second time after the fixed point had already solved for it (`achieved = q*P/(E_pre*(1-c))`). | The reported `exposure` was `target*(1-c)` after the trade, i.e. a permanent 10 bp shortfall at 10 bp/side. The ledger then treated that shortfall as drift and charged a rebalance into it on every later bar that had a price move. | v3 carries `quantity`, `cash` and `equity` explicitly. The fixed point is solved so the **post-trade** market value is the target times the **post-trade** equity, `achieved` is scored on that same executed equity, and the closed-form solution is asserted to `1e-9`. |
| 2 | The v2 final-bar block rebuilt equity from `cash + notional` instead of the bar's own mark-to-market P&L, which silently re-counted the whole prior mark on the last bar. | The published `net` series did not equal `gross - fees + funding` on the final bar, and the per-bar returns no longer compounded to the reported ending equity. | v3 computes the final bar's gross P&L from `quantity * (final_open - open)` like every other bar, includes the final settlement in the post-trade equity, and asserts the per-bar identity on every row. |
| 3 | `drift_rebalancing_turnover_total` subtracted the **liability-space** signal turnover from the **notional-space** physical turnover: two different units. | For a constant-target sleeve the entire physical turnover was reported as "drift" only by coincidence of the two units; for others the split was meaningless and could exceed the total. | v3 reports `turnover_signal_notional_total` (traded notional the *signal* alone asks for, measured against pre-trade equity) and `drift_rebalancing_turnover_total = total - signal`, both in the same units, plus the liability-space `signal_turnover_total` separately. |

The addendum's specific observation — *"for a permanent 1× long it charges zero
turnover after funding reduces equity, yet it again applies 1× to the reduced
equity"* — is exactly defect 1. The v3 ledger now also treats the **funding
notional** as a real cashflow (`-quantity * rate * price_proxy`) rather than as a
position-fraction return term, so the drift is visible in the equity path.

Two things the addendum asked for and v3 does **not** claim:

* It does **not** use a per-settlement mark price. The local funding files carry no
  `markPrice` (G13), so each settlement is valued at a **labelled open-to-open
  linear price proxy**, recorded on every funding row
  (`price_proxy_label = open_to_open_linear_interpolation_of_4h_opens`). The
  settlement *times* are the observed ones; the notional is a proxy.
* It does **not** model intra-bar fills, partial fills or a liquidation path. All
  trades happen at bar opens.

---

## 2. The v3 physical ledger (what `simulate` now does)

For each asset sleeve, in its own units:

1. **Opening state.** `cash = 1`, `quantity = 0`, `equity = 1` at the first bar.
2. **Bar open.** The target drawn on at bar `t` is the one decided at bar `t-2`
   (`target.shift(2)`), so the fill is strictly later than the decision. The
   quantity is re-solved so that, *after* paying the fee, the position's market
   value is the target times the post-trade equity. With `c` the flat per-side cost
   (fee + slippage), `E_pre` the pre-trade equity, `P` the open, `q_prev` the
   inherited quantity and `phi` the fee as a fraction of `E_pre`:
   `q = target*E_pre*(1-phi)/P` and `phi = c*|q - q_prev|*P/E_pre`. The root is
   bracketed and bisected on `[0, 1)`; **the fee is solved with the target, not
   applied after it**. The achieved exposure is `q*P/(E_pre*(1-phi))` and equals the
   target to `1e-9`.
3. **Cash and fees.** `fee_cash = |delta_quantity| * P * c` is charged on the traded
   notional and paid out of cash; the fixed point is asserted to leave cash
   non-negative, and a target at or beyond `1/c` raises instead of silently
   changing the convention.
4. **Inside the bar the quantity is constant.** The mark-to-market P&L is
   `quantity * (next_open - open)`. Nothing in the funding step can change the
   quantity.
5. **Funding at its own event time.** For each observed settlement inside the
   measured window, `funding_cash = -quantity * rate * price_proxy`, where
   `quantity` is the quantity held across the bar containing the settlement and
   `price_proxy` is the labelled open-to-open interpolation. The settlement changes
   cash and equity (and therefore the exposure the next open inherits) but never the
   quantity. A settlement outside the measured window is counted in
   `funding_events_out_of_range`, never filled or extrapolated.
6. **Identities.** `cash + quantity*price == equity_post_trade` at every open
   (worst residual `1.4e-14` over all 40 published sleeve ledgers),
   `cash + marked notional == equity` after every bar (`1.8e-15`),
   `prod(1+net) == ending equity` (`1.4e-12`), and
   `net == gross - fees + funding` on **every** bar (`4.0e-16`). The portfolio
   reproduces the same decomposition with a `self_financing_residual` of
   `<= 5.3e-16`.
7. **Break-even cost.** The metric is the flat per-side cost at which the compounded
   NET portfolio total return is zero, and it is now found by **re-running the whole
   physical ledger** at each trial cost (geometric scan bracket + bisection),
   because the traded quantity, the equity path and the funding notional all depend
   on the cost. It is `n/a` when portfolio turnover is below 30 units or no root is
   found within 500 bp/side. The metric is never approximated by a closed form.

The choice of convention is recorded in `study_spec_v3.json`
(`portfolio.fee_target_fixed_point`, `portfolio.quantity_conservation`,
`portfolio.physical_identity`, `funding_cashflow.price_proxy`) and its consequences
are measured, not hidden: `max_target_exposure_gap` is `2.2e-16` for every
strategy, `target_fixed_point_fallbacks` is `0`, and the fee drag shows up as
explicit per-bar traded notional rather than as a phantom drift.

### 2.1 Solver and diagnostic notes

* `solve_target_quantity` is exported and deterministically tested. The bisection
  runs to the floating-point bracket limit (no fixed iteration count), so a
  constant target produces a **bit-stable** quantity: a 1× long with a flat price
  and no funding trades exactly once, and its `quantity` column is constant to the
  last bit.
* `turnover` is traded notional divided by pre-trade equity (so it stays comparable
  with the earlier rounds); `turnover_units` is the traded notional in asset units.
  `position` is the legacy pre-trade leverage ratio, `exposure` is
  `notional / equity_post_trade` (the achieved fraction of post-trade equity).
* `funding_notional`, `quantity`, `rate` and `price_proxy` are recorded per
  settlement, so a reviewer can recompute every funding cashflow by hand.

---

## 3. Corrected headline results (v3)

Primary cost **10 bp/side, 0 slippage, observed funding included, 1× notional** on
the frozen window `2020-08-11 → 2026-09-24T20:00Z` (SOL from 2020-09-14).
Portfolio = self-financing fixed-capital sleeves (equal 25% each, except
`BUY_HOLD_BTC` = 100% BTC).

| Strategy | Role | v2 NET (withdrawn) | **v3 NET** | v3 ann. | v3 Sharpe | v3 gross | v3 max DD | v3 pos.chg | v3 RT | v3 to/yr | v3 BE bp | v3 win | v3 PF | Label |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `BUY_HOLD_EW` | baseline | +1 811.70% | **+1 799.78%** | +61.71% | 1.01 | +1 988.31% | −83.40% | 11 973 | 4 | 0.3 | n/a | 100.00% | ∞ | `POSITIVE_NET_EXPLORATORY` |
| `BUY_HOLD_BTC` | baseline | +260.82% | **+260.56%** | +23.29% | 0.65 | +617.61% | −79.08% | 9 123 | 1 | 0.3 | n/a | 100.00% | ∞ | `POSITIVE_NET_EXPLORATORY` |
| `EXPLORATORY_DONCHIAN_50` | existing strategy | +165.70% | **+165.21%** | +17.26% | 0.61 | +441.05% | −42.26% | 6 518 | 736 | 65.7 | 34.3 | 34.92% | 1.35 | `POSITIVE_NET_EXPLORATORY` |
| `CARD_C_FUNDING_R1` | pre-registered | +38.24% | **+38.18%** | +5.42% | 0.63 | +80.32% | −17.73% | 13 020 | 1 310 | 30.5 | 27.4 | 33.28% | 1.49 | `POSITIVE_NET_EXPLORATORY` |
| `CARD_A_DONCHIAN_55_10` | diagnostic | +37.74% | **+37.54%** | +5.34% | 0.34 | +202.52% | −71.03% | 8 919 | 805 | 74.3 | 17.0 | 33.17% | 1.26 | `POSITIVE_NET_EXPLORATORY` |
| `CARD_B_TSMOM_EW` | pre-registered main | +36.78% | **+36.71%** | +5.24% | 0.60 | +79.83% | −17.69% | 13 064 | 1 302 | 31.0 | 26.6 | 32.64% | 1.46 | `POSITIVE_NET_EXPLORATORY` |
| `CARD_C_R3` | control | +36.78% | **+36.71%** | +5.24% | 0.60 | +79.83% | −17.69% | 13 064 | 1 302 | 31.0 | 26.6 | 32.64% | 1.46 | `POSITIVE_NET_EXPLORATORY` |
| `CARD_B_TSMOM_RP` | diagnostic | +36.54% | **+36.46%** | +5.21% | 0.58 | +80.23% | −17.53% | 13 174 | 1 413 | 31.9 | 25.9 | 25.90% | 1.43 | `POSITIVE_NET_EXPLORATORY` |
| `CARD_A_DONCHIAN_55_20` | pre-registered main | −14.95% | **−15.41%** | −2.70% | 0.19 | +93.91% | −68.04% | 11 013 | 639 | 63.8 | 5.7 | 31.92% | 1.24 | `NEGATIVE_NET` |
| `CARD_A_DONCHIAN_20_10` | diagnostic | −44.47% | **−44.45%** | −9.15% | 0.09 | +67.90% | −84.68% | 11 892 | 1 316 | 121.7 | 2.1 | 33.89% | 1.11 | `NEGATIVE_NET` |

### 3.1 Counts, and what changed

* **Counted honestly: 6 positive timing-rule configurations + 2 positive
  baselines + 2 negative timing-rule configurations.** Eight of the ten
  configurations are numerically net positive (six timing rules and the two
  constant-exposure baselines) and the other two timing rules are negative. The v2
  counts are unchanged and the v2/v1 prose error (mixing numerical sign with the
  `INSUFFICIENT_SAMPLE` label) stays corrected.
* **Labels: 8 `POSITIVE_NET_EXPLORATORY`, 2 `NEGATIVE_NET`, 0
  `INSUFFICIENT_SAMPLE`.** The frozen acceptance rule (`fewer than 30 position
  changes`) is retained, so the two baselines are no longer labelled
  `INSUFFICIENT_SAMPLE`. The physical ledger shows why the change count is large: a
  constant 1× target needs a real rebalance whenever a price move or a funding
  settlement changes the equity it is a fraction of, so `BUY_HOLD_EW` now has
  **11 973** position changes (v2: 2) and `BUY_HOLD_BTC` **9 123** (v2: 1). This is
  a **limitation of the frozen rule, stated prominently**: those changes are
  funding-induced micro rebalances, not entries, and each baseline has only **4**
  or **1** continuous signed position run, so the change count cannot support a
  win-rate or profit-factor inference. The two baselines are therefore
  **constant-exposure perpetual baselines, not one-time buy-and-hold**: they are
  excluded from the positive timing-rule list, and the frozen
  `POSITIVE_NET_EXPLORATORY` verdict is kept for reproducibility only. The
  win-rate/profit-factor caveat is stated in §3.3.
* **Every level moves down except `CARD_A_DONCHIAN_20_10`.** The largest
  corrections are the two price-only baselines, which are the most sensitive to
  the defect exactly as the addendum predicted:
  `BUY_HOLD_EW −11.92 pp`, `BUY_HOLD_BTC −0.25 pp`; the timing rules move by
  `−0.07` to `−0.48 pp` (`CARD_A_DONCHIAN_20_10` moves `+0.02 pp`). The v2
  **ranking of the timing rules is preserved** and no rule changes sign relative to
  v2.

### 3.2 The baseline arithmetic, explicitly

* `BUY_HOLD_BTC` is 100% BTC. Its sleeve ends at equity **3.605635**
  (`+260.56%`) with a closing notional of **3.605687**; the gross (zero cost, zero
  funding) sleeve return is `+617.61%`, and with observed funding but zero fees it
  is `+261.21%`. Funding removes the bulk of the gross on a permanently-long BTC
  book (a `−2.042746` USDT funding cashflow on a 1.0 initial book), but it no longer
  removes 1× of equity through a phantom rebalance. The single entry fee is
  `0.003247` USDT and the sleeve has 9 123 position changes from the 1×-of-equity
  re-solves the funding path requires.
* `BUY_HOLD_EW` sleeve ending equities are BTC **3.605635**, ETH **3.176327**,
  SOL **33.553836**, BNB **35.655529**, so
  `0.25 * (Σ equity) − 1 = +1 799.78%`, exactly the reported portfolio net. The
  fees total **0.045270** USDT of the initial 1.0 across the four sleeves and the
  observed funding cashflows total **−14.910563** USDT over the same book.
* All four sleeves finish fully invested (`ending notional ≈ ending equity`), so the
  1× convention holds at the measured end as well as at every interior open.

### 3.3 Trade and win-rate statistics

A round trip is one signed position run; a direct reversal `+q → -p` is two trips
and its fee is split into the closing leg (old trade) and the opening leg (new
trade). A position still open at the measured end has **no** exit fee invented.
The pooled win rate / profit factor at the primary cost: `EXPLORATORY_DONCHIAN_50`
34.92% / 1.35; `CARD_C_FUNDING_R1` 33.28% / 1.49; `CARD_A_DONCHIAN_55_10`
33.17% / 1.26; `CARD_B_TSMOM_EW` and `CARD_C_R3` 32.64% / 1.46; `CARD_B_TSMOM_RP`
25.90% / 1.43; `CARD_A_DONCHIAN_55_20` 31.92% / 1.24; `CARD_A_DONCHIAN_20_10`
33.89% / 1.11. Each constant-exposure baseline sleeve is one uninterrupted signed
run per held asset (`BUY_HOLD_EW` 4, `BUY_HOLD_BTC` 1), all profitable, so their win
rate is 100% and their profit factor is +∞; that is an artefact of having no losing
round trip and is **not** evidence of edge — hence the retained caveat rather than a
`POSITIVE_NET_EXPLORATORY`-as-evidence reading.

### 3.4 Break-even cost detail

| Strategy | v2 cost root (withdrawn) | **v3 cost root** | Survives 20 bp/side? |
| :--- | ---: | ---: | :--- |
| `EXPLORATORY_DONCHIAN_50` | 34.3 | **34.3** | yes: +77.39% |
| `CARD_A_DONCHIAN_55_10` | 17.0 | **17.0** | no: −12.75% |
| `CARD_A_DONCHIAN_55_20` | 5.9 | **5.7** | no: −42.83% |
| `CARD_A_DONCHIAN_20_10` | 2.1 | **2.1** | no: −73.56% |
| `CARD_C_FUNDING_R1` | 27.3 | **27.4** | yes: +14.70% |
| `CARD_B_TSMOM_EW` / `CARD_C_R3` | 26.5 | **26.6** | yes: +13.13% |
| `CARD_B_TSMOM_RP` | 26.0 | **25.9** | yes: +12.24% |

The roots are close to v2 because the turnover of the trading rules barely changes;
the *method* is different. Each root is a full physical-ledger rerun per trial cost
(scan bracket + bisection), and the reported root reproduces a zero compounded NET
to `1e-9` when the ledger is re-run there. The metric is `n/a` for the baselines
(turnover below 30 units), where the root is not identified.

### 3.5 Regime diagnostic (post-hoc, Gate 6 evidence only)

The rule (in `study_spec_v3.json`, applied to BTC 4h closes, shifted one bar) is
unchanged. Bar counts: bull 5 147, bear 4 947, sideways 2 122, undefined 1 200.

| Strategy | Bull | Bear | Sideways | Undefined |
| :--- | ---: | ---: | ---: | ---: |
| `BUY_HOLD_EW` | +369.02% | −34.41% | +31.98% | +367.93% |
| `BUY_HOLD_BTC` | +35.00% | −16.66% | −0.76% | +222.96% |
| `EXPLORATORY_DONCHIAN_50` | +94.57% | −50.24% | +48.44% | +84.52% |
| `CARD_C_FUNDING_R1` | +21.74% | −4.86% | −1.57% | +21.21% |
| `CARD_A_DONCHIAN_55_10` | −6.53% | −55.03% | +50.74% | +117.07% |
| `CARD_B_TSMOM_EW` / `CARD_C_R3` | +22.60% | −5.99% | −1.67% | +20.64% |
| `CARD_B_TSMOM_RP` | +20.94% | −6.12% | +0.51% | +19.58% |
| `CARD_A_DONCHIAN_55_20` | +27.04% | −67.77% | +18.74% | +73.97% |
| `CARD_A_DONCHIAN_20_10` | −13.31% | −76.58% | +35.87% | +101.39% |

The labels were defined after the frozen run, so this is a post-hoc diagnostic: it
shows the timing rules earn in bull/undefined regimes and lose in bear regimes, but
it **cannot** promote Gate 6. A pre-declared regime definition and a rerun on it are
still required.

### 3.6 Per-year results (primary cost, portfolio)

| Year | `BUY_HOLD_EW` | `EXPLORATORY_DONCHIAN_50` | `CARD_A_DONCHIAN_55_20` | `CARD_B_TSMOM_EW` |
| :--- | ---: | ---: | ---: | ---: |
| 2020 | +52.85% | +9.35% | −1.56% | +7.46% |
| 2021 | +981.15% | +112.70% | +20.99% | +15.76% |
| 2022 | −75.61% | −18.18% | −32.11% | +1.79% |
| 2023 | +227.05% | +31.64% | +41.70% | +4.81% |
| 2024 | +79.97% | +17.67% | −5.09% | +1.80% |
| 2025 | −12.16% | −15.39% | −30.62% | −4.63% |
| 2026 | −8.84% | +6.33% | +12.12% | +6.10% |

Full per-year, per-pair, sensitivity and regime tables live in
`reports/strategy_validation/round2/ROUND2_RESULTS.md`, in the per-strategy reports
`reports/strategy_validation/<slug>_round2v3_20260926T010145Z.md`, and in the
machine-readable `reports/strategy_validation/round2/round2_results.json`.

---

## 4. Deterministic tests for the three addendum cases

`tests/test_round2_strategy_eval.py` now covers the addendum's required cases
directly, on frames small enough to check by hand:

| Addendum case | Test | What it asserts |
| :-- | :-- | :-- |
| Constant 1× long, two bars, a nonzero funding charge and a later price move | `test_unit_long_with_funding_keeps_quantity_and_pays_turnover_to_rebalance` | the quantity at the settlement is exactly the entry quantity; the bar-4 open does not trade; the funding cashflow is `-q*rate*proxy` to the last bit; the later open re-solves to 1× of the changed equity |
| Constant 0.5 exposure with price and funding changes | `test_half_exposure_rebalances_on_price_and_funding_changes` | the funding settlement and the price move land in the bar they belong to; the next open re-solves to 0.5 of the changed equity; `cash + notional == equity` on every bar |
| A direct reversal | `test_direct_reversal_is_two_trades_and_trades_the_full_notional` | `+1 → −1` is two round trips, the closing leg is charged to the long and the opening leg to the short, and the reversal bar books the full notional |
| Quantity conservation | `test_unit_long_never_rebalances_without_funding`, `test_ledger_audit_rejects_a_tampered_quantity`, `ledger_audit` | a 1× book with a flat price and no funding is bit-identical after entry; a tampered quantity fails the audit |
| Fee/target fixed point | `test_fee_target_fixed_point_solves_in_closed_form` | `q*P == target*post-trade equity` to `1e-9`, and a non-positive equity raises |
| Break-even reruns the ledger | `test_break_even_cost_reruns_the_full_physical_ledger_at_each_trial_cost`, `test_break_even_is_not_reported_without_a_physical_ledger_callback` | the solver calls the callback more than 20 times and the reported root re-runs to zero; without a callback the metric is `n/a`, never a closed-form guess |
| Cash identity | `test_synthetic_ledger_check_reports_the_physical_cash_identity` | `cash + notional − equity == 0` and compounding equals the ending equity |

The synthetic hand-computable event stream (`synthetic_ledger_check`) was rewritten
so that every expected quantity and cashflow is an exact algebraic function of the
documented fixed point (`q = target*E_pre*(1-phi)/P`, `cashflow = -q*rate*proxy`,
fee `= c*|delta|*P`); it reconciles to `0.0` absolute difference at `1e-9`, and the
run refuses to report unless it passes.

---

## 5. Independent verifier for the physical ledger

New: `scripts/verify_physical_ledger.py` (report
`archive/inventory/physical_ledger_verification.json`). It re-derives the physical
claims from the published per-pair ledger CSVs and the raw observed funding series,
and exits `1` on any failed hard claim. It passes **4/4** across **40 ledgers**:

| Claim | Result |
| :-- | :-- |
| V1 every published per-pair ledger passes the structural physical-ledger audit | PASS |
| V2 quantity changes only on bars with booked traded notional | PASS |
| V3 funding is charged only at observed settlement times inside the measured window | PASS |
| V4 the run JSON is v3 and both earlier frozen specs are preserved | PASS |

The audit recomputes, per ledger: the open cash identity, the marked walk identity,
the funding-ledger reconciliation, the quantity held at each settlement, the traded
notional definition of turnover, the per-bar `net = gross - fees + funding`
decomposition, and the compounding of the per-bar returns to the ending equity. The
worst residuals over all 40 ledgers are: open cash `1.4e-14`, walk `1.8e-15`,
decomposition `3.9e-16`, funding reconciliation `3.2e-14`, compounding `1.3e-12`,
settlement quantity `0.0`, turnover units `0.0`. Every in-window settlement matches
an observed settlement of the raw series on the exact timestamp
(`max_settlement_offset_seconds = 0.0`); the canonical converted funding files
preserve the provider's millisecond offsets rather than snapping them, and the
in-range settlement counts are BTC 6 708, ETH 6 708, SOL 6 680, BNB 6 708 (26 804
across the four sleeves, with 1 888 pre-window settlements counted as out of range).
The one settlement that falls inside the first evaluated bar is recorded but charges
nothing, because the sleeve is still flat at that instant.

The audit is also run inside the evaluation itself
(`round2_results.json → physical_ledger_audit`), and the run refuses to write
results if any sleeve fails; the verifier is an independent second pass over the
published bytes.

---

## 6. Corrected gate statuses

Unchanged from v2 except where the physical ledger strengthens or weakens the
evidence wording. Gate 1 is `PASS` for the price leg and `BLOCKED` for
`CARD_C_FUNDING_R1`; Gate 2 is `PASS` for `EXPLORATORY_DONCHIAN_50` and `NOT_RUN`
for the bespoke rules; Gate 3 is `PASS`; Gate 4 is `BLOCKED` (no untouched OOS);
Gate 5 is `BLOCKED` (no spread/participation model and the funding notional is a
labelled price proxy, not a mark); Gate 6 is `NOT_RUN` (calendar years are not
regimes and §3.5 is post-hoc); Gate 7 is `BLOCKED` (no margin or liquidation
path); Gates 8 and 9 are `NOT_RUN`.

**No strategy passes the nine gates.** Every verdict is `EXPLORATORY`.

---

## 7. Commands run, in order, and results

| Step | Command | Exit / result |
| :-- | :-- | :-- |
| 1 | `python scripts\fetch_local_source_copies.py --verify` | 0; 37 entries, `all_copies_verified=True` |
| 2 | `python scripts\import_perp_data.py` | 0; legacy-converted Core4 |
| 3 | `python scripts\import_staged_batch.py --timeframes all --window-policy intersect` | 0; mark coverage 8/8 |
| 4 | `python scripts\build_inventory.py` | 0; 257 artifacts, 37 source entries |
| 5 | `python scripts\build_reports.py` | 0 |
| 6 | `python -m pytest tests -q` | **238 passed, 1 skipped** (v2: 224 passed) |
| 7 | `python scripts\evaluate_round2_strategies.py` | 0; run `round2v3_20260926T010145Z`, 40/40 sleeve audits pass |
| 8 | `python scripts\build_round2_validation_reports.py` | 0; ten nine-gate reports |
| 9 | `python scripts\verify_physical_ledger.py` | 0; **4/4** hard claims pass across 40 ledgers |
| 10 | `python scripts\verify_handoff_reconciliation.py` | 0; all six hard claims PASS, **31/31** CSV rows reproduced |
| 11 | `python scripts\verify_staging_handoff.py` | 0; all four hard claims PASS, 31 divergent bars, funding exact vs the frozen legacy copy |
| 12 | `.\.venv\Scripts\freqtrade.exe backtesting --config user_data\configs\config_futures_backtest.example.json --strategy ExploratoryDonchianFutures --timerange 20200811-20260924 --cache none` | 0; 1 340 trades, +31.98%, DD −73.53%, Sharpe 0.33 (identical to the Round-2 and v2 runs — the pipeline reproduces the canonical bytes exactly) |
| 13 | `.\.venv\Scripts\freqtrade.exe lookahead-analysis --config user_data\configs\config_futures_backtest.example.json --config scratch\lookahead_override.json --strategy ExploratoryDonchianFutures --timerange 20240101-20260924` | 0; `has_bias = No`, 20 signals, 0 biased entry/exit |

The canonical converted files were hashed before and after the pipeline and are
byte-identical, so none of the v3 numbers are a data change. Full verifier reports:
`archive/inventory/handoff_reconciliation.json`,
`archive/inventory/staging_verification.json` and
`archive/inventory/physical_ledger_verification.json`. Freqtrade logs:
`reports/strategy_validation/round2/freqtrade_backtest/{backtesting_run.log,lookahead_analysis.log}`.

> Sandbox note: inside the DSH file sandbox the pytest `tmp_path` tests need
> `TEMP=<abs>\.tmp`, `DSH_SANDBOX_MKDIR_COMPAT=1` and
> `PYTHONPATH=<workspace>\scratch\sandbox-compat`. A normal host needs none of it.

---

## 8. Remaining blockers

1. **No untouched OOS.** Gate 4 stays `BLOCKED`; the frozen window was inspected
   in legacy research.
2. **Funding-feature publish latency is unmeasured** (Gate 1 `BLOCKED` for
   `CARD_C_FUNDING_R1`).
3. **The funding notional is a labelled price proxy**, not a mark price: the local
   funding files carry no per-settlement `markPrice` (G13). This is a first-order
   limitation for a book whose funding drag dominates its gross (BTC).
4. **No spread, depth or participation model**; slippage is a flat sensitivity, not
   a cost curve (Gate 5 `BLOCKED`).
5. **No margin or liquidation path** (Gate 7 `BLOCKED`); 1× is never scaled up.
6. **Gate 6 is `NOT_RUN`**: the regime labels are post-hoc and must be pre-declared
   and rerun.
7. **Multiple comparisons.** Ten rules on a heavily inspected window; no
   deflated-Sharpe correction, so no positive cell is significant.
8. **The target/fee fixed point is one of several defensible conventions.** It is
   the one documented and solved here: exposure is measured on post-trade equity,
   and a constant 1× book therefore re-trades the small difference that each
   funding payment and price move creates. A different convention (for example
   measuring the target on pre-trade equity and leaving the fee as a permanent
   shortfall) would produce a different but equally documented turnover path. The
   convention is frozen in `study_spec_v3.json` and every consequence is reported
   (`max_target_exposure_gap`, `target_fixed_point_fallbacks`), but a reviewer
   should treat the baselines' 11 973 / 9 123 position changes as a property of the
   convention, not of any signal.
9. **The bar-level model remains a bar-level model**: every trade is at a bar open,
   there are no partial fills, and a settlement is valued at an interpolated trade
   price rather than a mark.

Nothing in this document is evidence that a signal or strategy has an edge, and no
result from this workspace may be presented as tradable.

---

## 9. What a reviewer should re-run

```text
python scripts\fetch_local_source_copies.py --verify
python scripts\import_perp_data.py
python scripts\import_staged_batch.py --timeframes all --window-policy intersect
python scripts\build_inventory.py
python scripts\build_reports.py
python -m pytest tests -q
python scripts\evaluate_round2_strategies.py
python scripts\build_round2_validation_reports.py
python scripts\verify_physical_ledger.py
python scripts\verify_handoff_reconciliation.py
python scripts\verify_staging_handoff.py
```

The four claims in §5 are the ones that decide whether the physical accounting is
sound; `scripts\verify_physical_ledger.py` exits non-zero if any of them fails.

---

## 10. Version history

| Version | Spec sha256 | Accounting | Status |
| :-- | :-- | :-- | :-- |
| v1 `round2_strategy_eval_20260925` | `a403a266…` | mean-of-four-returns portfolio, free 4h rebalance | withdrawn (v2) |
| v2 `round2_strategy_eval_20260925_v2_accounting` | `18bf9c0f…` | self-financing sleeves, drift-aware return series, linear break-even | **withdrawn (this document)** |
| v3 `round2_strategy_eval_20260925_v3_physical` | `24d9e45e…` | physical quantity/cash/equity ledger, event-time funding, full-ledger break-even | active, `EXPLORATORY` |

---

## 11. Preserved superseded evidence

* `reports/strategy_validation/round2/study_spec.json` — v1 frozen spec,
  byte-unchanged (sha256 `a403a266…`).
* `reports/strategy_validation/round2/study_spec_v2.json` — v2 frozen spec,
  byte-unchanged (sha256 `18bf9c0f…`).
* `docs/ROUND2_STRATEGY_NET_RETURN_EVALUATION.md` — v1 prose, superseded banner,
  otherwise unedited.
* `docs/ROUND2_ACCOUNTING_ERRATUM.md` — v2 prose, withdrawal banner added, otherwise
  unedited.
* `reports/strategy_validation/round2/superseded_v1/` — the ten v1 nine-gate reports,
  a v1-accounting machine-readable run and the v1 generated results document.
* `reports/strategy_validation/round2/superseded_v2/` — the v2 machine-readable run
  (`round2_results.json`), the v2 generated `ROUND2_RESULTS.md`, and all forty v2
  per-pair ledger CSVs, copied before the v3 run overwrote the live paths.
* `reports/strategy_validation/*_round2v2_20260925T212422Z.md` — the ten v2
  nine-gate reports, retained beside the v3 reports.

The v3 run writes to the same live paths the v2 run used, so the v2 artifacts in
`superseded_v2/` are the preserved bytes; the live `round2_results.json`,
`ROUND2_RESULTS.md` and `ledgers/` now hold the v3 run identified in this document
by `round2v3_20260926T010145Z`.
