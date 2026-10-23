> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 2025 CatBoost support-rebound development validation

This report is exploratory. 2025 was previously inspected and is not an untouched test. No 2026 numeric values are used.

Protocol SHA256: `8b98e9159628482f15a1bb6e8770f922b6775f744fb14afeec972669bc3db2c3`

## Locked 5 bp/side results

Per-coin H1/H2/full metrics, 2 bp/side sensitivity, and event-level predictions are in the linked CSV artifacts.

| Configuration | Coin | Window | N | Net return | PF | MDD | Win rate | Mean/trade | Worst month | Worst trade |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| F0 | BTC | full_2025 | 7 | -0.4065% | 0.8465919463225837 | -1.4400% | 0.42857142857142855 | -0.0005548989277396977 | 2025-11 | -0.010457194367929084 |
| F0 | ETH | full_2025 | 13 | -1.3620% | 0.7813587786020275 | -2.9835% | 0.5384615384615384 | -0.0009995535723548302 | 2025-11 | -0.021840522794006237 |
| F0 | SOL | full_2025 | 26 | -2.1168% | 0.8917344083380256 | -7.7342% | 0.46153846153846156 | -0.0007059017530114275 | 2025-12 | -0.027835217646881447 |
| F0 | BNB | full_2025 | 8 | -4.5791% | 0.15837731162789767 | -4.5918% | 0.375 | -0.005809087086037218 | 2025-11 | -0.01849275461401351 |
| F1 | BTC | full_2025 | 14 | -4.5868% | 0.2473087031250653 | -4.9701% | 0.2857142857142857 | -0.0033322217585484105 | 2025-02 | -0.012391088512159002 |
| F1 | ETH | full_2025 | 27 | -6.1725% | 0.5212066160109379 | -6.1725% | 0.37037037037037035 | -0.002315284758915873 | 2025-11 | -0.021840522794006237 |
| F1 | SOL | full_2025 | 59 | -1.9775% | 0.9349494964112992 | -10.3717% | 0.4745762711864407 | -0.00027871794966794085 | 2025-10 | -0.018556414098647323 |
| F1 | BNB | full_2025 | 17 | -3.0660% | 0.5648000004136127 | -3.5768% | 0.6470588235294118 | -0.0017966335889271106 | 2025-11 | -0.01849275461401351 |
| F2 | BTC | full_2025 | 383 | -28.2866% | 0.5364584687300801 | -30.4833% | 0.370757180156658 | -0.000861008518545056 | 2025-02 | -0.012391088512159002 |
| F2 | ETH | full_2025 | 388 | -26.0395% | 0.7041159224960728 | -26.4685% | 0.44587628865979384 | -0.0007598343889407263 | 2025-11 | -0.021840522794006237 |
| F2 | SOL | full_2025 | 364 | -27.4945% | 0.7421725986960229 | -37.1881% | 0.44505494505494503 | -0.0008515748489517266 | 2025-05 | -0.027835217646881447 |
| F2 | BNB | full_2025 | 368 | -33.4443% | 0.5192376996731212 | -33.5108% | 0.38858695652173914 | -0.0010951055204104093 | 2025-03 | -0.02419456074032466 |
| baseline_strength_all | BTC | full_2025 | 390 | -30.6502% | 0.5146180878168712 | -32.4240% | 0.37435897435897436 | -0.0009306929648207512 | 2025-11 | -0.022366605385418476 |
| baseline_strength_all | ETH | full_2025 | 407 | -28.9057% | 0.6865661412680053 | -29.3180% | 0.44226044226044225 | -0.000820353562535364 | 2025-01 | -0.021840522794006237 |
| baseline_strength_all | SOL | full_2025 | 406 | -28.6917% | 0.7590261995277924 | -39.8920% | 0.4482758620689655 | -0.0008007472986394978 | 2025-05 | -0.027835217646881447 |
| baseline_strength_all | BNB | full_2025 | 393 | -33.2840% | 0.5499175705103868 | -33.5820% | 0.3994910941475827 | -0.0010183686098270194 | 2025-03 | -0.02419456074032466 |
| body_engulf_4h_strength | BTC | full_2025 | 17 | 1.4610% | 2.052528254436436 | -0.7496% | 0.5882352941176471 | 0.0008586529846588553 | 2025-12 | -0.007496201656664333 |
| body_engulf_4h_strength | ETH | full_2025 | 22 | -4.3777% | 0.3120313526665966 | -4.8633% | 0.3181818181818182 | -0.0020226046973593793 | 2025-10 | -0.013295698566439505 |
| body_engulf_4h_strength | SOL | full_2025 | 25 | 7.3754% | 2.427938881793423 | -2.3978% | 0.64 | 0.0029132540459424617 | 2025-09 | -0.01310461085118997 |
| body_engulf_4h_strength | BNB | full_2025 | 25 | -3.2813% | 0.3501849798320885 | -3.3129% | 0.4 | -0.001328246371210777 | 2025-04 | -0.008612671214529325 |

## Predictive and ledger increments

F1−F0 and F2−F1 comparisons are paired on the same retained event universe for prediction metrics. Ledger trade counts/exposure may differ because fixed thresholds select different events; consult the incremental comparison CSV.

## Provenance and limitations

2024 warm-up only supports causal features; 2025 events/fills/exits only. Labels crossing 2026 are censored. Funding is a prior observed feature only; funding cashflows, spread, slippage and execution fills are absent. Net costs are fixed 2/5 bp per side price-only proxies.

Local artifacts:

- dev25_v4_event_predictions.csv (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/support_rebound_mtf/catboost_meta_dev_2025_v4/dev25_v4_event_predictions.csv`)
- dev25_v4_ledger_metrics.csv (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/support_rebound_mtf/catboost_meta_dev_2025_v4/dev25_v4_ledger_metrics.csv`)
- dev25_v4_prediction_metrics.csv (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/support_rebound_mtf/catboost_meta_dev_2025_v4/dev25_v4_prediction_metrics.csv`)
- dev25_v4_trades.csv (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/support_rebound_mtf/catboost_meta_dev_2025_v4/dev25_v4_trades.csv`)
- dev25_v4_event_diagnostics.csv (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/support_rebound_mtf/catboost_meta_dev_2025_v4/dev25_v4_event_diagnostics.csv`)
- dev25_v4_funding_coverage_all_events.csv (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/support_rebound_mtf/catboost_meta_dev_2025_v4/dev25_v4_funding_coverage_all_events.csv`)
- dev25_v4_htf_timing_audit.csv (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/support_rebound_mtf/catboost_meta_dev_2025_v4/dev25_v4_htf_timing_audit.csv`)
- dev25_v4_prediction_comparison.csv (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/support_rebound_mtf/catboost_meta_dev_2025_v4/dev25_v4_prediction_comparison.csv`)
- dev25_v4_ledger_comparison.csv (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/support_rebound_mtf/catboost_meta_dev_2025_v4/dev25_v4_ledger_comparison.csv`)
- dev25_v4_funding_coverage_retained.csv (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/support_rebound_mtf/catboost_meta_dev_2025_v4/dev25_v4_funding_coverage_retained.csv`)
- dev25_v4_censored_events.csv (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/support_rebound_mtf/catboost_meta_dev_2025_v4/dev25_v4_censored_events.csv`)
- Frozen protocol (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/support_rebound_mtf/catboost_meta_dev_2025_v4/protocol_dev_2025_v4.json`)
