# -*- coding: utf-8 -*-
"""
Train CryptoLeverageTransformer with Purged Walk-Forward Splits
20倍杠杆时空 Transformer 模型训练引擎（时序净化防未来函数、多任务联合收敛）
"""

import os
import sys
import time
import argparse
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from crypto_leverage_transformer import CryptoLeverageTransformer, LeverageMultiTaskLoss


class CryptoLeverageDataset(Dataset):
    """
    Rolling 60-bar lookback dataset for 4 assets simultaneously
    Tensor shape: (K=4, L=60, D)
    """
    def __init__(self, features: np.ndarray, gates: np.ndarray, tps: np.ndarray, sls: np.ndarray, roes: np.ndarray, lookback: int = 60, start_idx: int = 0, end_idx: int = None):
        self.lookback = lookback
        self.start_idx = max(start_idx, lookback)
        self.end_idx = len(features) if end_idx is None else end_idx
        self.valid_indices = np.arange(self.start_idx, self.end_idx)

        # features: (N, K, D)
        self.features = features
        self.gates = gates
        self.tps = tps
        self.sls = sls
        self.roes = roes

    def __len__(self):
        return len(self.valid_indices)

    def __getitem__(self, idx):
        t = self.valid_indices[idx]
        # Slice window: (L, K, D) -> transpose to (K, L, D)
        x = self.features[t - self.lookback:t, :, :] # (L, K, D)
        x = np.transpose(x, (1, 0, 2))                # (K, L, D)

        y_gate = self.gates[t]     # (K,)
        y_tp = self.tps[t]         # (K,)
        y_sl = self.sls[t]         # (K,)
        y_roe = self.roes[t]       # (K,)

        return (
            torch.from_numpy(x).float(),
            torch.from_numpy(y_gate).long(),
            torch.from_numpy(y_tp).float(),
            torch.from_numpy(y_sl).float(),
            torch.from_numpy(y_roe).float()
        )


