# -*- coding: utf-8 -*-
"""
Train CryptoLeverageTransformer on 2020 - 2025/06 Full Multi-Year Horizon
针对 2020 至 2025年6月 全量跨周期历史数据的 Transformer 深度模型训练引擎
"""

import os
import sys
import time
import argparse
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from crypto_leverage_transformer import CryptoLeverageTransformer, LeverageMultiTaskLoss


class StrideCryptoDataset(Dataset):
    """
    Uniform-stride multi-year high-frequency dataset
    Ensures complete multi-year temporal coverage with zero lookahead bias
    """
    def __init__(self, features: np.ndarray, gates: np.ndarray, tps: np.ndarray, sls: np.ndarray, roes: np.ndarray, indices: np.ndarray, lookback: int = 60, stride: int = 4):
        self.lookback = lookback
        valid_mask = indices >= lookback
        self.indices = indices[valid_mask][::stride]
        self.features = features
        self.gates = gates
        self.tps = tps
        self.sls = sls
        self.roes = roes

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, idx):
        t = self.indices[idx]
        x = self.features[t - self.lookback:t, :, :] # (L, K, D)
        x = np.transpose(x, (1, 0, 2))                # (K, L, D)

        y_gate = self.gates[t]
        y_tp = self.tps[t]
        y_sl = self.sls[t]
        y_roe = self.roes[t]

        return (
            torch.from_numpy(x).float(),
            torch.from_numpy(y_gate).long(),
            torch.from_numpy(y_tp).float(),
            torch.from_numpy(y_sl).float(),
            torch.from_numpy(y_roe).float()
        )


def train_full_model(
    data_path: str = r"D:\Convertible_Bond_data\crypto_data\multi_asset_full_2020_2026.npz",
    epochs: int = 8,
    batch_size: int = 256,
    lr: float = 6e-4,
    lookback: int = 60,
    stride: int = 4,
    checkpoint_dir: str = r"c:\Users\liuqi\crypto\checkpoints"
):
    print("=" * 80)
    print("  Training CryptoLeverageTransformer on 2020 - 2025/06 Full Horizon")
    print("=" * 80)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")

    # 1. Load Data
    print(f"\n[1/4] Loading full multi-year archive: {data_path}...")
    data = np.load(data_path, allow_pickle=True)
    features = data['features']
    gates = data['gates']
    tp_targets = data['tp_targets']
    sl_targets = data['sl_targets']
    roe_targets = data['roe_targets']
    datetimes = data['datetimes']
    train_indices = data['train_indices']
    val_indices = data['val_indices']
    assets = data['assets']

    N, K, D = features.shape
    print(f"  Total bars: {N:,} | Assets: {K} | Features: {D}")
    print(f"  Train: [{train_indices[0]} to {train_indices[-1]:,}] ({datetimes[train_indices[0]]} -> {datetimes[train_indices[-1]]})")
    print(f"  Val:   [{val_indices[0]:,} to {val_indices[-1]:,}] ({datetimes[val_indices[0]]} -> {datetimes[val_indices[-1]]})")

    # 2. Scaler fitted strictly on Train Split
    train_feats = features[train_indices]
    mean = np.nanmean(train_feats, axis=(0, 1), keepdims=True)
    std = np.nanstd(train_feats, axis=(0, 1), keepdims=True)
    std[std < 1e-4] = 1.0
    features_norm = np.clip((features - mean) / std, -5.0, 5.0).astype(np.float32)

    # Class Weights for Train Split
    train_gates = gates[train_indices].flatten()
    c_counts = np.bincount(train_gates, minlength=3)
    c_weights = (len(train_gates) / (3.0 * np.maximum(c_counts, 1))).astype(np.float32)
    print(f"  Train Class counts: {c_counts.tolist()} -> Weights: {c_weights.round(3).tolist()}")
    class_weights = torch.from_numpy(c_weights).to(device)

    # Dataloaders
    # Validation split uses stride 5 for fast evaluation during training
    val_sub_indices = val_indices[::5]
    train_ds = StrideCryptoDataset(features_norm, gates, tp_targets, sl_targets, roe_targets, train_indices, lookback=lookback, stride=stride)
    val_ds = StrideCryptoDataset(features_norm, gates, tp_targets, sl_targets, roe_targets, val_sub_indices, lookback=lookback, stride=1)

    print(f"  Train samples per epoch (stride={stride}): {len(train_ds):,}")
    print(f"  Val samples per epoch: {len(val_ds):,}")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    # 3. Model & Optimizer
    print(f"\n[2/4] Initializing CryptoLeverageTransformer...")
    model = CryptoLeverageTransformer(num_assets=K, in_features=D, lookback=lookback, d_model=64, n_heads=4).to(device)
    criterion = LeverageMultiTaskLoss(w_cls=1.0, w_tp=0.5, w_sl=0.5, w_roe=0.2, class_weights=class_weights).to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)

    os.makedirs(checkpoint_dir, exist_ok=True)
    best_ckpt_path = os.path.join(checkpoint_dir, "best_transformer_2020_2025.pt")
    best_val_loss = float('inf')

    # 4. Training Loop
    print(f"\n[3/4] Training across 2020-2025/06 for {epochs} epochs...")
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
            loss, _ = criterion(out, y_gate, y_tp, y_sl, y_roe)
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

    print(f"\n[4/4] Model training complete! Saved to {best_ckpt_path}")
    return best_ckpt_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-path', type=str, default=r"D:\Convertible_Bond_data\crypto_data\multi_asset_full_2020_2026.npz")
    parser.add_argument('--epochs', type=int, default=8)
    parser.add_argument('--batch-size', type=int, default=256)
    parser.add_argument('--lr', type=float, default=6e-4)
    parser.add_argument('--stride', type=int, default=4)
    args = parser.parse_args()
    train_full_model(data_path=args.data_path, epochs=args.epochs, batch_size=args.batch_size, lr=args.lr, stride=args.stride)
