> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Round 3 — relative-strength signal training/validation study (Core4 P0)

**Run:** `round3_20260926T073318Z`　**Frozen spec:** `reports/strategy_validation/round3/study_spec_round3.json` (sha256 `de8a283d07208f70480d4d6e212d06b4ced34c11551c54fa646eb84bc744fd96`)
**Generated (UTC):** 2026-09-26T07:33:18Z
**Accounting:** `round2_v3_physical_quantity_cash_equity_ledger (reused unchanged)`　**Reused Round-2 spec:** `reports/strategy_validation/round2/study_spec_v3.json` (sha256 `24d9e45ecce9c12992a1d9c366c596212265c0f43f226092680e46af90fc3278`)

> **STATUS: EXPLORATORY. Nothing here is tradable, validated or a promise of future returns. No strategy passes the nine validation gates and no gate chain is promoted over an earlier unmet gate.** Gate 1 is `PASS` for the price leg and reported per sub-question for the cross-venue/funding legs; Gate 2 is `PASS` for the unchanged Round-2 `EXPLORATORY_DONCHIAN_50` baseline only; Gate 3 is `PASS`; Gate 4 is `BLOCKED` (no untouched window exists); Gate 5 is `BLOCKED`; Gate 6 is `NOT_RUN`; Gate 7 is `BLOCKED`; Gates 8 and 9 are `NOT_RUN`.

---

## 1. Pre-registered question, splits and costs

On the existing Core4 verified 4h Binance USDT-M perpetual data, and under a strictly causal, pre-registered feature set, does a coin relative-strength signal (BTC-relative return and 4-coin cross-sectional rank) add incremental net risk-adjusted value to the two existing Round-2 baselines EXPLORATORY_DONCHIAN_50 and CARD_B_TSMOM_EW - and what can honestly be said about the locally available OKX swap-candle and OKX funding research references?

### 1.1 Window plan (all three are development periods; none is an untouched Test)

| Role | Start (UTC) | End (UTC) | Label | Disclosure |
| :--- | :--- | :--- | :--- | :--- |
| train | 2020-08-11T00:00:00Z | 2023-12-31T20:00:00Z | `DEVELOPMENT_TRAIN` | already touched by legacy research and by this workspace |
| validation | 2024-01-01T00:00:00Z | 2025-12-31T20:00:00Z | `DEVELOPMENT_VALIDATION` | already touched; a held-out-for-reporting period, not an untouched OOS period |
| verdict | 2020-08-11T00:00:00Z | 2025-12-31T20:00:00Z | `DEVELOPMENT_TRAIN_PLUS_VALIDATION` | THE WINDOW THE FROZEN PRIMARY METRIC REFERS TO. Criteria (a), (d) and (e) are evaluated here and nowhere else. |
| diagnostic | 2026-01-01T00:00:00Z | 2026-09-24T20:00:00Z | `POST_HOC_DIAGNOSTIC_ONLY` | post-hoc only; never used for selection and never used in a verdict |
| development_full | 2020-08-11T00:00:00Z | 2026-09-24T20:00:00Z | `DEVELOPMENT_FULL_DISPLAY_ONLY` | reported for continuity with the v1 tables ONLY; because it contains the 2026 diagnostic window it enters no acceptance criterion. A v1 defect was that criteria (a),(d),(e) were computed on this window; see corrections_applied_in_v2. |

Every variant is a deterministic rule whose parameters were frozen in the spec before the run, so no window is used to fit anything. That removes the usual train/validation *fitting* channel but it does **not** make the validation window an untouched out-of-sample period: both the train and the validation windows have already been inspected in legacy research and in Rounds 1–2. Gate 4 therefore stays `BLOCKED` and the internal validation window is described as *held out for reporting*, never as untouched.

### 1.2 Cost scenarios

| Scenario | Fee bp/side | Slippage bp/side | Funding | Role |
| :--- | ---: | ---: | :--- | :--- |
| `primary` | 5 | 5 | observed | primary |
| `stress` | 10 | 5 | observed | stress |
| `maker_optimistic` | 2 | 0 | observed | optimistic_sensitivity |
| `zero_cost_no_funding` | 0 | 0 | excluded | gross_reference |

The primary cost is **taker 5 bp/side + 5 bp slippage/side + observed funding at 1× notional**; the stress scenario is **10 bp fee + 5 bp slippage + funding**. The `maker_optimistic` cell (2 bp, 0 slippage) is an **optimistic sensitivity only**: a maker fill is never assumed to be guaranteed, adverse selection and non-fills are not modelled, and that cell must not be read as attainable.

### 1.3 Experiment grid (frozen, 8 cells, nothing added or dropped after the run)

| # | Cell | Role | Base | Overlay / params |
| ---: | :--- | :--- | :--- | :--- |
| 1 | `EXPLORATORY_DONCHIAN_50` | baseline | — | `{"channel": 50, "ema_fast": 21, "ema_slow": 200}` |
| 2 | `CARD_B_TSMOM_EW` | baseline | — | `{"cap": 3.0, "lookbacks_days": [20, 50, 100, 200], "mode": "ew", "vol_target": 0.15, "vol_window": 120}` |
| 3 | `D50_RS_GATE_30` | candidate | EXPLORATORY_DONCHIAN_50 | `{"feature": "rs_ratio", "lookback_days": 30, "overlay": "gate", "weak_scale": 0.0}` |
| 4 | `D50_RS_SCALE_30` | diagnostic | EXPLORATORY_DONCHIAN_50 | `{"feature": "rs_ratio", "lookback_days": 30, "overlay": "gate", "weak_scale": 0.5}` |
| 5 | `D50_RS_GATE_90` | candidate | EXPLORATORY_DONCHIAN_50 | `{"feature": "rs_ratio", "lookback_days": 90, "overlay": "gate", "weak_scale": 0.0}` |
| 6 | `B_RS_GATE_30` | candidate | CARD_B_TSMOM_EW | `{"feature": "rs_ratio", "lookback_days": 30, "overlay": "gate", "weak_scale": 0.0}` |
| 7 | `B_RS_GATE_90` | candidate | CARD_B_TSMOM_EW | `{"feature": "rs_ratio", "lookback_days": 90, "overlay": "gate", "weak_scale": 0.0}` |
| 8 | `B_RS_RANK_90` | candidate | CARD_B_TSMOM_EW | `{"feature": "rs_rank", "lookback_days": 90, "overlay": "rank_gate", "weak_scale": 0.0}` |

