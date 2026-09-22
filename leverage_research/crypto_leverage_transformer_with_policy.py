"""
CryptoLeverageTransformerWithPolicy:
Extended Transformer architecture featuring an end-to-end continuous
Self-Adaptive Optimal Leverage Head (0X - 75X) trained via Differentiable Sharpe Loss.
"""

import math
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 500):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, L, d_model)
        return x + self.pe[:, :x.size(1), :]

class CryptoLeverageTransformerWithPolicy(nn.Module):
    def __init__(
        self,
        num_assets: int = 4,
        in_features: int = 30,
        lookback: int = 60,
        d_model: int = 64,
        n_heads: int = 4,
        num_layers: int = 3,
        dim_feedforward: int = 256,
        dropout: float = 0.15,
        min_leverage: float = 0.0,
        max_leverage: float = 75.0,
        min_tp_pct: float = 0.0035,
        max_tp_pct: float = 0.0250,
        min_sl_pct: float = 0.0018,
        max_sl_pct: float = 0.0080
    ):
        super().__init__()
        self.num_assets = num_assets
        self.in_features = in_features
        self.lookback = lookback
        self.d_model = d_model
        self.min_leverage = min_leverage
        self.max_leverage = max_leverage
        self.min_tp_pct = min_tp_pct
        self.max_tp_pct = max_tp_pct
        self.min_sl_pct = min_sl_pct
        self.max_sl_pct = max_sl_pct

        # 1. Feature Projection
        self.input_proj = nn.Linear(in_features, d_model)
        self.pos_encoder = PositionalEncoding(d_model, max_len=lookback + 10)

        # 2. Temporal Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=n_heads,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation='gelu',
            batch_first=True
        )
        self.temporal_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # 3. Cross-Asset Relational Multi-Head Attention
        self.asset_emb = nn.Embedding(num_assets, d_model)
        self.cross_asset_attn = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=n_heads,
            dropout=dropout,
            batch_first=True
        )
        self.ln_cross = nn.LayerNorm(d_model)

        # 4. Multi-Task Heads
        # Head 1: Directional Gate (0: Flat/Pass, 1: Long, 2: Short)
        self.head_gate = nn.Sequential(
            nn.Linear(d_model, 64),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(64, 3)
        )

        # Head 2: Dynamic Take-Profit Target
        self.head_tp = nn.Sequential(
            nn.Linear(d_model, 32),
            nn.GELU(),
            nn.Linear(32, 1)
        )

        # Head 3: Dynamic Stop-Loss Distance
        self.head_sl = nn.Sequential(
            nn.Linear(d_model, 32),
            nn.GELU(),
            nn.Linear(32, 1)
        )

        # Head 4: Continuous Optimal Leverage Head (0x to 75x)
        self.head_leverage = nn.Sequential(
            nn.Linear(d_model, 64),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.GELU(),
            nn.Linear(32, 1)
        )

        # Head 5: Expected Net ROE Head
        self.head_roe = nn.Sequential(
            nn.Linear(d_model, 32),
            nn.GELU(),
            nn.Linear(32, 1)
        )

    def forward(self, x: torch.Tensor) -> dict:
        """
        Input:
            x: (B, K, L, D) where K=num_assets, L=lookback, D=in_features
        """
        B, K, L, D = x.size()

        # 1. Temporal Encoding
        x_flat = x.view(B * K, L, D)
        h_proj = self.input_proj(x_flat)
        h_pos = self.pos_encoder(h_proj)
        h_temp = self.temporal_encoder(h_pos) # (B*K, L, d_model)
        # Take the last time step representation
        h_last = h_temp[:, -1, :]             # (B*K, d_model)
        h_assets = h_last.view(B, K, self.d_model) # (B, K, d_model)

        # 2. Add Asset Role Embedding
        asset_ids = torch.arange(K, device=x.device).unsqueeze(0).expand(B, -1)
        h_assets = h_assets + self.asset_emb(asset_ids)

        # 3. Cross-Asset Attention
        attn_out, attn_weights = self.cross_asset_attn(h_assets, h_assets, h_assets)
        h_fused = self.ln_cross(h_assets + attn_out) # (B, K, d_model)

        # 4. Multi-Task Heads
        logits_gate = self.head_gate(h_fused)               # (B, K, 3)
        prob_gate = F.softmax(logits_gate, dim=-1)         # (B, K, 3)

        sig_tp = torch.sigmoid(self.head_tp(h_fused).squeeze(-1))
        pred_tp_pct = self.min_tp_pct + (self.max_tp_pct - self.min_tp_pct) * sig_tp

        sig_sl = torch.sigmoid(self.head_sl(h_fused).squeeze(-1))
        pred_sl_pct = self.min_sl_pct + (self.max_sl_pct - self.min_sl_pct) * sig_sl

        sig_lev = torch.sigmoid(self.head_leverage(h_fused).squeeze(-1))
        pred_leverage = self.min_leverage + (self.max_leverage - self.min_leverage) * sig_lev

        pred_roe = self.head_roe(h_fused).squeeze(-1)

        return {
            'logits_gate': logits_gate,
            'prob_gate': prob_gate,
            'pred_tp_pct': pred_tp_pct,
            'pred_sl_pct': pred_sl_pct,
            'pred_leverage': pred_leverage,
            'pred_roe': pred_roe,
            'attn_weights': attn_weights
        }


