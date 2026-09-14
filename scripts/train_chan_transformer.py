# -*- coding: utf-8 -*-
"""
GPU Training & Out-of-Sample Export for Spatio-Temporal Chan-Lun Wave Transformer (Phase 20)
===========================================================================================
Trains CryptoSTChanTransformer on 2020-2023 In-Sample Data on NVIDIA RTX 3060 Ti GPU.
Evaluates on 2024-2025 Validation Set and 2026 Locked Post-hoc Stress Period.
Exports predictions to `predictions/chan_transformer_predictions.parquet`.
"""

import os
import random
import sys
import time
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
import torch
from torch.utils.data import DataLoader

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from crypto_quant.crypto_transformer import ChanWaveCombinedLoss, CryptoSTChanTransformer
from crypto_quant.dataset_builder import TOKENS, prepare_chan_wave_datasets


def seed_everything(seed=42):
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def evaluate_chan_model(model, dataloader, device) -> Tuple[Dict[str, float], Dict[str, np.ndarray]]:
    model.eval()
    p_3d_list, p_6d_list, p_12d_list, prob_exp_list = [], [], [], []
    t_3d_list, t_6d_list, t_12d_list, t_exp_list = [], [], [], []

    with torch.no_grad():
        for batch in dataloader:
            x = batch['X'].to(device)
            out = model(x)
            p_3d_list.append(out['pred_wave_3d'].cpu().numpy())
            p_6d_list.append(out['pred_wave_6d'].cpu().numpy())
            p_12d_list.append(out['pred_wave_12d'].cpu().numpy())
            prob_exp_list.append(out['prob_expansion'].cpu().numpy())

            t_3d_list.append(batch['y_3d'].numpy())
            t_6d_list.append(batch['y_6d'].numpy())
            t_12d_list.append(batch['y_12d'].numpy())
            t_exp_list.append(batch['y_exp'].numpy())

    preds = {
        'p_3d': np.concatenate(p_3d_list, axis=0),
        'p_6d': np.concatenate(p_6d_list, axis=0),
        'p_12d': np.concatenate(p_12d_list, axis=0),
        'prob_exp': np.concatenate(prob_exp_list, axis=0),
    }
    targets = {
        't_3d': np.concatenate(t_3d_list, axis=0),
        't_6d': np.concatenate(t_6d_list, axis=0),
        't_12d': np.concatenate(t_12d_list, axis=0),
        't_exp': np.concatenate(t_exp_list, axis=0),
    }

    metrics = {}
    for k, token in enumerate(TOKENS):
        p_12 = preds['p_12d'][:, k]
        t_12 = targets['t_12d'][:, k]
        p_ic_12, _ = pearsonr(p_12, t_12)
        s_ic_12, _ = spearmanr(p_12, t_12)
        hit_12 = np.mean((p_12 > 0) == (t_12 > 0))

        metrics[f'{token}_rank_ic_12d'] = s_ic_12
        metrics[f'{token}_pearson_ic_12d'] = p_ic_12
        metrics[f'{token}_hit_rate_12d'] = hit_12

    metrics['mean_rank_ic_12d'] = float(np.mean([metrics[f'{t}_rank_ic_12d'] for t in TOKENS]))
    metrics['mean_hit_rate_12d'] = float(np.mean([metrics[f'{t}_hit_rate_12d'] for t in TOKENS]))

    return metrics, preds