**Overlay invariant.** Every overlay is a multiplier in `{0, 0.5, 1}` on the base target, so a variant can only hold, halve or flatten the baseline position: it never increases leverage and never opens a position the baseline did not ask for. Variant and baseline therefore run at an identical risk budget (1×) on an identical window with an identical cost grid, which is what makes the difference attributable to the overlay.

---

## 2. Relative-strength signal prerequisite

Feature: coin 4h close log return over *L* days minus BTC's, *L* ∈ [30, 90], measured on the **train+validation window** `2020-08-11T00:00:00Z → 2025-12-31T20:00:00Z` (`DEVELOPMENT_TRAIN_PLUS_VALIDATION`) because the signal prerequisite is part of the frozen acceptance rule. The label is the forward BTC-relative return starting at the **fill** instant `open_(t+2)` and running *L* days from there; it is a diagnostic label and never a feature. The 2026 diagnostic window is shown separately and never feeds the verdict.

**Label alignment (machine-checked):** the label of the feature at bar *t* starts at `open_(t+2)`, so for every row `label_start > feature_close`.

| L (days) | First label bar | Feature close (UTC) | Label start (UTC) | Label start − feature close | After feature close | Usable label bars |
| ---: | :--- | :--- | :--- | ---: | :--- | ---: |
| 30 | 2020-08-11T00:00:00Z | 2020-08-11T04:00:00Z | 2020-08-11T08:00:00Z | 0 days 04:00:00 | **True** | 13234 |
| 90 | 2020-08-11T00:00:00Z | 2020-08-11T04:00:00Z | 2020-08-11T08:00:00Z | 0 days 04:00:00 | **True** | 12874 |

| L (days) | Pooled Spearman IC | 95% time-block bootstrap CI | CI contains 0 | Effective n (from bootstrap) | Coins | Timestamps | Non-overlapping IC (n) | Confirmed |
| ---: | ---: | :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| 30 | 0.0197 | [-0.0814, 0.1265] | True | 366.9 | 4 | 11634 | 0.0343 (n=258) | no |
| 90 | 0.1146 | [-0.0609, 0.2768] | True | 138.2 | 4 | 11274 | 0.2119 (n=83) | no |

**Signal prerequisite verdict: `NO_MEASURABLE_SIGNAL`** (confirmed lookbacks: none).

* Frozen rule: while the pooled IC bootstrap CI contains 0 for every lookback, no overlay may be described as effective, whatever the P&L cell says
* Added requirement (post-hoc, applied on top of the frozen rule and disclosed as such): a lookback counts as a signal only if the non-overlapping subsample carries the same sign at |IC| >= 0.02; this requirement was added after the frozen run and is applied on top of, never instead of, the frozen rule
* the frozen rule and the added non-overlap requirement are both reported; a lookback whose CI excludes 0 while its non-overlapping estimate contradicts it is reported as unconfirmed rather than as evidence

* Estimator: pooled Spearman over all (coin, 4h timestamp) pairs.
* Bootstrap: circular block bootstrap over time on the same panel; the coin vector at each 4h timestamp is resampled as a unit and the pooled estimator is recomputed on the resampled panel; block 180 bars (30 days × 6 bars/day).
* Effective n is **derived from the bootstrap spread** (Fisher-z: `n_eff = 3 + 1/var(z)`), not asserted from an assumed inflation factor.
**Dependence, stated correctly.** The four coins are pooled, so the sample is not an independent cross-section. The four BTC-relative labels do **not** sum to zero: with `label_i = own_i − reference` the sum is `Σ own_i − 4·reference = −3·reference` because the reference (BTC) is itself one of the four coins. They are dependent because they share the BTC term, not because they cancel.

### 2.1 Per-year IC (pooled estimator, time-block bootstrap per year)

| L (days) | Year | IC | 95% CI | CI contains 0 | Timestamps | Observations |
| ---: | ---: | ---: | :--- | :--- | ---: | ---: |
| 30 | 2020 | 0.0902 | [n/a, n/a] | True | 678 | 2506 |
| 30 | 2021 | -0.0469 | [n/a, n/a] | True | 2190 | 8760 |
| 30 | 2022 | 0.0397 | [n/a, n/a] | True | 2190 | 8760 |
| 30 | 2023 | -0.0124 | [n/a, n/a] | True | 2190 | 8760 |
| 30 | 2024 | -0.2344 | [n/a, n/a] | True | 2196 | 8784 |
| 30 | 2025 | 0.1285 | [n/a, n/a] | True | 2190 | 8760 |
| 90 | 2020 | -0.8912 | [n/a, n/a] | True | 318 | 1066 |
| 90 | 2021 | 0.0272 | [n/a, n/a] | True | 2190 | 8760 |
| 90 | 2022 | 0.0298 | [n/a, n/a] | True | 2190 | 8760 |
| 90 | 2023 | 0.2550 | [n/a, n/a] | True | 2190 | 8760 |
| 90 | 2024 | 0.1848 | [n/a, n/a] | True | 2196 | 8784 |
| 90 | 2025 | -0.0216 | [n/a, n/a] | True | 2190 | 8760 |