class DifferentiableSharpeLeverageLoss(nn.Module):
    """
    End-to-end differentiable loss combining:
    1. Cross-entropy direction loss
    2. Huber regression for TP and SL
    3. Differentiable Sharpe Ratio maximization for the leverage head
    """
    def __init__(
        self,
        weight_gate: float = 1.0,
        weight_tp: float = 0.5,
        weight_sl: float = 0.5,
        weight_leverage: float = 0.8,
        friction_rate: float = 0.0009 # 9 bps total friction (fees + slippage)
    ):
        super().__init__()
        self.weight_gate = weight_gate
        self.weight_tp = weight_tp
        self.weight_sl = weight_sl
        self.weight_leverage = weight_leverage
        self.friction_rate = friction_rate
        self.ce_loss = nn.CrossEntropyLoss(label_smoothing=0.05)
        self.huber_loss = nn.SmoothL1Loss()

    def forward(
        self,
        preds: dict,
        target_gates: torch.Tensor,     # (B, K)
        target_tps: torch.Tensor,       # (B, K)
        target_sls: torch.Tensor,       # (B, K)
        target_roes: torch.Tensor       # (B, K) in percent (e.g. +1.5% or -0.6%)
    ) -> dict:
        logits = preds['logits_gate']    # (B, K, 3)
        B, K, _ = logits.size()

        # 1. Gate Classification Loss
        loss_gate = self.ce_loss(logits.view(B * K, 3), target_gates.view(B * K))

        # 2. Dynamic Barrier Losses
        loss_tp = self.huber_loss(preds['pred_tp_pct'].view(-1), target_tps.view(-1))
        loss_sl = self.huber_loss(preds['pred_sl_pct'].view(-1), target_sls.view(-1))

        # 3. Differentiable Sharpe Leverage Loss
        # Target raw asset return: target_roes is raw percentage move / 20.0 (unleveraged)
        raw_asset_ret = target_roes / 20.0 # (B, K) in decimal
        pred_lev = preds['pred_leverage']  # (B, K) in [0, 75]

        # Net realized return for this trade:
        # Net Return = Leverage * Asset Return - Leverage * Friction Rate
        net_trade_ret = pred_lev * raw_asset_ret - pred_lev * self.friction_rate # (B, K)

        # Differentiable Sharpe across batch
        mean_ret = torch.mean(net_trade_ret)
        std_ret = torch.std(net_trade_ret) + 1e-6
        sharpe_loss = - (mean_ret / std_ret)

        # Downside penalty: Heavily penalize negative net returns
        downside_risk = torch.mean(torch.relu(-net_trade_ret) ** 2)

        loss_leverage = sharpe_loss + 2.0 * downside_risk

        # Total Loss
        total_loss = (
            self.weight_gate * loss_gate +
            self.weight_tp * loss_tp +
            self.weight_sl * loss_sl +
            self.weight_leverage * loss_leverage
        )

        return {
            'total_loss': total_loss,
            'loss_gate': loss_gate,
            'loss_tp': loss_tp,
            'loss_sl': loss_sl,
            'loss_leverage': loss_leverage,
            'sharpe_estimate': -sharpe_loss.item()
        }