def train_model(
    data_path: str = r"D:\Convertible_Bond_data\crypto_data\multi_asset_20x_leverage_dataset.npz",
    epochs: int = 12,
    batch_size: int = 128,
    lr: float = 5e-4,
    lookback: int = 60,
    checkpoint_dir: str = r"c:\Users\liuqi\crypto\checkpoints",
    export_only: bool = False
):
    print("=" * 75)
    print("  Training CryptoLeverageTransformer (20X Multi-Task Architecture)")
    print("=" * 75)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")

    # 1. Load Dataset
    print(f"\n[1/5] Loading multi-asset dataset: {data_path}")
    data = np.load(data_path, allow_pickle=True)
    features = data['features']       # (N, K=4, D=25)
    gates = data['gates']             # (N, K=4)
    tp_targets = data['tp_targets']   # (N, K=4)
    sl_targets = data['sl_targets']   # (N, K=4)
    roe_targets = data['roe_targets'] # (N, K=4)
    timestamps = data['timestamps']
    datetimes = data['datetimes']
    assets = data['assets']

    N, K, D = features.shape
    print(f"  Total bars: {N:,} | Assets: {K} | Features per asset: {D}")
    print(f"  Range: {datetimes[0]} to {datetimes[-1]}")

    # 2. Train / Val / Test Splits (Purged Walk-Forward)
    # Train: 0 -> 100,000 (with 60-bar embargo)
    # Val: 100,060 -> 120,000
    # Test: 120,060 -> 150,000 (OOS evaluation)
    train_end = 100000
    val_start = 100060
    val_end = 120000
    test_start = 120060
    test_end = N

    print(f"\n[2/5] Purged Walk-Forward Splits:")
    print(f"  Train: [{lookback} to {train_end:,}] ({datetimes[lookback]} -> {datetimes[train_end]})")
    print(f"  Val:   [{val_start:,} to {val_end:,}] ({datetimes[val_start]} -> {datetimes[val_end]})")
    print(f"  Test:  [{test_start:,} to {test_end:,}] ({datetimes[test_start]} -> {datetimes[test_end-1]})")

    # Feature Normalization: compute mean and std strictly on train split
    train_feats = features[lookback:train_end]
    mean = np.nanmean(train_feats, axis=(0, 1), keepdims=True)
    std = np.nanstd(train_feats, axis=(0, 1), keepdims=True)
    std[std < 1e-4] = 1.0

    features_norm = np.clip((features - mean) / std, -5.0, 5.0).astype(np.float32)

    # Class Weights for Gate Classification
    train_gates = gates[lookback:train_end].flatten()
    c_counts = np.bincount(train_gates, minlength=3)
    c_weights = (len(train_gates) / (3.0 * np.maximum(c_counts, 1))).astype(np.float32)
    print(f"  Class counts (Train): {c_counts.tolist()} -> Weights: {c_weights.round(3).tolist()}")
    class_weights_tensor = torch.from_numpy(c_weights).to(device)

    # Dataloaders
    train_ds = CryptoLeverageDataset(features_norm, gates, tp_targets, sl_targets, roe_targets, lookback=lookback, start_idx=lookback, end_idx=train_end)
    val_ds = CryptoLeverageDataset(features_norm, gates, tp_targets, sl_targets, roe_targets, lookback=lookback, start_idx=val_start, end_idx=val_end)
    test_ds = CryptoLeverageDataset(features_norm, gates, tp_targets, sl_targets, roe_targets, lookback=lookback, start_idx=test_start, end_idx=test_end)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    # 3. Initialize Model & Optimizer
    print(f"\n[3/5] Initializing CryptoLeverageTransformer...")
    model = CryptoLeverageTransformer(num_assets=K, in_features=D, lookback=lookback, d_model=64, n_heads=4).to(device)
    criterion = LeverageMultiTaskLoss(w_cls=1.0, w_tp=0.5, w_sl=0.5, w_roe=0.2, class_weights=class_weights_tensor).to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)

    os.makedirs(checkpoint_dir, exist_ok=True)
    best_ckpt_path = os.path.join(checkpoint_dir, "best_20x_leverage_transformer.pt")
    best_val_loss = float('inf')

    # 4. Training Loop
    if export_only and os.path.exists(best_ckpt_path):
        print(f"\n[4/5] Skipping training (export-only mode requested). Loading checkpoint: {best_ckpt_path}")
    else:
        print(f"\n[4/5] Training for {epochs} epochs...")
        for epoch in range(1, epochs + 1):
            model.train()
            train_loss = 0.0
            train_cls_acc = 0.0
            total_samples = 0

            t0 = time.time()
            for x, y_gate, y_tp, y_sl, y_roe in train_loader:
                x = x.to(device)
                y_gate = y_gate.to(device)
                y_tp = y_tp.to(device)
                y_sl = y_sl.to(device)
                y_roe = y_roe.to(device)

                optimizer.zero_grad()
                out = model(x)
                loss, l_dict = criterion(out, y_gate, y_tp, y_sl, y_roe)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), max_norm=2.0)
                optimizer.step()

                train_loss += loss.item() * len(x)
                preds = out['logits_gate'].argmax(dim=-1)
                train_cls_acc += (preds == y_gate).float().mean().item() * len(x)
                total_samples += len(x)

            scheduler.step()
            train_loss /= total_samples
            train_cls_acc /= total_samples

            # Validation
            model.eval()
            val_loss = 0.0
            val_cls_acc = 0.0
            val_samples = 0
            with torch.no_grad():
                for x, y_gate, y_tp, y_sl, y_roe in val_loader:
                    x = x.to(device)
                    y_gate = y_gate.to(device)
                    y_tp = y_tp.to(device)
                    y_sl = y_sl.to(device)
                    y_roe = y_roe.to(device)

                    out = model(x)
                    loss, _ = criterion(out, y_gate, y_tp, y_sl, y_roe)
                    val_loss += loss.item() * len(x)
                    preds = out['logits_gate'].argmax(dim=-1)
                    val_cls_acc += (preds == y_gate).float().mean().item() * len(x)
                    val_samples += len(x)

            val_loss /= val_samples
            val_cls_acc /= val_samples
            dt = time.time() - t0

            print(f"  Epoch {epoch:2d}/{epochs:2d} ({dt:.1f}s) | Train Loss: {train_loss:.4f}, Acc: {train_cls_acc*100:.1f}% | Val Loss: {val_loss:.4f}, Acc: {val_cls_acc*100:.1f}% | LR: {scheduler.get_last_lr()[0]:.2e}")

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                torch.save({
                    'epoch': epoch,
                    'model_state_dict': model.state_dict(),
                    'optimizer_state_dict': optimizer.state_dict(),
                    'val_loss': val_loss,
                    'val_acc': val_cls_acc,
                    'scaler_mean': mean,
                    'scaler_std': std,
                    'assets': assets,
                    'feature_dim': D,
                    'lookback': lookback
                }, best_ckpt_path)
                print(f"    -> [CHECKPOINT SAVED] Best Val Loss: {best_val_loss:.4f}")

    # 5. Out-of-Sample Inference & Export
    print(f"\n[5/5] Generating Out-of-Sample Predictions ({test_end - test_start:,} bars)...")
    checkpoint = torch.load(best_ckpt_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    oos_preds = []
    with torch.no_grad():
        for x, _, _, _, _ in test_loader:
            x = x.to(device)
            out = model(x)

            prob_gate = out['prob_gate'].cpu().numpy()       # (B, K, 3)
            pred_tp = out['pred_tp_pct'].cpu().numpy()        # (B, K)
            pred_sl = out['pred_sl_pct'].cpu().numpy()        # (B, K)
            pred_roe = out['pred_expected_roe'].cpu().numpy() # (B, K)

            for b in range(len(x)):
                oos_preds.append({
                    'prob_gate': prob_gate[b],
                    'pred_tp': pred_tp[b],
                    'pred_sl': pred_sl[b],
                    'pred_roe': pred_roe[b]
                })

    # Save OOS predictions with prices for backtest
    oos_indices = np.arange(test_start, test_end)
    out_oos_path = r"D:\Convertible_Bond_data\crypto_data\oos_20x_predictions.npz"
    np.savez_compressed(
        out_oos_path,
        prob_gate=np.stack([p['prob_gate'] for p in oos_preds]),
        pred_tp=np.stack([p['pred_tp'] for p in oos_preds]),
        pred_sl=np.stack([p['pred_sl'] for p in oos_preds]),
        pred_roe=np.stack([p['pred_roe'] for p in oos_preds]),
        timestamps=timestamps[oos_indices],
        datetimes=datetimes[oos_indices],
        prices=data['prices'][oos_indices],
        gates_true=gates[oos_indices],
        assets=assets
    )
    print(f"[COMPLETE] OOS predictions saved -> {out_oos_path}")
    return best_ckpt_path, out_oos_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-path', type=str, default=r"D:\Convertible_Bond_data\crypto_data\multi_asset_20x_leverage_dataset.npz")
    parser.add_argument('--epochs', type=int, default=10)
    parser.add_argument('--batch-size', type=int, default=128)
    parser.add_argument('--lr', type=float, default=5e-4)
    parser.add_argument('--export-only', action='store_true', help="Skip training and export OOS predictions using existing checkpoint")
    args = parser.parse_args()
    train_model(data_path=args.data_path, epochs=args.epochs, batch_size=args.batch_size, lr=args.lr, export_only=args.export_only)
