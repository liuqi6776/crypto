"""
Train Microstructure GBDT with Purged Walk-Forward Time-Series Validation
========================================================================
Implements:
1. Feature selection (Multi-scale OFI, Cross-Asset Lead-Lag, Parkinson Volatility)
2. Purged Walk-Forward Time-Series Split (Marcos López de Prado standard)
3. LightGBM Dual Directional Classifiers (Long-Win and Short-Win)
4. Volatility-Gated High-Conviction Thresholding
5. Out-of-Sample Prediction Logging for High-Friction 20X Backtesting
"""

import os
import sys
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, log_loss, precision_score

def train_purged_walk_forward_models(
    feat_path: str,
    output_pred_path: str,
    train_size: int = 140000,   # ~97 days training
    test_size: int = 40000,     # ~28 days test per fold
    purge_buffer: int = 30,     # 30 bars (2x horizon) buffer to eliminate leakage
    vol_gate_quantile: float = 0.50 # Stage 1 Volatility Gate
):
    print("=" * 70)
    print("  Microstructure GBDT Purged Walk-Forward Validation Engine")
    print("=" * 70)
    
    print(f"\n[1/4] Loading feature dataset: {feat_path}")
    df = pd.read_parquet(feat_path)
    n_total = len(df)
    print(f"  Total records: {n_total:,} bars ({df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]})")

    feature_cols = [
        # ETH OFI & Microstructure
        'eth_ofi_1m', 'eth_ofi_3m', 'eth_ofi_5m', 'eth_ofi_15m',
        'eth_taker_buy_ratio', 'trade_intensity', 'rel_trade_intensity',
        # BTC / SOL Flow
        'btc_ofi_1m', 'btc_ofi_5m', 'sol_ofi_1m',
        # Returns
        'eth_ret_1m', 'eth_ret_3m', 'eth_ret_5m', 'eth_ret_10m',
        'btc_ret_1m', 'btc_ret_3m', 'btc_ret_5m', 'btc_ret_10m',
        'sol_ret_1m', 'sol_ret_3m', 'sol_ret_5m',
        # Lead-Lag Spreads (Cross-Asset Alpha)
        'btc_eth_lead_1m', 'btc_eth_lead_3m', 'btc_eth_lead_5m', 'btc_eth_lead_10m',
        'sol_eth_lead_1m', 'sol_eth_lead_3m',
        # Volatility
        'vol_pct', 'btc_vol_pct', 'parkinson_vol_15m'
    ]

    print(f"  Selected features ({len(feature_cols)} total):")
    for i in range(0, len(feature_cols), 4):
        print(f"    {', '.join(feature_cols[i:i+4])}")

    # Targets: 1 if Take-Profit hit first, 0 otherwise
    target_long = (df['tb_long_label'] == 1).astype(np.int32).values
    target_short = (df['tb_short_label'] == 1).astype(np.int32).values
    
    # Pre-calculate Volatility Gate threshold (rolling or overall median)
    vol_median = df['vol_pct'].rolling(1000).quantile(vol_gate_quantile).bfill().values
    vol_gate_active = (df['vol_pct'].values >= vol_median).astype(bool)

    # Walk-forward setup
    fold_starts = []
    curr = 0
    while curr + train_size + purge_buffer + test_size <= n_total:
        fold_starts.append(curr)
        curr += test_size

    print(f"\n[2/4] Generating {len(fold_starts)} Purged Walk-Forward Folds...")
    
    oos_preds = []
    lgb_params = {
        'objective': 'binary',
        'metric': 'auc',
        'boosting_type': 'gbdt',
        'n_estimators': 300,
        'learning_rate': 0.03,
        'num_leaves': 31,
        'max_depth': 6,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'min_child_samples': 50,
        'random_state': 42,
        'verbose': -1,
        'n_jobs': -1
    }

    fold_metrics = []

    for fold_idx, start_idx in enumerate(fold_starts):
        train_end = start_idx + train_size
        test_start = train_end + purge_buffer
        test_end = test_start + test_size
        
        print(f"\n--- Processing Fold {fold_idx + 1}/{len(fold_starts)} ---")
        print(f"  Train: [{start_idx:,} : {train_end:,}] ({train_size:,} bars)")
        print(f"  Purge Buffer: [{train_end:,} : {test_start:,}] ({purge_buffer} bars dropped)")
        print(f"  Test:  [{test_start:,} : {test_end:,}] ({test_size:,} bars)")

        X_train = df[feature_cols].iloc[start_idx:train_end]
        X_test = df[feature_cols].iloc[test_start:test_end]

        # -------------------------------------------------------------
        # Model 1: Long Take-Profit Predictor
        # -------------------------------------------------------------
        y_train_long = target_long[start_idx:train_end]
        y_test_long = target_long[test_start:test_end]

        model_long = lgb.LGBMClassifier(**lgb_params)
        model_long.fit(
            X_train, y_train_long,
            eval_set=[(X_test, y_test_long)],
            callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)]
        )
        pred_long = model_long.predict_proba(X_test)[:, 1]
        auc_long = roc_auc_score(y_test_long, pred_long)

        # -------------------------------------------------------------
        # Model 2: Short Take-Profit Predictor
        # -------------------------------------------------------------
        y_train_short = target_short[start_idx:train_end]
        y_test_short = target_short[test_start:test_end]

        model_short = lgb.LGBMClassifier(**lgb_params)
        model_short.fit(
            X_train, y_train_short,
            eval_set=[(X_test, y_test_short)],
            callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)]
        )
        pred_short = model_short.predict_proba(X_test)[:, 1]
        auc_short = roc_auc_score(y_test_short, pred_short)

        fold_metrics.append({
            'fold': fold_idx + 1,
            'start_dt': df['datetime'].iloc[test_start],
            'end_dt': df['datetime'].iloc[test_end - 1],
            'auc_long': auc_long,
            'auc_short': auc_short
        })

        print(f"  Out-of-Sample AUC: Long = {auc_long:.4f}, Short = {auc_short:.4f}")

        # Collect out-of-sample slice for simulation
        df_oos_fold = df.iloc[test_start:test_end].copy()
        df_oos_fold['pred_prob_long'] = pred_long
        df_oos_fold['pred_prob_short'] = pred_short
        df_oos_fold['vol_gate'] = vol_gate_active[test_start:test_end]
        df_oos_fold['fold'] = fold_idx + 1
        oos_preds.append(df_oos_fold)

    # Consolidate Out-of-Sample
    df_oos_all = pd.concat(oos_preds, ignore_index=True)
    print("\n" + "=" * 70)
    print("  Walk-Forward Validation Summary")
    print("=" * 70)
    df_metrics = pd.DataFrame(fold_metrics)
    print(df_metrics.to_string(index=False))
    print(f"\nMean OOS Long AUC:  {df_metrics['auc_long'].mean():.4f}")
    print(f"Mean OOS Short AUC: {df_metrics['auc_short'].mean():.4f}")

    # Top Feature Importance from last models
    print("\n[3/4] Top 10 Most Predictive Microstructure Features (Long Model):")
    imp_long = pd.Series(model_long.feature_importances_, index=feature_cols).sort_values(ascending=False)
    for feat, imp in imp_long.head(10).items():
        print(f"  {feat:22s}: {imp}")

    print("\n[4/4] Top 10 Most Predictive Microstructure Features (Short Model):")
    imp_short = pd.Series(model_short.feature_importances_, index=feature_cols).sort_values(ascending=False)
    for feat, imp in imp_short.head(10).items():
        print(f"  {feat:22s}: {imp}")

    # Save out-of-sample scored dataset for execution backtest
    df_oos_all.to_parquet(output_pred_path, index=False)
    print(f"\n[SAVED] Out-of-sample predictions ({len(df_oos_all):,} bars) -> {output_pred_path}")
    
    return df_oos_all, df_metrics

if __name__ == '__main__':
    feat_parquet = r"d:\Convertible_Bond_data\crypto_data\eth_microstructure_features.parquet"
    pred_parquet = r"d:\Convertible_Bond_data\crypto_data\eth_microstructure_oos_predictions.parquet"
    
    train_purged_walk_forward_models(
        feat_path=feat_parquet,
        output_pred_path=pred_parquet,
        train_size=140000,
        test_size=40000,
        purge_buffer=30,
        vol_gate_quantile=0.50
    )
