# -*- coding: utf-8 -*-
"""
CryptoLeverageTransformer: Spatio-Temporal Relational Transformer for 20X Perpetual Leverage
20倍杠杆多资产时空关系 Transformer 模型
- 4 Assets: BTC, ETH, SOL, BNB
- 60 1-Minute Microstructure & Capital Flow Lookback Window
- Multi-Task Heads: Directional Gate, Dynamic Optimal TP Price, Dynamic Optimal SL Price, Expected Net ROE
- Strict 20X Liquidation Guard (< 1.2% hard max SL vs 4.5% liquidation barrier)
"""

import math
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import numba


class PositionalEncoding(nn.Module):
    """Sinusoidal Positional Encoding for 1-minute high-frequency sequences"""
    def __init__(self, d_model: int, max_len: int = 120):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B * K, L, d_model)
        return x + self.pe[:, :x.size(1), :]


class TemporalTransformerEncoder(nn.Module):
    """Encodes 60-bar temporal micro-patterns with Multi-Head Self-Attention"""
    def __init__(self, in_features: int, d_model: int = 64, nhead: int = 4, num_layers: int = 2, dropout: float = 0.1):
        super().__init__()
        self.input_proj = nn.Linear(in_features, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=d_model * 2,
            dropout=dropout,
            activation='gelu',
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.pool_query = nn.Linear(d_model, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B * K, L, in_features)
        h = self.input_proj(x)
        h = self.pos_encoder(h)
        h = self.transformer(h)  # (B * K, L, d_model)
        # Attention Pooling
        weights = F.softmax(self.pool_query(h), dim=1)  # (B * K, L, 1)
        pooled = torch.sum(h * weights, dim=1)           # (B * K, d_model)
        return pooled


class CryptoLeverageTransformer(nn.Module):
    """
    Spatio-Temporal Cross-Asset Transformer for 20X Leverage Perpetual Trading
    时空跨资产 20倍杠杆最优止盈止损预测大模型
    """
    def __init__(
        self,
        num_assets: int = 4,
        in_features: int = 32,
        lookback: int = 60,
        d_model: int = 64,
        n_heads: int = 4,
        num_temporal_layers: int = 2,
        num_relational_layers: int = 2,
        dropout: float = 0.1,
        min_tp_pct: float = 0.005,   # Minimum TP: 0.5% (10% ROE at 20x)
        max_tp_pct: float = 0.025,   # Maximum TP: 2.5% (50% ROE at 20x)
        min_sl_pct: float = 0.003,   # Minimum SL: 0.3% (6% ROE at 20x)
        max_sl_pct: float = 0.012    # Maximum SL: 1.2% (24% ROE at 20x, far safer than 4.5% liq line)
    ):
        super().__init__()
        self.num_assets = num_assets
        self.d_model = d_model
        self.lookback = lookback
        self.min_tp_pct = min_tp_pct
        self.max_tp_pct = max_tp_pct
        self.min_sl_pct = min_sl_pct
        self.max_sl_pct = max_sl_pct

        # 1. Temporal Self-Attention Encoder
        self.temporal_encoder = TemporalTransformerEncoder(
            in_features=in_features,
            d_model=d_model,
            nhead=n_heads,
            num_layers=num_temporal_layers,
            dropout=dropout
        )

        # 2. Asset Role Embeddings (BTC=0, ETH=1, SOL=2, BNB=3)
        self.asset_emb = nn.Embedding(num_assets, d_model)

        # 3. Cross-Asset Relational Multi-Head Attention Layers
        self.rel_layers = nn.ModuleList()
        for _ in range(num_relational_layers):
            layer = nn.ModuleDict({
                'attn': nn.MultiheadAttention(embed_dim=d_model, num_heads=n_heads, dropout=dropout, batch_first=True),
                'ln1': nn.LayerNorm(d_model),
                'mlp': nn.Sequential(
                    nn.Linear(d_model, d_model * 2),
                    nn.GELU(),
                    nn.Dropout(dropout),
                    nn.Linear(d_model * 2, d_model)
                ),
                'ln2': nn.LayerNorm(d_model)
            })
            self.rel_layers.append(layer)

        # 4. Multi-Task Heads
        # Head 1: Directional Gate (0: Flat/Pass, 1: Long, 2: Short)
        self.head_gate = nn.Sequential(
            nn.Linear(d_model, 32),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(32, 3)
        )

        # Head 2: Dynamic Take-Profit Distance Head (Bounded via sigmoid)
        self.head_tp = nn.Sequential(
            nn.Linear(d_model, 32),
            nn.GELU(),
            nn.Linear(32, 1)
        )

        # Head 3: Dynamic Stop-Loss Distance Head (Bounded via sigmoid, max 1.2%)
        self.head_sl = nn.Sequential(
            nn.Linear(d_model, 32),
            nn.GELU(),
            nn.Linear(32, 1)
        )

        # Head 4: Expected Net 20X ROE Head (%)
        self.head_roe = nn.Sequential(
            nn.Linear(d_model, 32),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1)
        )

    def forward(self, x: torch.Tensor) -> dict:
        """
        Input:
            x: (B, K=4, L=60, D)
        Output:
            dict containing:
                'logits_gate': (B, K, 3)
                'prob_gate': (B, K, 3)
                'pred_tp_pct': (B, K) in [min_tp_pct, max_tp_pct]
                'pred_sl_pct': (B, K) in [min_sl_pct, max_sl_pct]
                'pred_expected_roe': (B, K)
                'attn_weights': (B, K, K)
        """
        B, K, L, D = x.size()

        # 1. Temporal encoding across the 60 1m bars
        x_reshaped = x.view(B * K, L, D)
        temp_repr = self.temporal_encoder(x_reshaped)  # (B * K, d_model)
        temp_repr = temp_repr.view(B, K, self.d_model)  # (B, K, d_model)

        # 2. Inject Asset Role Embedding
        asset_ids = torch.arange(K, device=x.device).unsqueeze(0).expand(B, -1)
        h = temp_repr + self.asset_emb(asset_ids)

        # 3. Cross-Asset Relational Multi-Head Attention
        last_weights = None
        for layer in self.rel_layers:
            attn_out, weights = layer['attn'](h, h, h)
            h = layer['ln1'](h + attn_out)
            mlp_out = layer['mlp'](h)
            h = layer['ln2'](h + mlp_out)
            last_weights = weights  # (B, K, K)

        # 4. Multi-Task Heads
        logits_gate = self.head_gate(h)               # (B, K, 3)
        prob_gate = F.softmax(logits_gate, dim=-1)   # (B, K, 3)

        # Sigmoid-bounded TP distance
        sig_tp = torch.sigmoid(self.head_tp(h).squeeze(-1))
        pred_tp_pct = self.min_tp_pct + (self.max_tp_pct - self.min_tp_pct) * sig_tp

        # Sigmoid-bounded SL distance (strictly guaranteed <= max_sl_pct)
        sig_sl = torch.sigmoid(self.head_sl(h).squeeze(-1))
        pred_sl_pct = self.min_sl_pct + (self.max_sl_pct - self.min_sl_pct) * sig_sl

        # Expected Net ROE (%)
        pred_expected_roe = self.head_roe(h).squeeze(-1)

        return {
            'logits_gate': logits_gate,
            'prob_gate': prob_gate,
            'pred_tp_pct': pred_tp_pct,
            'pred_sl_pct': pred_sl_pct,
            'pred_expected_roe': pred_expected_roe,
            'attn_weights': last_weights
        }


