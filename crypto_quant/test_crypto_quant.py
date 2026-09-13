"""
Automated Unit and Integration Tests for Crypto Quant Engine
加密货币量化交易引擎自动化单元与集成测试
"""

import unittest
import pandas as pd
import numpy as np
from crypto_quant.data_fetcher import fetch_klines, fetch_24h_ticker
from crypto_quant.factors import compute_all_factors
from crypto_quant.backtester import CryptoBacktester
from crypto_quant.strategies import dual_ema_trend_strategy, supertrend_strategy

class TestCryptoQuant(unittest.TestCase):
    def test_data_fetcher(self):
        """Test Binance live public klines fetching."""
        df = fetch_klines("BTCUSDT", interval="1h", limit=10)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 10)
        for col in ["open", "high", "low", "close", "volume"]:
            self.assertIn(col, df.columns)

    def test_factor_computation(self):
        """Test factor computation."""
        df = fetch_klines("BTCUSDT", interval="1h", limit=50)
        df_factors = compute_all_factors(df)
        expected_cols = ["macd", "rsi_14", "bb_bandwidth", "supertrend_dir", "taker_buy_ratio"]
        for col in expected_cols:
            self.assertIn(col, df_factors.columns)

    def test_backtester(self):
        """Test backtester execution."""
        df = fetch_klines("BTCUSDT", interval="1h", limit=100)
        signals = supertrend_strategy(df)
        backtester = CryptoBacktester(initial_capital=10000.0)
        res = backtester.run(df, signals)
        self.assertIn("metrics", res)
        self.assertIn("Total Return", res["metrics"])
        self.assertIn("Sharpe Ratio", res["metrics"])
        self.assertIn("Max Drawdown", res["metrics"])

if __name__ == "__main__":
    unittest.main()
