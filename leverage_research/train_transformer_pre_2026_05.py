# -*- coding: utf-8 -*-
"""
Train CryptoLeverageTransformer Strictly on Pre-2026/05 Training Horizon
在 2026年5月1日 之前的数据集上严格进行 Transformer 多任务模型 GPU 训练
- Training horizon: 2020-09-14 to 2026-04-30 23:59:00 (~2.95M bars)
- Zero Lookahead Bias: Normalizer fitted strictly on pre-2026/05 train indices
- Test Set (2026-05-01 to 2026-09-22) is completely isolated and unseen
- Exports optimal checkpoint: best_transformer_pre_2026_05.pt
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
    Uniform-stride multi-year high-frequency dataset.
    Ensures complete temporal coverage across all regimes with zero lookahead bias.
    """
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


def train_model(
    data_path: str = r"D:\Convertible_Bond_data\crypto_data\multi_asset_split_2026_05.npz",
    epochs: int = 6,
    batch_size: int = 256,
    lr: float = 5e-4,
    lookback: int = 60,
    stride: int = 4,
    checkpoint_dir: str = r"c:\Users\liuqi\crypto\checkpoints"
):
    print("=" * 85)
    print("  Training CryptoLeverageTransformer on Pre-2026/05 In-Sample Horizon")
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
    test_indices = data['test_indices']
    assets = data['assets']
    feat_names = data['feature_names']

    N, K, D = features.shape
    print(f"  Total bars: {N:,} | Assets ({K}): {assets.tolist()} | Features ({D}): {len(feat_names)}")
    print(f"  Training Split Range: [{train_indices[0]} to {train_indices[-1]:,}] ({datetimes[train_indices[0]]} -> {datetimes[train_indices[-1]]})")
    print(f"  Unseen Test Split Range: [{test_indices[0]:,} to {test_indices[-1]:,}] ({datetimes[test_indices[0]]} -> {datetimes[test_indices[-1]]})")

    # 2. Fit Scaler STRICTLY on Train Split (Zero Lookahead Leakage)
    print("\n[2/4] Fitting feature scaler strictly on in-sample training split...")
    train_feats = features[train_indices]
    scaler_mean = np.nanmean(train_feats, axis=(0, 1), keepdims=True)
    scaler_std = np.nanstd(train_feats, axis=(0, 1), keepdims=True)
    scaler_std[scaler_std < 1e-4] = 1.0

    features_norm = np.clip((features - scaler_mean) / scaler_std, -5.0, 5.0).astype(np.float32)

    # Class Weights for Train Split
    train_gates = gates[train_indices].flatten()
    c_counts = np.bincount(train_gates, minlength=3)
    c_weights = (len(train_gates) / (3.0 * np.maximum(c_counts, 1))).astype(np.float32)
    print(f"  Train Class distribution: Flat={c_counts[0]:,}, Long={c_counts[1]:,}, Short={c_counts[2]:,}")
    print(f"  Computed Balanced Class Weights: {c_weights.round(3).tolist()}")
    class_weights = torch.from_numpy(c_weights).to(device)

    # Internal Validation split within the training horizon (last 10% of train_indices)
    n_train_total = len(train_indices)
    split_pivot = int(n_train_total * 0.90)
    sub_train_idx = train_indices[:split_pivot]
    sub_val_idx = train_indices[split_pivot:]

    print(f"  Sub-Train bars: {len(sub_train_idx):,} ({datetimes[sub_train_idx[0]]} -> {datetimes[sub_train_idx[-1]]})")
    print(f"  Sub-Val bars:   {len(sub_val_idx):,} ({datetimes[sub_val_idx[0]]} -> {datetimes[sub_val_idx[-1]]})")

    # Dataloaders
    train_ds = StrideCryptoDataset(
        features_norm, gates, tp_targets, sl_targets, roe_targets,
        sub_train_idx, lookback=lookback, stride=stride
    )
    val_ds = StrideCryptoDataset(
        features_norm, gates, tp_targets, sl_targets, roe_targets,
        sub_val_idx[::6], lookback=lookback, stride=1
    )

    print(f"  Train samples per epoch (stride={stride}): {len(train_ds):,}")
    print(f"  Sub-Val samples per epoch (stride=6): {len(val_ds):,}")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    # 3. Model & Optimizer
    print(f"\n[3/4] Initializing CryptoLeverageTransformer (D={D}, K={K}, L={lookback})...")
    model = CryptoLeverageTransformer(
        num_assets=K,
        in_features=D,
        lookback=lookback,
        d_model=64,
        n_heads=4,
        num_temporal_layers=2,
        num_relational_layers=2,
        dropout=0.10
    ).to(device)

    criterion = LeverageMultiTaskLoss(
        w_cls=1.0,
        w_tp=0.5,
        w_sl=0.5,
        w_roe=0.2,
        class_weights=class_weights
    ).to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)

    os.makedirs(checkpoint_dir, exist_ok=True)
    best_ckpt_path = os.path.join(checkpoint_dir, "best_transformer_pre_2026_05.pt")
    best_val_loss = float('inf')

    # 4. Training Loop
    print(f"\n[4/4] Starting GPU training loop ({epochs} epochs)...")
    training_start = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        train_cls_acc = 0.0
        total_samples = 0
        t0 = time.time()

        for batch_idx, (x, y_gate, y_tp, y_sl, y_roe) in enumerate(train_loader):
            x = x.to(device)
            y_gate = y_gate.to(device)
            y_tp = y_tp.to(device)
            y_sl = y_sl.to(device)
            y_roe = y_roe.to(device)

            optimizer.zero_grad()
            preds = model(x)
            loss, loss_dict = criterion(preds, y_gate, y_tp, y_sl, y_roe)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=2.0)
            optimizer.step()

            # Directional accuracy
            pred_gate = preds['prob_gate'].argmax(dim=-1)
            acc = (pred_gate == y_gate).float().mean().item()

            train_loss += loss.item() * len(x)
            train_cls_acc += acc * len(x)
            total_samples += len(x)

            if (batch_idx + 1) % 500 == 0:
                print(f"  Epoch {epoch:02d} | Step {batch_idx+1:04d}/{len(train_loader)} | Loss: {loss.item():.4f} (Cls: {loss_dict['loss_cls']:.4f}, ROE: {loss_dict['loss_roe']:.4f}) | Acc: {acc*100:.2f}%", flush=True)

        scheduler.step()
        train_loss /= total_samples
        train_cls_acc /= total_samples

        # Validation phase
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

                preds = model(x)
                v_loss, v_loss_dict = criterion(preds, y_gate, y_tp, y_sl, y_roe)
                pred_gate = preds['prob_gate'].argmax(dim=-1)
                acc = (pred_gate == y_gate).float().mean().item()

                val_loss += v_loss.item() * len(x)
                val_cls_acc += acc * len(x)
                val_samples += len(x)

        val_loss /= val_samples
        val_cls_acc /= val_samples

        elapsed = time.time() - t0
        print(f"\n>>> Epoch {epoch:02d}/{epochs:02d} Finished in {elapsed:.1f}s:")
        print(f"    Train Loss: {train_loss:.4f} | Train Acc: {train_cls_acc*100:.2f}%")
        print(f"    Val Loss:   {val_loss:.4f} | Val Acc:   {val_cls_acc*100:.2f}% | LR: {scheduler.get_last_lr()[0]:.2e}")

        # Checkpoint if best
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'scaler_mean': scaler_mean,
                'scaler_std': scaler_std,
                'feature_dim': D,
                'lookback': lookback,
                'feature_names': feat_names,
                'assets': assets,
                'best_val_loss': best_val_loss,
                'split_date': "2026-05-01 00:00:00"
            }, best_ckpt_path)
            print(f"    [*] NEW BEST MODEL SAVED -> {best_ckpt_path} (Val Loss: {best_val_loss:.4f})")

        print("-" * 80)

    total_time = time.time() - training_start
    print(f"\n[DONE] Training complete in {total_time/60:.2f} minutes. Best Checkpoint -> {best_ckpt_path}")
    return best_ckpt_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-path', type=str, default=r"D:\Convertible_Bond_data\crypto_data\multi_asset_split_2026_05.npz")
    parser.add_argument('--epochs', type=int, default=6)
    parser.add_argument('--batch-size', type=int, default=256)
    parser.add_argument('--lr', type=float, default=5e-4)
    parser.add_argument('--stride', type=int, default=4)
    args = parser.parse_args()

    train_model(
        data_path=args.data_path,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        stride=args.stride
    )