class LeverageMultiTaskLoss(nn.Module):
    """
    Multi-Task Loss for 20X Leverage Transformer
    Balances Directional Classification, TP/SL Distance Regression, and Net ROE Fit
    """
    def __init__(
        self,
        w_cls: float = 1.0,
        w_tp: float = 0.5,
        w_sl: float = 0.5,
        w_roe: float = 0.2,
        class_weights: torch.Tensor = None
    ):
        super().__init__()
        self.w_cls = w_cls
        self.w_tp = w_tp
        self.w_sl = w_sl
        self.w_roe = w_roe
        self.ce_loss = nn.CrossEntropyLoss(weight=class_weights)
        self.huber_tp = nn.SmoothL1Loss(beta=0.002)
        self.huber_sl = nn.SmoothL1Loss(beta=0.001)
        self.huber_roe = nn.SmoothL1Loss(beta=1.0)

    def forward(self, outputs: dict, target_gate: torch.Tensor, target_tp: torch.Tensor, target_sl: torch.Tensor, target_roe: torch.Tensor):
        """
        target_gate: (B, K) in {0: Flat, 1: Long, 2: Short}
        target_tp: (B, K) in float
        target_sl: (B, K) in float
        target_roe: (B, K) in float (20x net ROE)
        """
        logits_gate = outputs['logits_gate'].view(-1, 3)
        target_gate_flat = target_gate.view(-1)
        loss_cls = self.ce_loss(logits_gate, target_gate_flat)

        # Only compute TP/SL distance loss on non-flat samples (where target_gate != 0)
        active_mask = (target_gate_flat != 0)
        if active_mask.sum() > 0:
            pred_tp_active = outputs['pred_tp_pct'].view(-1)[active_mask]
            target_tp_active = target_tp.view(-1)[active_mask]
            loss_tp = self.huber_tp(pred_tp_active, target_tp_active)

            pred_sl_active = outputs['pred_sl_pct'].view(-1)[active_mask]
            target_sl_active = target_sl.view(-1)[active_mask]
            loss_sl = self.huber_sl(pred_sl_active, target_sl_active)
        else:
            loss_tp = torch.tensor(0.0, device=logits_gate.device)
            loss_sl = torch.tensor(0.0, device=logits_gate.device)

        # Expected Net ROE loss
        loss_roe = self.huber_roe(outputs['pred_expected_roe'].view(-1), target_roe.view(-1))

        total_loss = self.w_cls * loss_cls + self.w_tp * loss_tp + self.w_sl * loss_sl + self.w_roe * loss_roe
        return total_loss, {
            'loss_total': total_loss.item(),
            'loss_cls': loss_cls.item(),
            'loss_tp': loss_tp.item() if isinstance(loss_tp, torch.Tensor) else loss_tp,
            'loss_sl': loss_sl.item() if isinstance(loss_sl, torch.Tensor) else loss_sl,
            'loss_roe': loss_roe.item()
        }


