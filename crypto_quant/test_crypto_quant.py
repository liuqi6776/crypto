# -*- coding: utf-8 -*-
"""
Unit Tests for Crypto Quant Engine (100% Offline & Self-Contained)
加密货币量化交易引擎自动化单元测试 (完全离线运行，无需外网依赖)
"""

import os
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import torch

from crypto_quant.factors import compute_all_factors
from crypto_quant.backtester import CryptoBacktester
from crypto_quant.strategies import dual_ema_trend_strategy, supertrend_strategy
from crypto_quant.data_fetcher import fetch_klines
from crypto_quant.crypto_transformer import CryptoSTTransformer


def generate_synthetic_ohlcv(n_bars=120):
    """生成确定性的合成离线K线数据用于单元测试"""
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=n_bars, freq='4h')
    
    # 模拟几何布朗运动价格
    returns = np.random.normal(0.0005, 0.015, n_bars)
    price = 3000.0 * np.exp(np.cumsum(returns))
    
    high = price * (1 + np.abs(np.random.normal(0, 0.005, n_bars)))
    low = price * (1 - np.abs(np.random.normal(0, 0.005, n_bars)))
    open_p = price * (1 + np.random.normal(0, 0.002, n_bars))
    close = price
    volume = np.random.uniform(100, 5000, n_bars)
    taker_buy_vol = volume * np.random.uniform(0.4, 0.6, n_bars)
    
    df = pd.DataFrame({
        'open': open_p,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
        'taker_buy_volume': taker_buy_vol,
        'quote_volume': volume * close,
        'trades_count': np.random.randint(50, 500, n_bars)
    }, index=dates)
    return df


class TestCryptoQuantOffline(unittest.TestCase):
    """100% 离线单元测试用例集"""

    def setUp(self):
        self.df = generate_synthetic_ohlcv(150)

    def test_factor_computation(self):
        """测试技术与微观结构因子计算完整性与数值有效性"""
        df_factors = compute_all_factors(self.df.copy())
        expected_cols = [
            'macd', 'macd_signal', 'macd_hist', 'rsi_14',
            'bb_upper', 'bb_mid', 'bb_lower', 'bb_bandwidth', 'bb_percent_b',
            'atr_14', 'supertrend', 'supertrend_dir', 'taker_buy_ratio',
            'log_ret', 'realized_vol_24h'
        ]
        for col in expected_cols:
            self.assertIn(col, df_factors.columns, f'Missing factor column: {col}')
        
        # 确保计算结果不是全 NaN
        self.assertFalse(df_factors['rsi_14'].dropna().empty)
        self.assertFalse(df_factors['macd'].dropna().empty)

    def test_strategies(self):
        """测试趋势策略信号生成"""
        sig_supertrend = supertrend_strategy(self.df.copy())
        self.assertEqual(len(sig_supertrend), len(self.df))
        self.assertTrue(set(sig_supertrend.unique()).issubset({-1.0, 0.0, 1.0}))

        sig_dual_ema = dual_ema_trend_strategy(self.df.copy())
        self.assertEqual(len(sig_dual_ema), len(self.df))
        self.assertTrue(set(sig_dual_ema.unique()).issubset({-1.0, 0.0, 1.0}))

    def test_backtester(self):
        """测试逐笔/逐根回测引擎逻辑与指标计算"""
        signals = supertrend_strategy(self.df.copy())
        backtester = CryptoBacktester(initial_capital=10000.0, commission_rate=0.0005, slippage=0.0002)
        res = backtester.run(self.df, signals)
        
        self.assertIn('metrics', res)
        metrics = res['metrics']
        for key in ['Total Return', 'Sharpe Ratio', 'Max Drawdown', 'Win Rate']:
            self.assertIn(key, metrics)
        
        # 检查回测输出 DataFrame
        self.assertIn('result_df', res)
        self.assertEqual(len(res['result_df']), len(self.df))

    @patch('crypto_quant.data_fetcher._http_get')
    def test_data_fetcher_mock(self, mock_http_get):
        """使用 Mock 测试数据解析逻辑，杜绝网络封锁与外网请求依赖"""
        # 构造标准的 Binance 12 列 K 线响应结构
        mock_http_get.return_value = [
            [
                1704067200000, "42000.0", "42500.0", "41800.0", "42300.0", "120.5",
                1704070799999, "5100000.0", 1500, "65.2", "2760000.0", "0"
            ]
        ]

        df = fetch_klines('BTCUSDT', interval='1h', limit=1)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]['close'], 42300.0)
        self.assertEqual(df.iloc[0]['volume'], 120.5)

    def test_transformer_forward(self):
        """测试 Spatio-Temporal Transformer 模型的张量输入与前向传播"""
        num_assets = 4
        in_features = 23
        lookback = 12
        batch_size = 2

        model = CryptoSTTransformer(
            num_assets=num_assets,
            in_features=in_features,
            lookback=lookback,
            d_model=32,
            n_heads=4,
            num_layers=1,
            dropout=0.1
        )
        model.eval()

        # 构造合成张量 (batch, num_assets, seq_len=lookback, in_features)
        dummy_input = torch.randn(batch_size, num_assets, lookback, in_features)
        with torch.no_grad():
            outputs = model(dummy_input)

        # 检查输出形状
        self.assertIn('pred_4h', outputs)
        self.assertIn('prob_up', outputs)
        self.assertEqual(outputs['pred_4h'].shape, (batch_size, num_assets))
        self.assertFalse(torch.isnan(outputs['pred_4h']).any())


if __name__ == '__main__':
    unittest.main()
