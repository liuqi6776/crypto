# -*- coding: utf-8 -*-
"""
Four-Tier Progressive Model Hierarchy & Decile Expectancy Calibration
四级递进模型体系与十分位期望值校准分析器
=====================================================================
1. Group 0: Existing Strict Pullback Rule Baseline
2. Group 1: Fixed Post-Congestion Directional Rule
3. Group 2: Calibrated Logistic Regression (L1/L2 Regularization)
4. Group 3: Regularized Gradient Boosted Trees (XGBoost)
5. Out-of-fold probability calibration & decile expectancy audit
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.calibration import CalibratedClassifierCV
from xgboost import XGBClassifier, XGBRegressor


FEATURE_COLUMNS = [
    "ma_order_type",
    "ma_cross_count_12",
    "congestion_ratio",
    "congestion_ratio_delta_3",
    "price_location",
    "dist_to_u",
    "dist_to_l",
    "dist_to_ma200",
    "ma20_slope_3",
    "ma20_slope_6",
    "ma20_slope_12",
    "ma50_slope_3",
    "ma50_slope_6",
    "ma50_slope_12",
    "ma100_slope_3",
    "ma100_slope_6",
    "ma100_slope_12",
    "ma200_slope_12",
    "atr_ratio",
    "vol_ratio_20",
    "taker_buy_ratio",
    "candle_body_ratio",
    "upper_shadow_ratio",
    "lower_shadow_ratio",
]


def evaluate_fixed_post_congestion_rule(df_events: pd.DataFrame) -> pd.DataFrame:
    """
    Group 1 Baseline: Fixed heuristic direction immediately upon congestion.
    - If Close > MA200 and MA200 slope > 0: Action = BUY (1)
    - If Close < MA200 and MA200 slope < 0: Action = SELL (2)
    - Else: FLAT (0)
    """
    preds = []
    realized_rs = []
    for _, row in df_events.iterrows():
        c_above = row["dist_to_ma200"] > 0
        slope_pos = row["ma200_slope_12"] > 0

        if c_above and slope_pos:
            action = 1
            realized_r = row["long_net_r"]
        elif (not c_above) and (not slope_pos):
            action = 2
            realized_r = row["short_net_r"]
        else:
            action = 0
            realized_r = 0.0

        preds.append(action)
        realized_rs.append(realized_r)

    res = df_events.copy()
    res["pred_action"] = preds
    res["realized_net_r"] = realized_rs
    res["pred_score"] = 0.5  # flat score
    return res


class CongestionMLPipeline:
    """
    Progressive ML Classifier & Decile Expectancy Evaluator.
    """
    def __init__(self, model_type: str = "xgboost"):
        self.model_type = model_type.lower()
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.feature_cols = FEATURE_COLUMNS
        self.model = None
        self.classes_ = None

    def fit(self, X_train: pd.DataFrame, y_train: pd.Series):
        """Fit model with strict feature pre-processing."""
        X_feats = X_train[self.feature_cols].copy()

        y_enc = self.label_encoder.fit_transform(y_train)
        self.classes_ = self.label_encoder.classes_
        counts = pd.Series(y_enc).value_counts()
        min_class_samples = counts.min() if len(counts) > 0 else 0

        if self.model_type == "logistic_regression":
            X_scaled = self.scaler.fit_transform(X_feats)
            base_lr = LogisticRegression(
                C=0.1,
                penalty="l2",
                solver="lbfgs",
                max_iter=1000,
                class_weight="balanced",
                random_state=42,
            )
            if min_class_samples >= 3 and len(counts) >= 2:
                self.model = CalibratedClassifierCV(base_lr, method="sigmoid", cv=min(3, min_class_samples))
                self.model.fit(X_scaled, y_enc)
            else:
                base_lr.fit(X_scaled, y_enc)
                self.model = base_lr

        elif self.model_type == "xgboost":
            xgb = XGBClassifier(
                n_estimators=100,
                max_depth=3,
                learning_rate=0.03,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_lambda=3.0,
                reg_alpha=1.0,
                random_state=42,
                eval_metric="mlogloss",
            )
            if min_class_samples >= 3 and len(counts) >= 2:
                self.model = CalibratedClassifierCV(xgb, method="sigmoid", cv=min(3, min_class_samples))
                self.model.fit(X_feats, y_enc)
            else:
                xgb.fit(X_feats, y_enc)
                self.model = xgb
        else:
            raise ValueError(f"Unknown model_type: {self.model_type}")

    def predict_proba(self, X_test: pd.DataFrame) -> np.ndarray:
        """Predict calibrated multi-class probabilities [P(FLAT), P(BUY), P(SELL)]."""
        X_feats = X_test[self.feature_cols].copy()
        if self.model_type == "logistic_regression":
            X_scaled = self.scaler.transform(X_feats)
            return self.model.predict_proba(X_scaled)
        else:
            return self.model.predict_proba(X_feats)

    def evaluate_test_set(
        self,
        df_test: pd.DataFrame,
        confidence_threshold: float = 0.40,
    ) -> pd.DataFrame:
        """
        Generate out-of-fold predictions, action decisions, and realized net R.
        """
        if df_test.empty:
            return df_test

        probas = self.predict_proba(df_test)
        # Class 0: FLAT, Class 1: BUY, Class 2: SELL
        # Handle case where fewer classes are observed in training fold
        classes = list(self.model.classes_)
        prob_dict = {c: probas[:, i] for i, c in enumerate(classes)}

        p_flat = prob_dict.get(0, np.zeros(len(df_test)))
        p_buy = prob_dict.get(1, np.zeros(len(df_test)))
        p_sell = prob_dict.get(2, np.zeros(len(df_test)))

        actions = []
        realized_rs = []
        scores = []

        for idx, (_, row) in enumerate(df_test.iterrows()):
            pb = p_buy[idx]
            ps = p_sell[idx]

            # Highest confidence non-flat action
            if pb > ps and pb >= confidence_threshold:
                act = 1
                r = row["long_net_r"]
                score = pb
            elif ps > pb and ps >= confidence_threshold:
                act = 2
                r = row["short_net_r"]
                score = ps
            else:
                act = 0
                r = 0.0
                score = max(pb, ps)

            actions.append(act)
            realized_rs.append(r)
            scores.append(score)

        res = df_test.copy()
        res["prob_flat"] = np.round(p_flat, 4)
        res["prob_buy"] = np.round(p_buy, 4)
        res["prob_sell"] = np.round(p_sell, 4)
        res["pred_action"] = actions
        res["pred_score"] = np.round(scores, 4)
        res["realized_net_r"] = realized_rs
        return res


def compute_decile_table(df_evaluated: pd.DataFrame) -> pd.DataFrame:
    """
    Partition test events into 10 prediction confidence deciles and compute audit metrics.
    将预测置信度切分为十分位，严格审计高分组真实扣费后净期望。
    """
    if df_evaluated.empty:
        return pd.DataFrame()

    df = df_evaluated.copy()
    n_bins = min(10, len(df))
    if n_bins < 2:
        return pd.DataFrame()
    df["decile"] = pd.qcut(df["pred_score"].rank(method="first"), q=n_bins, labels=range(1, n_bins + 1))

    rows = []
    for d, grp in df.groupby("decile"):
        trades_taken = grp[grp["pred_action"] != 0]
        n_events = len(grp)
        n_trades = len(trades_taken)
        
        if n_trades > 0:
            rs = trades_taken["realized_net_r"].values
            wins = rs[rs > 0]
            losses = rs[rs <= 0]
            win_rate = (len(wins) / n_trades) * 100.0
            mean_r = float(np.mean(rs))
            median_r = float(np.median(rs))
            gross_win = float(np.sum(wins)) if len(wins) > 0 else 0.0
            gross_loss = float(abs(np.sum(losses))) if len(losses) > 0 else 0.0
            profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (999.0 if gross_win > 0 else 0.0)
            net_r_sum = float(np.sum(rs))
        else:
            win_rate = 0.0
            mean_r = 0.0
            median_r = 0.0
            profit_factor = 0.0
            net_r_sum = 0.0

        rows.append({
            "decile": int(d),
            "events_count": n_events,
            "trades_taken": n_trades,
            "trade_ratio_pct": round((n_trades / n_events) * 100.0, 1),
            "win_rate_pct": round(win_rate, 2),
            "mean_net_r": round(mean_r, 3),
            "median_net_r": round(median_r, 3),
            "profit_factor": round(profit_factor, 2),
            "sum_net_r": round(net_r_sum, 2),
            "avg_pred_score": round(grp["pred_score"].mean(), 4),
        })

    return pd.DataFrame(rows)


def summarize_model_metrics(df_evaluated: pd.DataFrame, model_name: str) -> Dict[str, Any]:
    """Calculate institutional summary metrics for active trades."""
    trades = df_evaluated[df_evaluated["pred_action"] != 0]
    total_events = len(df_evaluated)
    n_trades = len(trades)

    if n_trades == 0:
        return {
            "model_name": model_name,
            "total_events": total_events,
            "trades_taken": 0,
            "trade_rate_pct": 0.0,
            "win_rate_pct": 0.0,
            "avg_net_r": 0.0,
            "median_net_r": 0.0,
            "profit_factor": 0.0,
            "total_net_r": 0.0,
            "expectancy_status": "NO_TRADES",
        }

    rs = trades["realized_net_r"].values
    wins = rs[rs > 0]
    losses = rs[rs <= 0]
    win_rate = (len(wins) / n_trades) * 100.0
    gross_win = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gross_loss = float(abs(np.sum(losses))) if len(losses) > 0 else 0.0
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else 999.0
    avg_r = float(np.mean(rs))
    median_r = float(np.median(rs))
    total_r = float(np.sum(rs))

    return {
        "model_name": model_name,
        "total_events": total_events,
        "trades_taken": n_trades,
        "trade_rate_pct": round((n_trades / total_events) * 100.0, 1),
        "win_rate_pct": round(win_rate, 2),
        "avg_net_r": round(avg_r, 3),
        "median_net_r": round(median_r, 3),
        "profit_factor": round(profit_factor, 2),
        "total_net_r": round(total_r, 2),
        "expectancy_status": "POSITIVE" if avg_r > 0 else "NEGATIVE",
    }