### 2.2 Diagnostic-window IC (2026, display only — enters no verdict)

| L (days) | 2026 IC | Timestamps | Observations |
| ---: | ---: | ---: | ---: |
| 30 | -0.1604 | 1420 | 5680 |
| 90 | -0.0638 | 1060 | 4240 |

---

## 3. Result per variant — does the overlay add incremental value?

Incremental value is judged against the variant's **own** baseline on the identical **train+validation-only** window `2020-08-11T00:00:00Z → 2025-12-31T20:00:00Z` (`DEVELOPMENT_TRAIN_PLUS_VALIDATION`) at the primary cost. The 2026 diagnostic window enters **no** acceptance criterion. The frozen rule requires all of: **(a)** train+validation NET Sharpe improvement ≥ +0.15; **(b)** validation NET return > 0; **(c)** the 95% circular block-bootstrap CI of the validation per-bar net-return difference excludes 0 on the positive side; **(d)** the stress-scenario Sharpe improvement is not negative on the same train+validation window; **(e)** max drawdown is not worse than the baseline's by more than 5.00 pp on the same window. The risk-budget invariant **(f)** (the overlay never exceeds the base target) and the window rule **(g)** are asserted for every variant.

An earlier revision of this harness evaluated (a), (d) and (e) on the full window, which contains 2026. That violated the frozen split; it is corrected here and the superseded run is preserved under `superseded/`. The display-only full-window deltas are carried in the JSON as `development_sharpe_improvement_display_only_full_window` so the contamination is visible rather than hidden.

| Verdict | Variant | Baseline | ΔSharpe (train+val) | ΔSharpe (validation) | Val NET (variant) | Val NET (baseline) | Δstress Sharpe (train+val) | ΔmaxDD (pp, train+val) | Bootstrap CI (val) | p (uncorr.) | (a) | (b) | (c) | (d) | (e) | (f) | (g) |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- | ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DEFECTIVE_DID_NOT_TEST_THE_HYPOTHESIS** | `B_RS_RANK_90` | `CARD_B_TSMOM_EW` | 0.071 | -0.154 | -3.33% | -2.91% | 0.047 | 5.83 | [-0.821, 0.476] | 0.6430 | FAIL | FAIL | FAIL | PASS | PASS | PASS | PASS |
| **NO_INCREMENTAL_EFFECT** | `D50_RS_SCALE_30` | `EXPLORATORY_DONCHIAN_50` | 0.039 | -0.094 | -4.11% | -0.44% | 0.040 | 2.71 | [-0.354, 0.161] | 0.4825 | FAIL | FAIL | FAIL | PASS | PASS | PASS | PASS |
| **NO_INCREMENTAL_EFFECT** | `D50_RS_GATE_30` | `EXPLORATORY_DONCHIAN_50` | -0.001 | -0.237 | -9.54% | -0.44% | 0.010 | 3.31 | [-0.807, 0.350] | 0.4315 | FAIL | FAIL | FAIL | PASS | PASS | PASS | PASS |
| **NO_INCREMENTAL_EFFECT** | `D50_RS_GATE_90` | `EXPLORATORY_DONCHIAN_50` | -0.191 | -0.094 | -2.86% | -0.44% | -0.178 | 0.03 | [-0.855, 0.548] | 0.7975 | FAIL | FAIL | FAIL | FAIL | PASS | PASS | PASS |
| **NO_INCREMENTAL_EFFECT** | `B_RS_GATE_90` | `CARD_B_TSMOM_EW` | -0.196 | -0.286 | -5.08% | -2.91% | -0.165 | 4.63 | [-1.136, 0.447] | 0.4870 | FAIL | FAIL | FAIL | FAIL | PASS | PASS | PASS |
| **NO_INCREMENTAL_EFFECT** | `B_RS_GATE_30` | `CARD_B_TSMOM_EW` | -0.328 | -0.539 | -6.90% | -2.91% | -0.328 | 2.81 | [-1.481, 0.458] | 0.2885 | FAIL | FAIL | FAIL | FAIL | PASS | PASS | PASS |

### 3.1 Answer

**No variant met all of the frozen criteria.** Every relative-strength overlay is reported as `NO_INCREMENTAL_EFFECT`, `INSUFFICIENT_SAMPLE` or `DEFECTIVE_DID_NOT_TEST_THE_HYPOTHESIS` against its own Round-2 baseline. The per-criterion failure pattern is in the table above; section 5 records the concrete failures.

Verdict counts: `DEFECTIVE_DID_NOT_TEST_THE_HYPOTHESIS` × 1, `NO_INCREMENTAL_EFFECT` × 5.

---

## 4. Baselines and variants — per-window NET detail (primary cost)

Windows are reported separately. **`verdict`** is the train+validation window the frozen primary metric refers to; `train`, `validation` and `diagnostic` are the internal splits; `development_full` is train+validation+diagnostic and is **display only** — because it contains the 2026 post-hoc window it enters no acceptance criterion. Equity is rebased at each window's first bar, so the numbers are the window's own compounded NET return, not a slice of one global curve.

