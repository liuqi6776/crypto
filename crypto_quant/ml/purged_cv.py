# -*- coding: utf-8 -*-
"""
Purged Forward-Rolling Time-Series Cross-Validation
滚动净化时间序列交叉验证器
===================================================
1. Strict chronologically forward-rolling expanding windows.
2. Synchronous timestamp partitioning across all portfolio assets (no cross-asset leakage).
3. Purge buffer between train and test windows to eliminate holding-period label overlap.
4. Total prohibition of random shuffling or k-fold data permutation.
"""

from typing import List, Tuple, Generator
import pandas as pd
import numpy as np


class PurgedRollingTimeSeriesSplit:
    """
    Purged Forward-Rolling Time-Series Cross-Validator.
    """
    def __init__(
        self,
        n_splits: int = 5,
        purge_bars: int = 12,           # 12 bars holding window
        bar_duration_minutes: int = 5,  # 5-minute bars
        min_train_ratio: float = 0.35,  # initial training slice ratio
    ):
        self.n_splits = n_splits
        self.purge_timedelta = pd.Timedelta(minutes=purge_bars * bar_duration_minutes)
        self.min_train_ratio = min_train_ratio

    def split(self, df_events: pd.DataFrame) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        Yield (train_indices, test_indices) tuples across expanding chronological slices.
        """
        if df_events.empty:
            return

        # Ensure sorted by timestamp
        df_sorted = df_events.sort_values("timestamp").reset_index(drop=True)
        timestamps = pd.to_datetime(df_sorted["timestamp"])
        min_time = timestamps.min()
        max_time = timestamps.max()
        total_span = max_time - min_time

        # Start of testing begins after min_train_ratio
        test_span = total_span * (1.0 - self.min_train_ratio)
        fold_test_duration = test_span / self.n_splits

        for fold in range(self.n_splits):
            train_end_time = min_time + total_span * self.min_train_ratio + fold * fold_test_duration
            test_start_time = train_end_time + self.purge_timedelta
            test_end_time = train_end_time + fold_test_duration

            # Purge gap ensures test_start_time is strictly after train_end_time + purge_timedelta
            train_mask = (timestamps <= train_end_time)
            test_mask = (timestamps >= test_start_time) & (timestamps <= test_end_time)

            train_idx = np.where(train_mask)[0]
            test_idx = np.where(test_mask)[0]

            if len(train_idx) > 0 and len(test_idx) > 0:
                yield train_idx, test_idx
