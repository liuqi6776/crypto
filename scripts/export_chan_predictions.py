# -*- coding: utf-8 -*-
"""
Export Predictions from Best ST-ChanTransformer Checkpoint
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from crypto_quant.crypto_transformer import CryptoSTChanTransformer
from crypto_quant.dataset_builder import TOKENS, prepare_chan_wave_datasets
from scripts.train_chan_transformer import evaluate_chan_model

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
best_ckpt_path = root_dir / 'checkpoints' / 'best_chan_transformer.pt'
pred_dir = root_dir / 'predictions'
pred_dir.mkdir(parents=True, exist_ok=True)

print(f"Loading checkpoint from {best_ckpt_path} on {device}...")
ckpt = torch.load(best_ckpt_path, map_location=device, weights_only=False)

meta = ckpt['metadata']
num_features = meta['num_features']
lookback_len = meta['lookback_len']

# Prepare datasets
train_ds, val_ds, blind_ds, _ = prepare_chan_wave_datasets(lookback_len=lookback_len)
val_loader = DataLoader(val_ds, batch_size=128, shuffle=False)
blind_loader = DataLoader(blind_ds, batch_size=128, shuffle=False)

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

model.load_state_dict(ckpt['model_state_dict'])

print("Evaluating Out-of-Sample (Val + Blind) datasets...")
val_metrics, val_preds = evaluate_chan_model(model, val_loader, device)
blind_metrics, blind_preds = evaluate_chan_model(model, blind_loader, device)

full_oos_timestamps = np.concatenate([meta['val_timestamps'], meta['blind_test_timestamps']])

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

print(f"Successfully exported predictions to: {pred_out_path}")
print(f"Shape: {df_chan_preds.shape}, Range: {df_chan_preds.index[0]} -> {df_chan_preds.index[-1]}")
print(f"Sample columns: {list(df_chan_preds.columns)}")
print(f"Val 12d Rank IC: {val_metrics['mean_rank_ic_12d']:.4f}")