| Cell | Window | NET total | NET Sharpe | Max DD | Turnover sum | Fees sum | Funding sum | Bars |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `EXPLORATORY_DONCHIAN_50` | verdict | 149.42% | 0.631 | -42.26% | 347.6 | 0.3476 | -0.2933 | 11814 |
| `EXPLORATORY_DONCHIAN_50` | train | 150.52% | 0.843 | -42.26% | 217.7 | 0.2177 | -0.2732 | 7428 |
| `EXPLORATORY_DONCHIAN_50` | validation | -0.44% | 0.139 | -40.75% | 129.9 | 0.1299 | -0.0200 | 4386 |
| `EXPLORATORY_DONCHIAN_50` | diagnostic | 6.33% | 0.462 | -25.58% | 54.6 | 0.0546 | -0.0069 | 1601 |
| `EXPLORATORY_DONCHIAN_50` | development_full | 165.21% | 0.613 | -42.26% | 402.2 | 0.4022 | -0.3002 | 13415 |
| `CARD_B_TSMOM_EW` | verdict | 28.85% | 0.560 | -17.69% | 162.8 | 0.1628 | -0.0837 | 11814 |
| `CARD_B_TSMOM_EW` | train | 32.71% | 0.957 | -12.91% | 96.5 | 0.0965 | -0.0662 | 7428 |
| `CARD_B_TSMOM_EW` | validation | -2.91% | -0.116 | -17.69% | 66.3 | 0.0663 | -0.0175 | 4386 |
| `CARD_B_TSMOM_EW` | diagnostic | 6.10% | 0.846 | -7.81% | 27.0 | 0.0270 | -0.0010 | 1601 |
| `CARD_B_TSMOM_EW` | development_full | 36.71% | 0.597 | -17.69% | 189.8 | 0.1898 | -0.0847 | 13415 |
| `D50_RS_GATE_30` | verdict | 127.25% | 0.630 | -38.95% | 265.8 | 0.2658 | -0.2323 | 11814 |
| `D50_RS_GATE_30` | train | 151.23% | 0.921 | -38.95% | 163.9 | 0.1639 | -0.2234 | 7428 |
| `D50_RS_GATE_30` | validation | -9.54% | -0.097 | -31.25% | 101.9 | 0.1019 | -0.0089 | 4386 |
| `D50_RS_GATE_30` | diagnostic | -7.12% | -0.532 | -18.41% | 48.6 | 0.0486 | -0.0056 | 1601 |
| `D50_RS_GATE_30` | development_full | 111.07% | 0.548 | -38.95% | 314.4 | 0.3144 | -0.2379 | 13415 |
| `D50_RS_SCALE_30` | verdict | 151.17% | 0.670 | -39.55% | 305.6 | 0.3056 | -0.2612 | 11814 |
| `D50_RS_SCALE_30` | train | 161.92% | 0.931 | -39.55% | 190.0 | 0.1900 | -0.2466 | 7428 |
| `D50_RS_SCALE_30` | validation | -4.11% | 0.046 | -34.64% | 115.6 | 0.1156 | -0.0146 | 4386 |
| `D50_RS_SCALE_30` | diagnostic | -0.22% | 0.084 | -21.79% | 51.5 | 0.0515 | -0.0063 | 1601 |
| `D50_RS_SCALE_30` | development_full | 150.61% | 0.621 | -39.55% | 357.1 | 0.3571 | -0.2675 | 13415 |
| `D50_RS_GATE_90` | verdict | 54.27% | 0.440 | -42.23% | 207.3 | 0.2073 | -0.2190 | 11814 |
| `D50_RS_GATE_90` | train | 58.81% | 0.631 | -42.23% | 117.6 | 0.1176 | -0.2069 | 7428 |
| `D50_RS_GATE_90` | validation | -2.86% | 0.046 | -33.76% | 89.8 | 0.0898 | -0.0121 | 4386 |
| `D50_RS_GATE_90` | diagnostic | 6.47% | 0.643 | -12.91% | 30.1 | 0.0301 | -0.0051 | 1601 |
| `D50_RS_GATE_90` | development_full | 64.25% | 0.451 | -42.23% | 237.4 | 0.2374 | -0.2241 | 13415 |
| `B_RS_GATE_30` | verdict | 6.26% | 0.232 | -14.88% | 100.2 | 0.1002 | -0.0379 | 11814 |
| `B_RS_GATE_30` | train | 14.14% | 0.718 | -9.46% | 60.6 | 0.0606 | -0.0347 | 7428 |
| `B_RS_GATE_30` | validation | -6.90% | -0.656 | -14.88% | 39.6 | 0.0396 | -0.0031 | 4386 |
| `B_RS_GATE_30` | diagnostic | -0.29% | -0.031 | -6.77% | 21.1 | 0.0211 | -0.0013 | 1601 |
| `B_RS_GATE_30` | development_full | 5.96% | 0.196 | -14.88% | 121.3 | 0.1213 | -0.0392 | 13415 |
| `B_RS_GATE_90` | verdict | 10.76% | 0.364 | -13.06% | 82.4 | 0.0824 | -0.0451 | 11814 |
| `B_RS_GATE_90` | train | 16.69% | 0.869 | -8.06% | 45.9 | 0.0459 | -0.0381 | 7428 |
| `B_RS_GATE_90` | validation | -5.08% | -0.402 | -13.06% | 36.6 | 0.0366 | -0.0070 | 4386 |
| `B_RS_GATE_90` | diagnostic | 3.54% | 0.729 | -5.74% | 15.0 | 0.0150 | -0.0018 | 1601 |
| `B_RS_GATE_90` | development_full | 14.68% | 0.414 | -13.06% | 97.4 | 0.0974 | -0.0469 | 13415 |
| `B_RS_RANK_90` | verdict | 19.98% | 0.631 | -11.86% | 114.3 | 0.1143 | -0.0504 | 11814 |
| `B_RS_RANK_90` | train | 24.11% | 1.173 | -8.58% | 65.0 | 0.0650 | -0.0409 | 7428 |
| `B_RS_RANK_90` | validation | -3.33% | -0.270 | -11.86% | 49.4 | 0.0494 | -0.0095 | 4386 |
| `B_RS_RANK_90` | diagnostic | 1.89% | 0.471 | -5.48% | 16.9 | 0.0169 | -0.0012 | 1601 |
| `B_RS_RANK_90` | development_full | 22.25% | 0.611 | -11.86% | 131.3 | 0.1313 | -0.0515 | 13415 |