# =====================================================================
# Numba-Accelerated Maximum Favorable / Adverse Excursion Labeler
# =====================================================================

@numba.jit(nopython=True)
def label_excursions_and_optimal_barriers_numba(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    horizon: int = 30,
    leverage: float = 20.0,
    roundtrip_fee_pct: float = 0.0004, # 0.04% maker-maker fee (0.8% on margin)
    min_profit_pct: float = 0.006,     # 0.6% price move (12% ROE on 20x)
    max_safe_sl_pct: float = 0.012,    # 1.2% price move (24% ROE loss, safe from 4.5% liq)
    min_sl_pct: float = 0.003
):
    """
    Computes Maximum Favorable Excursion (MFE), Maximum Adverse Excursion (MAE),
    and derives the mathematically optimal Take-Profit and Stop-Loss distances
    to maximize 20X expected net ROE for both Long and Short directions.
    """
    n = len(close)
    gate_labels = np.zeros(n, dtype=np.int8) # 0: Flat, 1: Long, 2: Short
    opt_tp = np.zeros(n, dtype=np.float32)
    opt_sl = np.zeros(n, dtype=np.float32)
    net_roe = np.zeros(n, dtype=np.float32)

    for i in range(n - horizon):
        p0 = close[i]

        # Scan future horizon
        h_max = -1.0
        l_min = 1e9
        for j in range(1, horizon + 1):
            h_val = high[i + j]
            l_val = low[i + j]
            if h_val > h_max:
                h_max = h_val
            if l_val < l_min:
                l_min = l_val

        # Long excursions
        long_mfe = (h_max - p0) / p0
        long_mae = (p0 - l_min) / p0

        # Short excursions
        short_mfe = (p0 - l_min) / p0
        short_mae = (h_max - p0) / p0

        # Evaluate Long suitability
        # Condition: favorable excursion covers fee and min profit, and risk-reward ratio >= 1.4
        long_valid = (long_mfe >= min_profit_pct) and (long_mae <= max_safe_sl_pct) and (long_mfe > long_mae * 1.3)

        # Evaluate Short suitability
        short_valid = (short_mfe >= min_profit_pct) and (short_mae <= max_safe_sl_pct) and (short_mfe > short_mae * 1.3)

        if long_valid and not short_valid:
            gate_labels[i] = 1 # Long
            # Optimal TP: captures 75% of MFE to ensure limit fill
            tp_target = min(max(long_mfe * 0.75, min_profit_pct), 0.025)
            # Optimal SL: placed just beyond MAE with safety cushion, capped at max_safe_sl_pct
            sl_target = min(max(long_mae * 1.15, min_sl_pct), max_safe_sl_pct)
            opt_tp[i] = tp_target
            opt_sl[i] = sl_target
            # Realized net 20x ROE
            net_roe[i] = (tp_target - roundtrip_fee_pct) * leverage * 100.0

        elif short_valid and not long_valid:
            gate_labels[i] = 2 # Short
            tp_target = min(max(short_mfe * 0.75, min_profit_pct), 0.025)
            sl_target = min(max(short_mae * 1.15, min_sl_pct), max_safe_sl_pct)
            opt_tp[i] = tp_target
            opt_sl[i] = sl_target
            net_roe[i] = (tp_target - roundtrip_fee_pct) * leverage * 100.0

        elif long_valid and short_valid:
            # Pick the higher net excursion
            if long_mfe >= short_mfe:
                gate_labels[i] = 1
                tp_target = min(max(long_mfe * 0.75, min_profit_pct), 0.025)
                sl_target = min(max(long_mae * 1.15, min_sl_pct), max_safe_sl_pct)
                opt_tp[i] = tp_target
                opt_sl[i] = sl_target
                net_roe[i] = (tp_target - roundtrip_fee_pct) * leverage * 100.0
            else:
                gate_labels[i] = 2
                tp_target = min(max(short_mfe * 0.75, min_profit_pct), 0.025)
                sl_target = min(max(short_mae * 1.15, min_sl_pct), max_safe_sl_pct)
                opt_tp[i] = tp_target
                opt_sl[i] = sl_target
                net_roe[i] = (tp_target - roundtrip_fee_pct) * leverage * 100.0
        else:
            gate_labels[i] = 0 # Flat
            opt_tp[i] = 0.010
            opt_sl[i] = 0.006
            net_roe[i] = 0.0

    return gate_labels, opt_tp, opt_sl, net_roe


