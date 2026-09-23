# -*- coding: utf-8 -*-
"""
Moving Average Congestion Machine Learning Study Runner
均线密集交汇机器学习量化实证研究运行器
======================================================
Executes:
1. Event-driven sample collection on 5m Core-4 data (2024-2026).
2. Continuous feature engineering (order, 3/6/12 slopes, crosses, distance, taker volume).
3. Causal friction-deducted target labeling (1R SL, 2R TP, 12 bars max, fees/slips/funding).
4. Purged forward-rolling time-series cross-validation (5 folds, 12-bar purge window).
5. Four progressive groups: Baseline, Fixed Post-Congestion, Logistic Regression, XGBoost.
6. Probability decile calibration and net R expectancy audit.
7. Downstream leverage stress test gating.
"""

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from crypto_quant.data.intraday_manager import (
    load_intraday_symbol,
    CORE4_SYMBOLS,
    DEFAULT_INTRADAY_DIR,
)
from crypto_quant.ml.congestion_dataset import (
    extract_congestion_events,
    label_congestion_events,
)
from crypto_quant.ml.purged_cv import PurgedRollingTimeSeriesSplit
from crypto_quant.ml.models import (
    CongestionMLPipeline,
    evaluate_fixed_post_congestion_rule,
    compute_decile_table,
    summarize_model_metrics,
    FEATURE_COLUMNS,
)

REPORTS_DIR = os.path.join(project_root, "reports", "ma_ml")
os.makedirs(REPORTS_DIR, exist_ok=True)


def load_all_5m_data(ma_type: str = "EMA") -> Dict[str, pd.DataFrame]:
    """Load cached 5m datasets for Core-4."""
    dfs = {}
    for sym in CORE4_SYMBOLS:
        df = load_intraday_symbol(
            symbol=sym,
            interval="5m",
            market_type="spot",
            start_dt=pd.to_datetime("2024-01-01", utc=True),
        )
        dfs[sym] = df
    return dfs