### 4.1 Per-year NET return (primary cost, full development window)

| Cell | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `EXPLORATORY_DONCHIAN_50` | 9.35% | 112.70% | -18.18% | 31.64% | 17.67% | -15.39% | 6.33% |
| `CARD_B_TSMOM_EW` | 7.46% | 15.76% | 1.79% | 4.81% | 1.80% | -4.63% | 6.10% |
| `D50_RS_GATE_30` | 3.89% | 135.55% | -17.87% | 25.00% | -4.50% | -5.28% | -7.12% |
| `D50_RS_SCALE_30` | 6.34% | 131.13% | -17.40% | 29.01% | 6.60% | -10.05% | -0.22% |
| `D50_RS_GATE_90` | -0.81% | 60.79% | -24.14% | 31.26% | 10.27% | -11.91% | 6.47% |
| `B_RS_GATE_30` | -2.06% | 12.11% | 2.14% | 1.77% | -6.61% | -0.31% | -0.29% |
| `B_RS_GATE_90` | -1.35% | 12.76% | 0.24% | 4.65% | -3.67% | -1.47% | 3.54% |
| `B_RS_RANK_90` | 2.31% | 12.70% | 1.31% | 6.25% | -2.87% | -0.47% | 1.89% |

### 4.2 Per-coin NET return over the full development window (primary cost)

Sleeve-level net return at each sleeve's own initial capital. `Weight` is the initial capital weight (0.25 each under the equal-weight convention).

| Cell | Pair | Weight | NET total | NET Sharpe | Max DD | Turnover sum | Funding sum |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `EXPLORATORY_DONCHIAN_50` | BTC/USDT:USDT | 0.25 | 24.61% | 0.275 | -51.32% | 400.9 | -0.2224 |
| `EXPLORATORY_DONCHIAN_50` | ETH/USDT:USDT | 0.25 | 23.37% | 0.299 | -64.03% | 397.1 | -0.3071 |
| `EXPLORATORY_DONCHIAN_50` | SOL/USDT:USDT | 0.25 | 98.06% | 0.514 | -74.40% | 441.5 | -0.6114 |
| `EXPLORATORY_DONCHIAN_50` | BNB/USDT:USDT | 0.25 | 514.81% | 0.854 | -50.12% | 390.8 | -0.1925 |
| `CARD_B_TSMOM_EW` | BTC/USDT:USDT | 0.25 | 35.42% | 0.481 | -24.02% | 222.1 | -0.1036 |
| `CARD_B_TSMOM_EW` | ETH/USDT:USDT | 0.25 | 24.32% | 0.361 | -22.34% | 173.7 | -0.1014 |
| `CARD_B_TSMOM_EW` | SOL/USDT:USDT | 0.25 | 49.20% | 0.621 | -23.27% | 133.0 | -0.0995 |
| `CARD_B_TSMOM_EW` | BNB/USDT:USDT | 0.25 | 37.91% | 0.493 | -29.87% | 235.7 | -0.0295 |
| `D50_RS_GATE_30` | BTC/USDT:USDT | 0.25 | 0.00% | n/a | 0.00% | 0.0 | 0.0000 |
| `D50_RS_GATE_30` | ETH/USDT:USDT | 0.25 | 1.11% | 0.195 | -52.05% | 360.2 | -0.1955 |
| `D50_RS_GATE_30` | SOL/USDT:USDT | 0.25 | 70.38% | 0.459 | -73.94% | 448.0 | -0.5993 |
| `D50_RS_GATE_30` | BNB/USDT:USDT | 0.25 | 372.79% | 0.830 | -60.53% | 316.4 | -0.1092 |
| `D50_RS_SCALE_30` | BTC/USDT:USDT | 0.25 | 21.76% | 0.275 | -27.72% | 200.9 | -0.1112 |
| `D50_RS_SCALE_30` | ETH/USDT:USDT | 0.25 | 16.03% | 0.260 | -56.16% | 379.2 | -0.2513 |
| `D50_RS_SCALE_30` | SOL/USDT:USDT | 0.25 | 95.80% | 0.499 | -74.00% | 445.0 | -0.6054 |
| `D50_RS_SCALE_30` | BNB/USDT:USDT | 0.25 | 468.86% | 0.880 | -52.82% | 353.8 | -0.1508 |
| `D50_RS_GATE_90` | BTC/USDT:USDT | 0.25 | 0.00% | n/a | 0.00% | 0.0 | 0.0000 |
| `D50_RS_GATE_90` | ETH/USDT:USDT | 0.25 | 18.42% | 0.251 | -52.43% | 278.7 | -0.1831 |
| `D50_RS_GATE_90` | SOL/USDT:USDT | 0.25 | 32.08% | 0.379 | -76.22% | 336.2 | -0.5906 |
| `D50_RS_GATE_90` | BNB/USDT:USDT | 0.25 | 206.50% | 0.699 | -43.26% | 258.1 | -0.1458 |
| `B_RS_GATE_30` | BTC/USDT:USDT | 0.25 | 0.00% | n/a | 0.00% | 0.0 | 0.0000 |
| `B_RS_GATE_30` | ETH/USDT:USDT | 0.25 | 4.04% | 0.116 | -26.33% | 152.4 | -0.0581 |
| `B_RS_GATE_30` | SOL/USDT:USDT | 0.25 | 19.77% | 0.331 | -26.15% | 127.4 | -0.0868 |
| `B_RS_GATE_30` | BNB/USDT:USDT | 0.25 | 0.02% | 0.046 | -32.71% | 196.0 | -0.0039 |
| `B_RS_GATE_90` | BTC/USDT:USDT | 0.25 | 0.00% | n/a | 0.00% | 0.0 | 0.0000 |
| `B_RS_GATE_90` | ETH/USDT:USDT | 0.25 | 9.63% | 0.207 | -18.18% | 118.9 | -0.0545 |
| `B_RS_GATE_90` | SOL/USDT:USDT | 0.25 | 42.29% | 0.597 | -24.47% | 106.7 | -0.0928 |
| `B_RS_GATE_90` | BNB/USDT:USDT | 0.25 | 6.78% | 0.166 | -21.27% | 156.2 | -0.0241 |
| `B_RS_RANK_90` | BTC/USDT:USDT | 0.25 | 26.67% | 0.525 | -12.61% | 146.2 | -0.0435 |
| `B_RS_RANK_90` | ETH/USDT:USDT | 0.25 | 2.65% | 0.092 | -28.42% | 124.7 | -0.0325 |
| `B_RS_RANK_90` | SOL/USDT:USDT | 0.25 | 57.28% | 0.740 | -20.88% | 109.7 | -0.0938 |
| `B_RS_RANK_90` | BNB/USDT:USDT | 0.25 | 2.39% | 0.088 | -20.36% | 149.6 | -0.0204 |

