> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# TSMOM-30D v1 — validation report (2026-10-20)

**Verdict: `REJECTED` — not validated.** The 30-day time-series momentum candidate that looked
promising on the 4-symbol / 2022-2026 window does **not** survive an expanded universe,
an extended history, multiple-testing correction, or a forward check.

## Evidence

| Test | Result |
| :--- | :--- |
| Full sample, 20 symbols, 2020-02 → 2026-10 | +92 bp/week, ann +37.9%, Sharpe 0.85, t=2.19, raw p=0.028, max DD −50.3% |
| 4-symbol discovery universe, same window | +88 bp/week, Sharpe 0.76, t=1.94, raw p=0.052, max DD −76.7% |
| **2020–2021 (not used in discovery)** | +210 bp/week, ann +136%, Sharpe 1.57, t=2.18 |
| **2022–2024** | +60 bp/week, ann +18%, Sharpe 0.58, **t=1.00** |
| **2025–2026** | +19 bp/week, ann +0.7%, Sharpe 0.23, **t=0.31** |
| **BH correction over 24-cell grid** | **no cell significant (min q=0.258)** |
| **Forward check, 2026-10 (2 weekly periods)** | **−1015 bp (−10.1%)** |

## Gates

| Gate | Status | Evidence |
| :--- | :--- | :--- |
| 1 Data integrity | PASS | 20 symbols, Binance fapi 1d klines, per-file SHA256 in `research_data/tsmom_universe_v1/manifest.json` |
| 2 Implementation | PASS (scoped) | causal signals, Monday rebalance, next-week close settlement, 12 bp round trip |
| 3 Economic mechanism | PASS (hypothesis) | time-series momentum is a pre-existing, published effect |
| 4 Untouched OOS | **FAIL** | edge concentrated in 2020–2021; 2025–2026 flat (t=0.31); Oct 2026 forward −10.1% |
| 5 Costs / funding | PASS (partial) | 12 bp included; funding applied only for the 4 symbols with local 8h series |
| 6 Multiple testing | **FAIL** | 24-cell grid, Benjamini–Hochberg min q=0.258 |
| 7 Regime robustness | **FAIL** | works only in the 2020–2021 high-trend regime |
| 8 Leverage / margin | N/A | 1x notional, no leverage applied |
| 9 Observation | N/A | no dry-run, no orders |

## Conclusion

The candidate has **no demonstrated edge after 2021**. The apparent profitability on the original
4-symbol window was a combination of (a) a small universe, (b) a trending regime, and
(c) an uncorrected single hypothesis. It must not be called a strategy.

Reproduce: `python research/options_chain_2023_v1/code/validate_tsmom.py`