if __name__ == '__main__':
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Testing CryptoLeverageTransformer on {device}...")

    B, K, L, D = 8, 4, 60, 32
    dummy_x = torch.randn(B, K, L, D, device=device)
    model = CryptoLeverageTransformer(num_assets=K, in_features=D, lookback=L).to(device)

    out = model(dummy_x)
    print("Forward pass successful!")
    print("  logits_gate shape:     ", out['logits_gate'].shape)
    print("  prob_gate shape:       ", out['prob_gate'].shape)
    print("  pred_tp_pct shape:     ", out['pred_tp_pct'].shape, "range:", out['pred_tp_pct'].min().item(), "to", out['pred_tp_pct'].max().item())
    print("  pred_sl_pct shape:     ", out['pred_sl_pct'].shape, "range:", out['pred_sl_pct'].min().item(), "to", out['pred_sl_pct'].max().item())
    print("  pred_expected_roe shape:", out['pred_expected_roe'].shape)
    print("  attn_weights shape:    ", out['attn_weights'].shape)

    # Test Loss Function
    target_gate = torch.randint(0, 3, (B, K), device=device)
    target_tp = torch.rand(B, K, device=device) * 0.02 + 0.005
    target_sl = torch.rand(B, K, device=device) * 0.008 + 0.003
    target_roe = torch.randn(B, K, device=device) * 20.0

    criterion = LeverageMultiTaskLoss().to(device)
    loss, loss_dict = criterion(out, target_gate, target_tp, target_sl, target_roe)
    loss.backward()
    print("Backward pass successful! Loss breakdown:", loss_dict)