### 4.2b Structurally excluded sleeves (a confound, reported rather than hidden)

The BTC-relative gate compares each pair's relative strength against BTC. BTC is *also* a member of the traded universe, so BTC's own `rs_ratio` is identically zero and the gate rule (`> 0` for a long, `< 0` for a short, flat at exactly zero) makes BTC structurally ineligible for the whole window. That is a property of the reference/member overlap, not of any signal, and it is quantified here per variant: a sleeve with exactly 0.00% NET return over the window while its baseline sleeve returned more than 0% was never given a position.

| Cell | Sleeve | Own NET (primary) | Baseline sleeve NET | Baseline sleeve held? |
| :--- | :--- | ---: | ---: | :--- |
| `D50_RS_GATE_30` | BTC/USDT:USDT | 0.00% | 24.61% | no |
| `D50_RS_GATE_90` | BTC/USDT:USDT | 0.00% | 24.61% | no |
| `B_RS_GATE_30` | BTC/USDT:USDT | 0.00% | 35.42% | no |
| `B_RS_GATE_90` | BTC/USDT:USDT | 0.00% | 35.42% | no |

The rank gate does not have this property: BTC can rank in the top half and can be held. Any statement about the gate family must therefore carry the caveat that part of its measured cost is a structural zero on one of four sleeves. The rank variant `B_RS_RANK_90` is the cleanest read on relative strength itself for that reason, and it too fails the frozen criteria.

### 4.3 Overlay mechanics — how much of the book the overlay actually confirms

`Bars held at full` counts the base-position bars whose direction the feature **confirmed** (gate) or whose rank **permitted** (rank gate). It is the single most diagnostic number in this study: an overlay that confirms nothing is not a weak filter, it is a construction that never agrees with its base signal, and its P&L measures that incompatibility rather than the predictive power of the feature.

| Variant | Sleeves | Base-position bars | Bars held at full | Share held at full | Bars scaled down | Bars flattened by rank | Feature/rank missing | Never exceeds base? |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `D50_RS_GATE_30` | 4 | 14366 | **7516** | 52.32% | 6850 | 0 | 724 | True |
| `D50_RS_SCALE_30` | 4 | 14366 | **7516** | 52.32% | 6850 | 0 | 724 | True |
| `D50_RS_GATE_90` | 4 | 14366 | **6450** | 44.90% | 7916 | 0 | 2164 | True |
| `B_RS_GATE_30` | 4 | 42326 | **20812** | 49.17% | 21514 | 0 | 724 | True |
| `B_RS_GATE_90` | 4 | 42326 | **19938** | 47.11% | 22388 | 0 | 2164 | True |
| `B_RS_RANK_90` | 4 | 42326 | **0** | 0.00% | 0 | 18347 | 2782 | True |

**Degenerate construction, reported as a failure of the experiment design rather than as a signal result:** `B_RS_RANK_90` gave its base position **no confirmation on any bar of the entire window**. The rank gate requires a long exactly when the coin's cross-sectional relative strength ranks in the top half, but the base TSMOM target is itself a momentum vote; the two conditions are structurally opposed, so the overlay collapses the book to flat and the small residual return comes only from the handful of transition bars. The cell's verdict (`NO_INCREMENTAL_EFFECT`) is correct, but the reader must not read it as evidence *against* relative strength: the cell never actually tested relative strength as a directional signal. That experiment is still un-run.

The gate variants are different: they hold the base position at full size on roughly 45–52% of base-position bars and scale the rest, so they do deliver a real test of the feature. They confirm the feature is not additive here (criteria (a) and (b) fail), and the structural BTC exclusion in §4.2b accounts for part — not all — of their cost.

### 4.4 Trade statistics (pooled signed runs, full development window, primary cost)