def main():
    parser = argparse.ArgumentParser(description="Run MA Congestion Machine Learning Study Suite.")
    parser.add_argument("--ma-type", type=str, default="EMA", choices=["EMA", "SMA"], help="MA type (EMA or SMA)")
    parser.add_argument("--confidence-threshold", type=float, default=0.38, help="Confidence threshold to trigger action")
    parser.add_argument("--n-splits", type=int, default=5, help="Number of purged forward rolling folds")
    args = parser.parse_args()

    print("\n" + "="*80)
    print(f"STEP 1: EVENT EXTRACTION & FEATURE ENGINEERING (5m Core-4, {args.ma_type})")
    print("="*80)

    dfs = load_all_5m_data(ma_type=args.ma_type)
    all_events_list = []

    for sym, df in dfs.items():
        print(f"[EXTRACT] Extracting congestion events for {sym} (Total bars: {len(df)})...")
        evs = extract_congestion_events(
            df=df,
            symbol=sym,
            ma_type=args.ma_type,
            congestion_threshold=0.5,
            cooldown_bars=12,
            warmup_bars=200,
        )
        labeled = label_congestion_events(
            df=df,
            df_events=evs,
            holding_bars=12,
            spot_fee_rate=0.0008,
            futures_fee_rate=0.0005,
            exec_slip=0.0005,
            stop_slip=0.0015,
        )
        print(f"  -> Extracted & Labeled {len(labeled)} discrete events for {sym}.")
        all_events_list.append(labeled)

    df_all_events = pd.concat(all_events_list, ignore_index=True)
    df_all_events["timestamp"] = pd.to_datetime(df_all_events["timestamp"])
    df_all_events.sort_values("timestamp", inplace=True)
    df_all_events.reset_index(drop=True, inplace=True)

    print(f"\n[DATASET BUILT] Total Events across Core-4: {len(df_all_events)}")
    action_counts = df_all_events["action_label"].value_counts().to_dict()
    print(f"  -> Label Distribution: FLAT (0): {action_counts.get(0, 0)} | BUY (1): {action_counts.get(1, 0)} | SELL (2): {action_counts.get(2, 0)}")

    # Export dataset artifacts
    parquet_path = os.path.join(REPORTS_DIR, f"congestion_events_5m_{args.ma_type.lower()}.parquet")
    df_all_events.to_parquet(parquet_path)
    csv_path = os.path.join(REPORTS_DIR, f"congestion_events_5m_{args.ma_type.lower()}_head1000.csv")
    df_all_events.head(1000).to_csv(csv_path, index=False)
    print(f"[EXPORT] Saved full event dataset to {parquet_path}")

    # =========================================================================
    # STEP 2: PURGED FORWARD-ROLLING CROSS-VALIDATION
    # =========================================================================
    print("\n" + "="*80)
    print(f"STEP 2: PURGED FORWARD-ROLLING CROSS-VALIDATION ({args.n_splits} Expanding Folds)")
    print("="*80)

    cv = PurgedRollingTimeSeriesSplit(
        n_splits=args.n_splits,
        purge_bars=12,
        bar_duration_minutes=5,
        min_train_ratio=0.35,
    )

    oof_fixed_rule = []
    oof_lr = []
    oof_xgb = []
    fold_metrics = []

    fold_idx = 1
    for train_indices, test_indices in cv.split(df_all_events):
        train_df = df_all_events.iloc[train_indices].copy()
        test_df = df_all_events.iloc[test_indices].copy()

        train_start = train_df['timestamp'].min().strftime('%Y-%m-%d')
        train_end = train_df['timestamp'].max().strftime('%Y-%m-%d')
        test_start = test_df['timestamp'].min().strftime('%Y-%m-%d')
        test_end = test_df['timestamp'].max().strftime('%Y-%m-%d')

        print(f"\n--- FOLD {fold_idx}/{args.n_splits} ---")
        print(f"  Train: {train_start} to {train_end} ({len(train_df)} events)")
        print(f"  Purge Buffer: 60 minutes gap")
        print(f"  Test:  {test_start} to {test_end} ({len(test_df)} events)")

        # 1. Group 1: Fixed Post-Congestion Rule on Test Set
        eval_fixed = evaluate_fixed_post_congestion_rule(test_df)
        oof_fixed_rule.append(eval_fixed)

        # 2. Group 2: Calibrated Logistic Regression
        lr_pipe = CongestionMLPipeline(model_type="logistic_regression")
        lr_pipe.fit(train_df, train_df["action_label"])
        eval_lr = lr_pipe.evaluate_test_set(test_df, confidence_threshold=args.confidence_threshold)
        oof_lr.append(eval_lr)

        # 3. Group 3: Regularized XGBoost
        xgb_pipe = CongestionMLPipeline(model_type="xgboost")
        xgb_pipe.fit(train_df, train_df["action_label"])
        eval_xgb = xgb_pipe.evaluate_test_set(test_df, confidence_threshold=args.confidence_threshold)
        oof_xgb.append(eval_xgb)

        # Fold Summary Stats
        m_fixed = summarize_model_metrics(eval_fixed, f"FixedRule_Fold{fold_idx}")
        m_lr = summarize_model_metrics(eval_lr, f"LR_Fold{fold_idx}")
        m_xgb = summarize_model_metrics(eval_xgb, f"XGB_Fold{fold_idx}")

        print(f"  [Fold {fold_idx} FixedRule] Trades: {m_fixed['trades_taken']}, WinRate: {m_fixed['win_rate_pct']}%, Avg R: {m_fixed['avg_net_r']}")
        print(f"  [Fold {fold_idx} LogReg   ] Trades: {m_lr['trades_taken']}, WinRate: {m_lr['win_rate_pct']}%, Avg R: {m_lr['avg_net_r']}")
        print(f"  [Fold {fold_idx} XGBoost  ] Trades: {m_xgb['trades_taken']}, WinRate: {m_xgb['win_rate_pct']}%, Avg R: {m_xgb['avg_net_r']}")

        fold_metrics.append({
            "fold": fold_idx,
            "train_period": f"{train_start} to {train_end}",
            "test_period": f"{test_start} to {test_end}",
            "fixed_trades": m_fixed['trades_taken'], "fixed_winrate": m_fixed['win_rate_pct'], "fixed_avg_r": m_fixed['avg_net_r'],
            "lr_trades": m_lr['trades_taken'], "lr_winrate": m_lr['win_rate_pct'], "lr_avg_r": m_lr['avg_net_r'],
            "xgb_trades": m_xgb['trades_taken'], "xgb_winrate": m_xgb['win_rate_pct'], "xgb_avg_r": m_xgb['avg_net_r'],
        })
        fold_idx += 1

    df_oof_fixed = pd.concat(oof_fixed_rule, ignore_index=True)
    df_oof_lr = pd.concat(oof_lr, ignore_index=True)
    df_oof_xgb = pd.concat(oof_xgb, ignore_index=True)

    # Save fold breakdown CSV
    df_fold_summary = pd.DataFrame(fold_metrics)
    fold_csv = os.path.join(REPORTS_DIR, "rolling_folds_breakdown.csv")
    df_fold_summary.to_csv(fold_csv, index=False)

    # =========================================================================
    # STEP 3: FOUR-TIER PROGRESSIVE MODEL COMPARISON
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 3: FOUR-TIER PROGRESSIVE MODEL HIERARCHY COMPARISON")
    print("="*80)

    summary_fixed = summarize_model_metrics(df_oof_fixed, "Group 1: Fixed Post-Congestion Rule")
    summary_lr = summarize_model_metrics(df_oof_lr, "Group 2: Calibrated Logistic Regression")
    summary_xgb = summarize_model_metrics(df_oof_xgb, "Group 3: Regularized XGBoost")

    # Baseline 0 from previous 5m empirical study
    baseline_0 = {
        "model_name": "Group 0: Existing Strict Pullback Baseline (5m)",
        "total_events": len(df_oof_fixed),
        "trades_taken": 457,
        "trade_rate_pct": round((457 / len(df_oof_fixed)) * 100, 1),
        "win_rate_pct": 18.38,
        "avg_net_r": -0.966,
        "median_net_r": -1.554,
        "profit_factor": 0.26,
        "total_net_r": -441.46,
        "expectancy_status": "NEGATIVE",
    }

    comparison_rows = [baseline_0, summary_fixed, summary_lr, summary_xgb]
    df_comparison = pd.DataFrame(comparison_rows)
    comp_csv = os.path.join(REPORTS_DIR, "four_groups_comparison.csv")
    df_comparison.to_csv(comp_csv, index=False)
    print(df_comparison.to_string(index=False))

    # =========================================================================
    # STEP 4: PROBABILITY DECILE CALIBRATION & AUDIT
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 4: PROBABILITY DECILE EXPECTANCY AUDIT")
    print("="*80)

    decile_xgb = compute_decile_table(df_oof_xgb)
    decile_lr = compute_decile_table(df_oof_lr)

    decile_xgb_csv = os.path.join(REPORTS_DIR, "decile_analysis_xgboost.csv")
    decile_xgb.to_csv(decile_xgb_csv, index=False)
    decile_lr_csv = os.path.join(REPORTS_DIR, "decile_analysis_logistic_regression.csv")
    decile_lr.to_csv(decile_lr_csv, index=False)

    print("\n--- XGBoost Prediction Deciles (Decile 10 = Highest Confidence) ---")
    print(decile_xgb.to_string(index=False))

    print("\n--- Logistic Regression Prediction Deciles ---")
    print(decile_lr.to_string(index=False))

    # =========================================================================
    # STEP 5: LEVERAGE STRESS TEST GATE AUDIT
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 5: LEVERAGE STRESS TEST GATING AUDIT")
    print("="*80)

    top_decile = decile_xgb[decile_xgb["decile"] == 10]
    top_decile_mean_r = float(top_decile["mean_net_r"].iloc[0]) if not top_decile.empty else -999.0
    top_decile_winrate = float(top_decile["win_rate_pct"].iloc[0]) if not top_decile.empty else 0.0

    print(f"Top Decile (Decile 10) Realized Net R: {top_decile_mean_r:.3f} R, Win Rate: {top_decile_winrate:.2f}%")

    if top_decile_mean_r > 0.15:
        leverage_gate_status = "PASSED"
        print("[GATE: PASSED] Top decile achieved robust positive net R. Proceeding to leverage simulation.")
    else:
        leverage_gate_status = "FAILED"
        print("[GATE: STRICTLY BLOCKED] Top decile failed to produce positive net expectancy after all frictions.")
        print(">> EMPIRICAL CONCLUSION: Prohibit increasing leverage to amplify non-viable signals.")

    # =========================================================================
    # STEP 6: COMPILE BILINGUAL REPORT
    # =========================================================================
    md_content = ["# MA Congestion Machine Learning Research & State Classification Report"]
    md_content.append("# 均线密集交汇状态机器学习分类与期望值审计报告\n")
    md_content.append("> **Research Specification & Rigor / 科研规约与严谨性保证**:")
    md_content.append("> 1. **样本时间与因果隔离**: 事件在 K 线收盘时确立并提取 24 维特征；成交最早于 $T+1$ 开盘以市价可得报价撮合；绝不用事后回踩泄露交汇当时方向。")
    md_content.append("> 2. **全额扣除真实交易摩擦**: 现货双边 8 bps + 滑点，合约双边 5 bps + 滑点 + 8h 资金费率，严格记录真实 Net R。")
    md_content.append("> 3. **时间序列滚动净化验证**: 杜绝任何随机打散与 Shuffle；四币同刻切分，设置 12 根 K 线持仓净化缓冲带。")
    md_content.append("> 4. **杠杆门禁**: 1 倍名义本金下扣费后净 R 不为正，严禁上杠杆放大。\n")

    md_content.append("## 1. 四级递进模型体系横向对比 (Four-Tier Progressive Model Comparison)\n")
    md_content.append(df_comparison.to_markdown(index=False))

    md_content.append("\n\n## 2. 预测置信度十分位净期望值审计 (Decile Expectancy Audit - XGBoost)\n")
    md_content.append("将所有未见测试集样本按 XGBoost 模型预测置信度分为 10 档（Decile 10 为最高置信度）：\n")
    md_content.append(decile_xgb.to_markdown(index=False))

    md_content.append("\n\n## 3. 预测置信度十分位净期望值审计 (Decile Expectancy Audit - Logistic Regression)\n")
    md_content.append(decile_lr.to_markdown(index=False))

    md_content.append("\n\n## 4. 时间序列滚动净化切分逐折表现 (Purged Rolling Folds Breakdown)\n")
    md_content.append(df_fold_summary.to_markdown(index=False))

    md_content.append("\n\n## 5. 核心量化发现与杠杆门禁科学裁决 (Empirical Findings & Leverage Verdict)\n")
    md_content.append(f"### 门禁审计结果 / Gate Verdict: `{leverage_gate_status}`\n")
    md_content.append("### 发现 1：均线交汇事件本身无法直接预测未来方向 (No Directional Edge in Raw Congestion)")
    md_content.append(f"- **Group 1 (交汇后固定均线方向规则)**: 胜率仅 `{summary_fixed['win_rate_pct']}%`，平均净 R 为 `{summary_fixed['avg_net_r']} R`。")
    md_content.append("- 证明单纯的均线聚拢只代表短线波动率压缩，并无内在多空偏向；若在此阶段无脑跟风下单，将遭受严重的交易摩擦损耗。")

    md_content.append("\n### 发现 2：机器学习筛选器的过滤效力 (Feature Filtering & Non-Linear Signals)")
    md_content.append(f"- **Group 2 (逻辑回归)**: 过滤了 `{100 - summary_lr['trade_rate_pct']:.1f}%` 的无效交汇事件，但胜率仅为 `{summary_lr['win_rate_pct']}%`，平均净 R 为 `{summary_lr['avg_net_r']} R`。")
    md_content.append(f"- **Group 3 (XGBoost 树模型)**: 在未见测试集中，通过 24 维微观结构特征，交易胜率为 `{summary_xgb['win_rate_pct']}%`，平均净 R 为 `{summary_xgb['avg_net_r']} R`。")
    
    md_content.append("\n### 发现 3：十分位校准审计与结论 (Decile Calibration & Final Answer)")
    md_content.append(f"- 查看最高置信分组（Decile 10）的实际表现：平均净 R 为 `{top_decile_mean_r:.3f} R`，胜率为 `{top_decile_winrate:.2f}%`。")
    if top_decile_mean_r <= 0.15:
        md_content.append("- **科学结论**: 即便利用 24 维微观特征与最先进的梯度提升树模型，在扣除真实手续费（现货8bps/合约5bps）、滑点（5/15bps）与资金费后，**最高预测分数组在新数据中依然无法稳定取得正期望**。")
        md_content.append("- **严格执行验收标准**: **目前没有找到可用信号，坚决不得提高杠杆！** 任何在负期望状态下盲目放大名义杠杆的行为，均会成倍加速本金穿仓归零。")
    else:
        md_content.append("- **科学结论**: 最高预测分数组在时间序列滚动测试中展现出初步正期望，可进入下一阶段杠杆压力模拟。")

    report_path = os.path.join(REPORTS_DIR, "ML_RESEARCH_SUMMARY.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_content))
    print(f"\n[REPORT SAVED] {report_path}")


if __name__ == "__main__":
    main()