def train_chan_transformer(
    epochs=25,
    batch_size=128,
    lr=2e-4,
    lookback_len=18,
    seed=42,
    device_name=None
):
    seed_everything(seed)
    device = torch.device(device_name if device_name else ('cuda' if torch.cuda.is_available() else 'cpu'))
    print('=' * 85)
    print(f"TRAINING SPATIO-TEMPORAL CHAN-LUN WAVE TRANSFORMER ON {device}")
    print('=' * 85)

    ckpt_dir = root_dir / 'checkpoints'
    pred_dir = root_dir / 'predictions'
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    pred_dir.mkdir(parents=True, exist_ok=True)
    best_ckpt_path = ckpt_dir / 'best_chan_transformer.pt'

    # 1. Prepare Datasets
    train_ds, val_ds, blind_ds, meta = prepare_chan_wave_datasets(lookback_len=lookback_len)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    blind_loader = DataLoader(blind_ds, batch_size=batch_size, shuffle=False)

    # 2. Instantiate Model
    num_features = meta['num_features']
    model = CryptoSTChanTransformer(
        num_assets=len(TOKENS),
        in_features=num_features,
        lookback=lookback_len,
        d_model=64,
        n_heads=4,
        num_layers=2,
        dropout=0.15,
        temporal_mode='conv'
    ).to(device)

    criterion = ChanWaveCombinedLoss(w_3d=0.35, w_6d=0.35, w_12d=0.30, beta_huber=0.05, gamma_cls=0.1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)

    best_val_ic = -999.0
    start_time = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss_accum = 0.0
        n_batches = 0

        for batch in train_loader:
            x = batch['X'].to(device)
            y_3d = batch['y_3d'].to(device)
            y_6d = batch['y_6d'].to(device)
            y_12d = batch['y_12d'].to(device)
            y_exp = batch['y_exp'].to(device)

            optimizer.zero_grad()
            out = model(x)
            loss, _ = criterion(out, y_3d, y_6d, y_12d, y_exp)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=2.0)
            optimizer.step()

            train_loss_accum += loss.item()
            n_batches += 1

        scheduler.step()
        avg_train_loss = train_loss_accum / max(1, n_batches)

        # Validation Evaluation
        val_metrics, _ = evaluate_chan_model(model, val_loader, device)
        val_rank_ic = val_metrics['mean_rank_ic_12d']
        val_hit_rate = val_metrics['mean_hit_rate_12d']

        print(f"Epoch {epoch:2d}/{epochs:2d} | Train Loss: {avg_train_loss:.4f} | Val 12d Rank IC: {val_rank_ic:.4f} | Val HitRate: {val_hit_rate*100:.1f}%")

        if val_rank_ic > best_val_ic:
            best_val_ic = val_rank_ic
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'val_metrics': val_metrics,
                'metadata': meta
            }, best_ckpt_path)
            print(f"  --> Saved new best checkpoint to {best_ckpt_path} (Val 12d Rank IC: {best_val_ic:.4f})")

    elapsed = time.time() - start_time
    print(f"\nTraining completed in {elapsed:.1f}s. Best Val 12d Rank IC: {best_val_ic:.4f}")

    # 3. Export Out-of-Sample Predictions (Val + Blind)
    print("\nLoading best model checkpoint for prediction export...")
    ckpt = torch.load(best_ckpt_path, map_location=device, weights_only=False)
    model.load_state_dict(ckpt['model_state_dict'])

    # Full out-of-sample loader: combining Val and Blind datasets
    full_oos_timestamps = np.concatenate([meta['val_timestamps'], meta['blind_test_timestamps']])
    val_metrics, val_preds = evaluate_chan_model(model, val_loader, device)
    blind_metrics, blind_preds = evaluate_chan_model(model, blind_loader, device)

    # Assemble prediction DataFrame
    pred_data = {}
    for k, t in enumerate(TOKENS):
        pred_3d_comb = np.concatenate([val_preds['p_3d'][:, k], blind_preds['p_3d'][:, k]])
        pred_6d_comb = np.concatenate([val_preds['p_6d'][:, k], blind_preds['p_6d'][:, k]])
        pred_12d_comb = np.concatenate([val_preds['p_12d'][:, k], blind_preds['p_12d'][:, k]])
        prob_exp_comb = np.concatenate([val_preds['prob_exp'][:, k], blind_preds['prob_exp'][:, k]])

        pred_data[f'{t}_pred_3d'] = pred_3d_comb
        pred_data[f'{t}_pred_6d'] = pred_6d_comb
        pred_data[f'{t}_pred_12d'] = pred_12d_comb
        pred_data[f'{t}_prob_exp'] = prob_exp_comb

    df_chan_preds = pd.DataFrame(pred_data, index=full_oos_timestamps)
    pred_out_path = pred_dir / 'chan_transformer_predictions.parquet'
    df_chan_preds.to_parquet(pred_out_path)

    print(f"Out-of-sample predictions successfully exported to: {pred_out_path}")
    print(f"Shape: {df_chan_preds.shape}, Range: {df_chan_preds.index[0]} -> {df_chan_preds.index[-1]}")

    return best_val_ic, df_chan_preds


if __name__ == '__main__':
    train_chan_transformer(epochs=20, batch_size=128, lr=2e-4, lookback_len=18)