| Cell | Round trips | Direct reversals | Pos. changes | Win rate | Profit factor | Worst trade | Worst MAE | Median MAE | Median MFE |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `EXPLORATORY_DONCHIAN_50` | 736 | 0 | 6518 | 34.92% | 1.355 | -16.15% | -18.05% | -2.17% | 2.62% |
| `CARD_B_TSMOM_EW` | 1302 | 80 | 13064 | 32.64% | 1.460 | -4.98% | -5.03% | -0.13% | 0.08% |
| `D50_RS_GATE_30` | 511 | 0 | 4742 | 38.94% | 1.405 | -21.05% | -21.73% | -1.73% | 2.12% |
| `D50_RS_SCALE_30` | 736 | 0 | 7013 | 34.65% | 1.396 | -16.15% | -18.05% | -1.40% | 1.71% |
| `D50_RS_GATE_90` | 397 | 0 | 3991 | 36.52% | 1.329 | -16.15% | -18.05% | -1.90% | 1.72% |
| `B_RS_GATE_30` | 977 | 0 | 11595 | 34.80% | 1.128 | -4.98% | -5.12% | -0.12% | 0.09% |
| `B_RS_GATE_90` | 746 | 0 | 10640 | 31.77% | 1.314 | -4.98% | -5.03% | -0.13% | 0.06% |
| `B_RS_RANK_90` | 988 | 0 | 12226 | 34.21% | 1.344 | -5.66% | -5.74% | -0.12% | 0.08% |

---

## 5. Cost sensitivity and explicit failures

Cost sensitivity is shown on the **train+validation (verdict) window**, the same window the acceptance criteria use.

| Cell | Primary NET | Primary Sharpe | Stress (10+5) NET | Stress Sharpe | Maker-optimistic (2+0) NET | Gross (0 bp, no funding) NET | Break-even bp/side |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `EXPLORATORY_DONCHIAN_50` | 149.42% | 0.631 | 109.84% | 0.548 | 228.94% | 368.94% | n/a |
| `CARD_B_TSMOM_EW` | 28.85% | 0.560 | 18.73% | 0.394 | 46.98% | 64.82% | n/a |
| `D50_RS_GATE_30` | 127.25% | 0.630 | 99.85% | 0.559 | 180.70% | 272.99% | n/a |
| `D50_RS_SCALE_30` | 151.17% | 0.670 | 115.93% | 0.589 | 220.43% | 339.95% | n/a |
| `D50_RS_GATE_90` | 54.27% | 0.440 | 39.69% | 0.370 | 81.61% | 136.36% | n/a |
| `B_RS_GATE_30` | 6.26% | 0.232 | 1.16% | 0.066 | 15.17% | 22.18% | n/a |
| `B_RS_GATE_90` | 10.76% | 0.364 | 6.29% | 0.230 | 18.44% | 26.05% | n/a |
| `B_RS_RANK_90` | 19.98% | 0.631 | 13.29% | 0.441 | 31.54% | 41.55% | n/a |

### 5.0 Display-only full-window view (contains 2026 — enters no verdict)

For continuity with the superseded v1 tables only. Because this window contains the 2026 post-hoc diagnostic period, none of it is used in any acceptance criterion.

| Cell | Full-window NET | Full-window Sharpe | ΔSharpe vs baseline (full) | ΔmaxDD pp (full) | ΔSharpe vs baseline (train+val, used) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `EXPLORATORY_DONCHIAN_50` | 165.21% | 0.613 | n/a | n/a | n/a |
| `CARD_B_TSMOM_EW` | 36.71% | 0.597 | n/a | n/a | n/a |
| `D50_RS_GATE_30` | 111.07% | 0.548 | -0.065 | 3.31 | -0.001 |
| `D50_RS_SCALE_30` | 150.61% | 0.621 | 0.008 | 2.71 | 0.039 |
| `D50_RS_GATE_90` | 64.25% | 0.451 | -0.162 | 0.03 | -0.191 |
| `B_RS_GATE_30` | 5.96% | 0.196 | -0.401 | 2.81 | -0.328 |
| `B_RS_GATE_90` | 14.68% | 0.414 | -0.183 | 4.63 | -0.196 |
| `B_RS_RANK_90` | 22.25% | 0.611 | 0.014 | 5.83 | 0.071 |

### 5.1 Failure list (every failed or unmet item, stated rather than dropped)

* `B_RS_RANK_90` vs `CARD_B_TSMOM_EW`: failed `a_development_sharpe_improvement_ge_0_15`, `b_validation_net_return_positive`, `c_bootstrap_ci_excludes_zero_positive` (verdict `DEFECTIVE_DID_NOT_TEST_THE_HYPOTHESIS`).
* `D50_RS_SCALE_30` vs `EXPLORATORY_DONCHIAN_50`: failed `a_development_sharpe_improvement_ge_0_15`, `b_validation_net_return_positive`, `c_bootstrap_ci_excludes_zero_positive` (verdict `NO_INCREMENTAL_EFFECT`).
* `D50_RS_GATE_30` vs `EXPLORATORY_DONCHIAN_50`: failed `a_development_sharpe_improvement_ge_0_15`, `b_validation_net_return_positive`, `c_bootstrap_ci_excludes_zero_positive` (verdict `NO_INCREMENTAL_EFFECT`).
* `D50_RS_GATE_90` vs `EXPLORATORY_DONCHIAN_50`: failed `a_development_sharpe_improvement_ge_0_15`, `b_validation_net_return_positive`, `c_bootstrap_ci_excludes_zero_positive`, `d_stress_sharpe_improvement_not_negative` (verdict `NO_INCREMENTAL_EFFECT`).
* `B_RS_GATE_90` vs `CARD_B_TSMOM_EW`: failed `a_development_sharpe_improvement_ge_0_15`, `b_validation_net_return_positive`, `c_bootstrap_ci_excludes_zero_positive`, `d_stress_sharpe_improvement_not_negative` (verdict `NO_INCREMENTAL_EFFECT`).
* `B_RS_GATE_30` vs `CARD_B_TSMOM_EW`: failed `a_development_sharpe_improvement_ge_0_15`, `b_validation_net_return_positive`, `c_bootstrap_ci_excludes_zero_positive`, `d_stress_sharpe_improvement_not_negative` (verdict `NO_INCREMENTAL_EFFECT`).
* **Signal prerequisite unmet**: the pooled relative-strength IC bootstrap CI contains zero for both lookbacks, so no overlay may be called effective even where a P&L criterion happened to pass.

