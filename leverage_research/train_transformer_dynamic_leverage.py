"""
Train CryptoLeverageTransformerWithPolicy on Pre-2026/05 Training Set.
Optimizes Direction, Take-Profit, Stop-Loss, and Self-Adaptive Leverage (0X-75X)
via Differentiable Sharpe Ratio Loss on GPU.
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
from crypto_leverage_transformer_with_policy import (
    CryptoLeverageTransformerWithPolicy,
    DifferentiableSharpeLeverageLoss
)

class StrideCryptoDataset(Dataset):
    def __init__(
        self,
        features: np.ndarray,
        gates: np.ndarray,
        tps: np.ndarray,
        sls: np.ndarray,
        roes: np.ndarray,
        indices: np.ndarray,
        lookback: int = 60,
        stride: int = 4
    ):
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
        x = self.features[t - self.lookback:t, :, :]  # (L, K, D)
        x = np.transpose(x, (1, 0, 2))                 # (K, L, D)

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

def train_dynamic_leverage_model(
    data_path: str = r"D:\Convertible_Bond_data\crypto_data\multi_asset_split_2026_05.npz",
    epochs: int = 5,
    batch_size: int = 512,
    lr: float = 5e-4,
    lookback: int = 60,
    stride: int = 4,
    checkpoint_dir: str = r"c:\Users\liuqi\crypto\checkpoints"
):
    print("=" * 85)
    print("  Training CryptoLeverageTransformerWithPolicy (End-to-End Optimal Leverage)")
    print(f"  Dataset: {data_path}")
    print(f"  Epochs: {epochs} | Batch Size: {batch_size} | Stride: {stride}")
    print("=" * 85)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Target Computing Device: {device}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)} (VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB)")

    # 1. Load Data
    print(f"\n[1/4] Loading pre-split dataset from: {data_path}...")
    data = np.load(data_path, allow_pickle=True)
    features = data['features']
    gates = data['gates']
    tp_targets = data['tp_targets']
    sl_targets = data['sl_targets']
    roe_targets = data['roe_targets']
    datetimes = data['datetimes']
    train_indices = data['train_indices']
    assets = data['assets']

    num_assets = len(assets)
    feat_dim = features.shape[-1]
    print(f"  Total bars: {len(features):,} | Assets ({num_assets}): {assets.tolist()} | Feature Dim: {feat_dim}")
    print(f"  Training horizon: {datetimes[train_indices[0]]} -> {datetimes[train_indices[-1]]} ({len(train_indices):,} bars)")

    # 2. Strict Z-Score Normalization
    print("\n[2/4] Normalizing features strictly on pre-2026/05 training set...")
    train_feat = features[train_indices]
    mean = np.mean(train_feat, axis=(0, 1), keepdims=True)
    std = np.std(train_feat, axis=(0, 1), keepdims=True) + 1e-6
    features_norm = np.clip((features - mean) / std, -5.0, 5.0).astype(np.float32)

    # 85% Train, 15% Validation Split within Training Set
    n_train_total = len(train_indices)
    split_idx = int(n_train_total * 0.85)
    tr_idx = train_indices[:split_idx]
    val_idx = train_indices[split_idx:]

    train_ds = StrideCryptoDataset(features_norm, gates, tp_targets, sl_targets, roe_targets, tr_idx, lookback, stride)
    val_ds = StrideCryptoDataset(features_norm, gates, tp_targets, sl_targets, roe_targets, val_idx, lookback, stride)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0, pin_memory=True)

    print(f"  Sampled Training steps: {len(train_ds):,} | Validation steps: {len(val_ds):,}")

    # 3. Model Architecture
    print("\n[3/4] Initializing CryptoLeverageTransformerWithPolicy...")
    model = CryptoLeverageTransformerWithPolicy(
        num_assets=num_assets,
        in_features=feat_dim,
        lookback=lookback,
        d_model=64,
        n_heads=4,
        num_layers=3,
        dim_feedforward=256,
        dropout=0.15,
        min_leverage=0.0,
        max_leverage=75.0
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Total Trainable Parameters: {total_params:,}")

    criterion = DifferentiableSharpeLeverageLoss(
        weight_gate=1.0,
        weight_tp=0.5,
        weight_sl=0.5,
        weight_leverage=0.8,
        friction_rate=0.0009
    )

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scaler = torch.cuda.amp.GradScaler(enabled=(device.type == 'cuda'))

    os.makedirs(checkpoint_dir, exist_ok=True)
    best_ckpt_path = os.path.join(checkpoint_dir, "best_transformer_dynamic_leverage.pt")

    # 4. Training Loop
    print("\n[4/4] Starting GPU Model Training...")
    best_val_loss = float('inf')
    best_val_acc = 0.0

    t_start = time.time()
    for epoch in range(1, epochs + 1):
        ep_t0 = time.time()
        model.train()
        total_tr_loss = 0.0
        n_batches = 0

        for x_b, g_b, tp_b, sl_b, roe_b in train_loader:
            x_b = x_b.to(device, non_blocking=True)
            g_b = g_b.to(device, non_blocking=True)
            tp_b = tp_b.to(device, non_blocking=True)
            sl_b = sl_b.to(device, non_blocking=True)
            roe_b = roe_b.to(device, non_blocking=True)

            optimizer.zero_grad()
            with torch.cuda.amp.autocast(enabled=(device.type == 'cuda')):
                preds = model(x_b)
                loss_dict = criterion(preds, g_b, tp_b, sl_b, roe_b)
                loss = loss_dict['total_loss']

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            scaler.step(optimizer)
            scaler.update()

            total_tr_loss += loss.item()
            n_batches += 1

        avg_tr_loss = total_tr_loss / max(n_batches, 1)

        # Validation
        model.eval()
        total_val_loss = 0.0
        correct_gates = 0
        total_gates = 0
        lev_list = []
        n_val = 0

        with torch.no_grad():
            for x_b, g_b, tp_b, sl_b, roe_b in val_loader:
                x_b = x_b.to(device, non_blocking=True)
                g_b = g_b.to(device, non_blocking=True)
                tp_b = tp_b.to(device, non_blocking=True)
                sl_b = sl_b.to(device, non_blocking=True)
                roe_b = roe_b.to(device, non_blocking=True)

                with torch.cuda.amp.autocast(enabled=(device.type == 'cuda')):
                    preds = model(x_b)
                    loss_dict = criterion(preds, g_b, tp_b, sl_b, roe_b)
                    loss = loss_dict['total_loss']

                total_val_loss += loss.item()
                n_val += 1

                # Gate accuracy
                pred_gates = torch.argmax(preds['logits_gate'], dim=-1)
                correct_gates += (pred_gates == g_b).sum().item()
                total_gates += g_b.numel()
                lev_list.append(preds['pred_leverage'].cpu().numpy())

        avg_val_loss = total_val_loss / max(n_val, 1)
        val_acc = (correct_gates / max(total_gates, 1)) * 100.0
        val_levs = np.concatenate(lev_list, axis=0)
        mean_lev = np.mean(val_levs)
        min_lev = np.min(val_levs)
        max_lev = np.max(val_levs)

        ep_duration = time.time() - ep_t0
        print(f"  Epoch {epoch:2d}/{epochs:2d} [{ep_duration:5.1f}s] | Tr Loss: {avg_tr_loss:.4f} | Val Loss: {avg_val_loss:.4f} | Val Acc: {val_acc:5.2f}% | Pred Lev: {min_lev:.1f}x-{max_lev:.1f}x (Avg: {mean_lev:.1f}x)")

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_val_acc = val_acc
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'scaler_mean': mean,
                'scaler_std': std,
                'val_loss': best_val_loss,
                'val_acc': best_val_acc,
                'feature_dim': feat_dim,
                'lookback': lookback,
                'num_assets': num_assets
            }, best_ckpt_path)
            print(f"    --> [SAVED] Optimal Checkpoint Saved -> {best_ckpt_path}")

    total_time = time.time() - t_start
    print("\n" + "=" * 85)
    print(f"  [SUCCESS] Dynamic Leverage Model Training Completed in {total_time/60:.2f} minutes!")
    print(f"  Best Val Loss: {best_val_loss:.4f} | Best Val Acc: {best_val_acc:.2f}%")
    print(f"  Optimal Weights Saved: {best_ckpt_path}")
    print("=" * 85)

if __name__ == '__main__':
    train_dynamic_leverage_model()
