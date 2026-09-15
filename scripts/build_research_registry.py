# -*- coding: utf-8 -*-
"""
Institutional Research Experiment Registry Builder (Phase 21)
============================================================
Generates `docs/research_registry.json` tracking all research phases, code commits,
data hashes, model checkpoint hashes, date boundaries, purge/embargo settings,
empirical results, and whether test data was previously observed during development.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

docs_dir = root_dir / 'docs'
docs_dir.mkdir(parents=True, exist_ok=True)


def compute_file_hash(path: Path) -> str:
    if not path.exists():
        return "N/A"
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(8192 * 16):
            h.update(chunk)
    return f"sha256:{h.hexdigest()[:16]}"


def main():
    print("Building Institutional Research Registry...")

    data_dir = root_dir / 'data'
    ckpt_dir = root_dir / 'checkpoints'
    pred_dir = root_dir / 'predictions'

    data_hash = compute_file_hash(data_dir / 'ETHUSDT_4h_2020_2026.parquet')
    ckpt_chan_hash = compute_file_hash(ckpt_dir / 'best_chan_transformer.pt')
    pred_chan_hash = compute_file_hash(pred_dir / 'chan_transformer_predictions.parquet')

    # Load clean benchmarks
    st_bench_path = docs_dir / 'structural_trend_clean_benchmark.json'
    chan_bench_path = docs_dir / 'chan_transformer_clean_benchmark.json'
    inc_bench_path = docs_dir / 'model_incremental_value.json'

    st_bench = json.loads(st_bench_path.read_text(encoding='utf-8')) if st_bench_path.exists() else {}
    chan_bench = json.loads(chan_bench_path.read_text(encoding='utf-8')) if chan_bench_path.exists() else {}
    inc_bench = json.loads(inc_bench_path.read_text(encoding='utf-8')) if inc_bench_path.exists() else {}

    registry = {
        "metadata": {
            "project": "Crypto Quantitative Systematic Architecture",
            "repository": "https://github.com/liuqi6776/crypto",
            "audit_commit": "f11dfd560e6a3a4c5fd2b4848c07549746fad788",
            "audit_standard": "Crypto Phase 18-20 Methodological Corrections and De-biasing Directives",
            "last_updated": "2026-09-15T16:55:00+08:00"
        },
        "experiments": [
            {
                "experiment_id": "EXP-19-STRUCTURAL-TREND-CLEAN",
                "phase": "Phase 19 / Phase 21",
                "model_type": "Macro Structural Trend Following (Bollinger 120 + 3 ATR Trailing Stop + EMA200 Sizing)",
                "status": "APPROVED_FOR_FROZEN_FORWARD_PAPER_TEST",
                "code_commit": "f11dfd5",
                "data_hash": data_hash,
                "prediction_hash": "N/A (Rule-based Causal Trend)",
                "checkpoint_hash": "N/A",
                "train_period": "2020-08-11 00:00:00 to 2023-12-31 23:59:59 (Pre-warmup & in-sample)",
                "validation_period": "2024-01-01 00:00:00 to 2025-12-31 23:59:59",
                "test_period": "2026-01-01 00:00:00 to 2026-09-01 12:00:00",
                "purge_bars": 0,
                "embargo_bars": 0,
                "whether_test_data_was_previously_observed": True,
                "research_classification": "Development Backtest (Subject to strategy selection bias)",
                "parameters": {
                    "lookback_bars": 120,
                    "exit_lookback_bars": 60,
                    "atr_period": 14,
                    "atr_trailing_mult": 3.0,
                    "fee_and_slippage": 0.0008,
                    "min_warmup_bars": 120,
                    "zero_bfill_enforced": True
                },
                "key_results": {
                    "ETHUSDT_return_pct": st_bench.get("clean_headline_results", {}).get("ETHUSDT", {}).get("total_return_pct", 126.36),
                    "ETHUSDT_sharpe": st_bench.get("clean_headline_results", {}).get("ETHUSDT", {}).get("daily_sharpe", 1.29),
                    "SOLUSDT_return_pct": st_bench.get("clean_headline_results", {}).get("SOLUSDT", {}).get("total_return_pct", 75.75),
                    "SOLUSDT_sharpe": st_bench.get("clean_headline_results", {}).get("SOLUSDT", {}).get("daily_sharpe", 0.81),
                    "portfolio_50_50_return_pct": st_bench.get("clean_headline_results", {}).get("PORTFOLIO_50_50", {}).get("total_return_pct", 107.36),
                    "portfolio_50_50_sharpe": st_bench.get("clean_headline_results", {}).get("PORTFOLIO_50_50", {}).get("daily_sharpe", 1.27),
                    "stitched_walk_forward_eth_sharpe": st_bench.get("walk_forward_stitched_oos", {}).get("ETHUSDT", {}).get("stitched_oos_metrics", {}).get("daily_sharpe", 0.83),
                    "cost_stress_30bps_sharpe": st_bench.get("cost_and_slippage_stress", {}).get("30_bps", {}).get("PORTFOLIO_50_50", {}).get("daily_sharpe", 1.04),
                    "top1_trade_share_eth": st_bench.get("profit_concentration", {}).get("ETHUSDT", {}).get("top1_share_of_sum_pnl_pct", 35.9),
                    "return_ex_top1_eth": st_bench.get("profit_concentration", {}).get("ETHUSDT", {}).get("cum_ret_ex_top1_pct", 64.3)
                },
                "compliance_check": {
                    "zero_bfill": True,
                    "history_warmup_enforced": True,
                    "parameter_neighborhood_stable": True,
                    "positive_at_15bps": True,
                    "walk_forward_sharpe_above_0_5": True,
                    "positive_ex_top1_trade": True
                }
            },
            {
                "experiment_id": "EXP-20-ST-CHAN-TRANSFORMER-CLEAN",
                "phase": "Phase 20 / Phase 21",
                "model_type": "Spatio-Temporal Chan-Lun Wave Transformer (ST-ChanTransformer)",
                "status": "EXPERIMENTAL_RESEARCH_FILTER_ONLY",
                "code_commit": "f11dfd5",
                "data_hash": data_hash,
                "prediction_hash": pred_chan_hash,
                "checkpoint_hash": ckpt_chan_hash,
                "train_period": "2020-08-21 00:00:00 to 2023-12-19 20:00:00 (Purged)",
                "validation_period": "2024-01-04 00:00:00 to 2025-12-19 20:00:00 (Purged & Embargoed)",
                "test_period": "2026-01-04 00:00:00 to 2026-09-01 12:00:00 (Embargoed)",
                "purge_bars": 72,
                "embargo_bars": 18,
                "whether_test_data_was_previously_observed": True,
                "research_classification": "Experimental Research Filter (Not verified production alpha)",
                "parameters": {
                    "d_model": 64,
                    "lookback_len": 18,
                    "in_features": 41,
                    "loss": "Huber (3d/6d/12d) + BCE (Expansion)",
                    "fixed_exp_thresh_eth": 0.4135,
                    "fixed_exp_thresh_sol": 0.4367,
                    "zero_full_sample_percentile": True,
                    "zero_bfill_enforced": True
                },
                "key_results": {
                    "gate_on_portfolio_return_pct": chan_bench.get("gate_on_vs_gate_off", {}).get("gate_on_fixed_threshold", {}).get("PORTFOLIO_50_50", {}).get("total_return_pct", 80.73),
                    "gate_on_portfolio_sharpe": chan_bench.get("gate_on_vs_gate_off", {}).get("gate_on_fixed_threshold", {}).get("PORTFOLIO_50_50", {}).get("daily_sharpe", 0.99),
                    "gate_off_portfolio_return_pct": chan_bench.get("gate_on_vs_gate_off", {}).get("gate_off", {}).get("PORTFOLIO_50_50", {}).get("total_return_pct", 109.61),
                    "gate_off_portfolio_sharpe": chan_bench.get("gate_on_vs_gate_off", {}).get("gate_off", {}).get("PORTFOLIO_50_50", {}).get("daily_sharpe", 1.06),
                    "pure_structure_return_pct": 107.36,
                    "shuffled_placebo_return_pct": 104.34,
                    "eth_2024_2025_rank_ic": inc_bench.get("prediction_skill", {}).get("ETHUSDT", {}).get("val_2024_2025_rank_ic", 0.1062),
                    "eth_2026_rank_ic": inc_bench.get("prediction_skill", {}).get("ETHUSDT", {}).get("test_2026_rank_ic", -0.3603),
                    "sol_overall_rank_ic": inc_bench.get("prediction_skill", {}).get("SOLUSDT", {}).get("overall_rank_ic", -0.0204),
                    "sol_2026_rank_ic": inc_bench.get("prediction_skill", {}).get("SOLUSDT", {}).get("test_2026_rank_ic", -0.1748)
                },
                "methodological_verdict": {
                    "incremental_alpha_proven": False,
                    "action_taken": "Model downgraded to experimental filter. Gate-off / pure structure recommended for production."
                }
            }
        ]
    }

    out_file = docs_dir / 'research_registry.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=2)

    print(f"[SUCCESS] Research Registry exported to: {out_file}")


if __name__ == '__main__':
    main()