### 5.2 Multiple-comparison and selection-bias disclosure

* Cells in the frozen family: **8** (2 unchanged baselines + 3 Donchian RS variants + 3 TSMOM RS variants).
* Correction: no deflated-Sharpe or Bonferroni-corrected promotion is applied; the bootstrap p-value is reported uncorrected and the family size (8) is stated next to every p-value so a reader can apply their own correction. With 6 candidate cells, an uncorrected p < 0.05 is NOT sufficient evidence.
* Selection bias: the train and validation windows have both been inspected before, in legacy research and in Rounds 1-2, so a positive validation cell here is a hypothesis about the past, not an out-of-sample discovery

### 5.3 Overlapping labels and effective sample

* The forward relative-strength labels overlap heavily (30- and 90-day labels on a 4h grid). Section 2 reports the block-bootstrap CI, the autocorrelation-adjusted effective daily sample and a non-overlapping subsample instead of a naive observation count.
* The P&L windows are *not* overlapping-label models: the ledger is a bar-by-bar physical book, so each bar's return is realised exactly once. The overlap problem applies to the **signal diagnostic**, not to the ledger arithmetic.
* Effective-sample numbers are quoted with every IC so a reader can see how thin the evidence is: four coins pooled over 6 years is not 6 years × 4 independent observations.

---

## 6. Physical-ledger audit

* Synthetic hand-computable reconciliation: **PASS** (funding ledger vs P&L funding abs. difference 0.000e+00; cash identity residual 0.000e+00; causality True; no early funding True).
* Every published primary-cost sleeve ledger is a real quantity/cash/equity book: `cash + quantity*price == equity_post_trade` at each open, funding charged only at observed settlement times on the quantity actually held, and the per-bar identity `net = gross - fees + funding`. The published CSVs under `ledgers/` carry every column needed to recompute those claims.
* Worst portfolio self-financing / decomposition residual across all 8 cells: **0.000e0** (reported per cell as `self_financing_residual`).
* Funding events outside the measured window are counted per sleeve (`funding_events_out_of_range`) and are never filled or extrapolated.

---

## 7. Reproduce

```text
python scripts\fetch_local_source_copies.py --verify
python scripts\import_perp_data.py
python scripts\import_staged_batch.py --timeframes all --window-policy intersect
python scripts\build_inventory.py
python scripts\build_reports.py
python -m pytest tests -q
python scripts\evaluate_round3_signals.py
python scripts\build_round3_validation_reports.py
```

The Round-2 pipeline commands in `docs/ROUND2_PHYSICAL_ACCOUNTING_ERRATUM_V3.md` §9 remain valid and unchanged; Round 3 rewrites none of its outputs.

---

## 8. What this does not establish

* No untouched out-of-sample window exists in this workspace: the train and validation windows have both already been inspected, so Gate 4 is BLOCKED and everything here is EXPLORATORY. This round makes no untouched-validation claim.
* The Core4 universe has four coins. A 4-coin cross-sectional rank is not a cross-sectional law: rank 1 of 4 is one coin, so no generalisable 'cross-sectional momentum' claim is made.
* Relative strength is defined against BTC only. BTC is both a member of the universe and the benchmark, so the four rs_ratio series are mechanically dependent (they share the BTC term; their BTC-relative labels do not sum to zero but to -3*reference) and the rank is a restatement of the same information.
* The rank-gate cell B_RS_RANK_90 is a DEFECTIVE construction in the v1/v2 runs (it confirmed the base target on zero bars), so it provides no evidence about relative strength; the feature remains untested in that direction.
* The OKX research reference carries close-only prices with no bid, ask, volume or depth, so no executable cross-venue return, basis PnL or arbitrage net-of-cost result can be computed; only a predictive diagnostic is reported.
* The cause of the measured +3h close-alignment offset between the OKX and Binance local series is UNKNOWN_AND_NOT_VERIFIABLE_LOCALLY; only the offset itself is measured.
* The OKX funding reference covers only 2026-06-08..2026-09-13, inside the post-hoc diagnostic period, so it cannot support an incremental-value claim.
* The funding notional is the labelled Round-2 open-to-open trade-price proxy, not a mark price: the local funding files carry no per-settlement markPrice (G13).
* No spread, depth or participation model exists; slippage is a flat sensitivity, never a cost curve.
* No margin or liquidation path is modelled; 1x is never scaled up.
* Multiple comparisons: 8 cells on heavily inspected windows with no deflated-Sharpe correction, so no positive cell is significant on its own.
* Overlapping labels: forward relative-strength labels over 30 and 90 days overlap heavily on a 4h grid; the IC uncertainty uses a time-block bootstrap on the same pooled panel estimator and an effective sample derived from the bootstrap spread.
* The bootstrap p-value assumes the per-bar return difference is stationary enough for a circular block bootstrap; it is a diagnostic, not a licence to promote.
* The regime analysis is not pre-declared in this round, so Gate 6 stays NOT_RUN.

Nothing in this document is evidence that a signal or strategy has an edge, and no result from this workspace may be presented as tradable.
