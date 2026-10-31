"""Causal 2025 & 2026 account backtester for 0-fee Maker ML strategies (Y0 + Y1).

Implements:
1. S1_HYSTERESIS_MAKER: Directional entry from Y0 composite score + Y1 liquidation gate,
   with state hysteresis to minimize unnecessary turnover, evaluated across cost tiers:
   - 0.0 bp/side (0 bp RT: pure 0-fee Maker upper bound)
   - 0.5 bp/side (1 bp RT: 0-fee Maker + realistic queue adverse selection)
   - 1.0 bp/side (2 bp RT: 0-fee Maker + heavy adverse selection)
   - 6.0 bp/side (12 bp RT: standard Taker baseline)
2. S2_PASSIVE_LIMIT_MAKER: Strict Post-Only limit order fill simulation inside bar i+1
   (P_limit = O_{i+1} * (1 - side * alpha * Y1_range_hat), strict through-price fill check,
   SL-first intrabar ambiguity rule, 0-bp Maker TP vs 6-bp Taker SL).
3. Leverage & Liquidation Stress Grid (1x, 3x, 5x, 10x, 20x + Dynamic 1/Y1 sizing),
   measuring exact liquidation count and max drawdown reduction from the Y1 gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from research.zero_fee_maker_ml_v1.code.features import HORIZON_BARS, DatasetBundle
from research.zero_fee_maker_ml_v1.code.models import HorizonPredictions


def _funding_sum_between(
    funding_ms: np.ndarray,
    funding_rate: np.ndarray,
    t_start_ms: int,
    t_end_ms: int,
) -> float:
    """Sum observed 8h funding rates strictly inside (t_start_ms, t_end_ms]."""
    i0 = int(np.searchsorted(funding_ms, t_start_ms, side="right"))
    i1 = int(np.searchsorted(funding_ms, t_end_ms, side="right"))
    if i1 <= i0:
        return 0.0
    return float(np.sum(funding_rate[i0:i1]))


def _compute_account_metrics(
    trade_net_rets: np.ndarray,
    trade_gross_rets: np.ndarray,
    trade_funding_rets: np.ndarray,
    trade_holding_bars: np.ndarray,
    trade_entry_ms: np.ndarray,
    trade_Sides: np.ndarray,
    trade_liquidated: np.ndarray,
    total_bars_in_period: int,
    leverage: float = 1.0,
) -> Dict[str, float]:
    n_trades = len(trade_net_rets)
    if n_trades == 0:
        return {
            "n_trades": 0,
            "total_return_pct": 0.0,
            "cagr_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_gross_bp": 0.0,
            "avg_net_bp": 0.0,
            "funding_drag_pct": 0.0,
            "exposure_pct": 0.0,
            "liquidations": 0,
            "positive_months_ratio": 0.0,
        }

    lev_rets = np.clip(trade_net_rets * leverage, -0.999, 10.0)
    eq = np.cumprod(1.0 + lev_rets)
    total_ret = float(eq[-1] - 1.0)
    peaks = np.maximum.accumulate( np.concatenate([[1.0], eq]) )
    dd = (np.concatenate([[1.0], eq]) - peaks) / peaks
    max_dd = float(np.min(dd))

    years = max(total_bars_in_period / (288.0 * 365.0), 0.1)
    cagr = float((eq[-1] ** (1.0 / years)) - 1.0) if eq[-1] > 0 else -1.0

    # Annualized Sharpe from trade returns scaled by trades per year
    trades_per_year = n_trades / years
    mu = float(np.mean(lev_rets))
    sd = float(np.std(lev_rets)) + 1e-12
    sharpe = float((mu / sd) * np.sqrt(trades_per_year))

    pos_sum = float(np.sum(lev_rets[lev_rets > 0]))
    neg_sum = float(-np.sum(lev_rets[lev_rets < 0]))
    pf = float(pos_sum / neg_sum) if neg_sum > 1e-12 else (99.0 if pos_sum > 0 else 0.0)

    # Monthly consistency
    months = pd.to_datetime(trade_entry_ms, unit="ms", utc=True).to_period("M")
    df_m = pd.DataFrame({"m": months, "r": lev_rets}).groupby("m")["r"].apply(lambda s: float(np.prod(1.0 + s) - 1.0))
    pos_m_ratio = float((df_m > 0).mean()) if len(df_m) > 0 else 0.0

    return {
        "n_trades": int(n_trades),
        "total_return_pct": round(total_ret * 100.0, 2),
        "cagr_pct": round(cagr * 100.0, 2),
        "max_drawdown_pct": round(max_dd * 100.0, 2),
        "sharpe": round(sharpe, 2),
        "profit_factor": round(min(pf, 99.0), 3),
        "win_rate": round(float(np.mean(lev_rets > 0)) * 100.0, 2),
        "avg_gross_bp": round(float(np.mean(trade_gross_rets)) * 1e4, 2),
        "avg_net_bp": round(float(np.mean(trade_net_rets)) * 1e4, 2),
        "funding_drag_pct": round(float(np.sum(trade_funding_rets * leverage)) * 100.0, 2),
        "exposure_pct": round(float(np.sum(trade_holding_bars) / max(1, total_bars_in_period)) * 100.0, 2),
        "liquidations": int(np.sum(trade_liquidated)),
        "positive_months_ratio": round(pos_m_ratio * 100.0, 1),
    }


def _select_scores(pred: HorizonPredictions, score_source: str) -> Tuple[np.ndarray, np.ndarray]:
    if score_source == "comp":
        return pred.val_score_comp, pred.test_score_comp
    if score_source == "sign_hgb":
        return pred.val_p_pos_hgb, pred.test_p_pos_hgb
    if score_source == "tail_hgb":
        return pred.val_score_tail_hgb, pred.test_score_tail_hgb
    if score_source == "cat":
        return pred.val_p_pos_cat, pred.test_p_pos_cat
    if score_source == "lin":
        return pred.val_p_pos_lin, pred.test_p_pos_lin
    raise ValueError(f"Unknown score_source: {score_source}")


def simulate_hysteresis_maker(
    bundle: DatasetBundle,
    pred: HorizonPredictions,
    entry_quantile: float = 0.92,
    hold_quantile: float = 0.60,
    use_y1_gate: bool = True,
    y1_quantile_cap: float = 0.85,
    one_way_cost_bp: float = 0.5,
    leverage: float = 1.0,
    safety_gamma: float = 1.5,
    dynamic_y1_sizing: bool = False,
    direction_mode: str = "both",  # "both", "long_only", "short_only"
    score_source: str = "comp",
) -> Dict[str, float]:
    """Simulate S1_HYSTERESIS_MAKER on Test set using thresholds calibrated strictly on Validation set."""
    k_bars = HORIZON_BARS[pred.horizon_min]
    va_sc, te_sc = _select_scores(pred, score_source)

    # Thresholds calibrated on Validation set only
    th_long_en = float(np.quantile(va_sc, entry_quantile))
    th_short_en = float(np.quantile(va_sc, 1.0 - entry_quantile))
    th_long_hold = float(np.quantile(va_sc, hold_quantile))
    th_short_hold = float(np.quantile(va_sc, 1.0 - hold_quantile))

    y1_cap_long = float(np.quantile(pred.val_y1_mae_long_q90, y1_quantile_cap))
    y1_cap_short = float(np.quantile(pred.val_y1_mae_short_q90, y1_quantile_cap))
    med_y1_val = float(np.median(pred.val_y1_mae_long_q90))

    # Map test indices back to full bundle arrays
    te_indices = np.flatnonzero(pred.test_mask)
    n_te = len(te_indices)
    idx_ms = (bundle.index.astype("int64") // 10**6).to_numpy()
    o_raw = bundle.open_raw
    h_raw = bundle.high_raw
    l_raw = bundle.low_raw
    c_raw = bundle.close_raw

    cost_rate = one_way_cost_bp * 1e-4
    liq_dist_base = max(0.0025, (1.0 / max(leverage, 1.0)) - 0.006)

    net_rets: List[float] = []
    gross_rets: List[float] = []
    funding_rets: List[float] = []
    hold_bars_list: List[int] = []
    entry_ms_list: List[int] = []
    sides_list: List[int] = []
    liq_list: List[int] = []

    p = 0
    while p < n_te - k_bars - 1:
        g_idx = te_indices[p]
        sc = te_sc[p]
        y1_l = pred.test_y1_mae_long_q90[p]
        y1_s = pred.test_y1_mae_short_q90[p]

        side = 0
        if sc >= th_long_en and direction_mode in ("both", "long_only"):
            if (not use_y1_gate) or (y1_l <= y1_cap_long and y1_l <= liq_dist_base / safety_gamma):
                side = 1
        elif sc <= th_short_en and direction_mode in ("both", "short_only"):
            if (not use_y1_gate) or (y1_s <= y1_cap_short and y1_s <= liq_dist_base / safety_gamma):
                side = -1

        if side == 0:
            p += 1
            continue

        # Enter at bar g_idx + 1 open
        entry_bar = g_idx + 1
        entry_price = o_raw[entry_bar]
        entry_time_ms = int(idx_ms[entry_bar])
        y1_entry = y1_l if side == 1 else y1_s

        # Dynamic inverse-Y1 position sizing multiplier (relative to nominal leverage)
        size_mult = 1.0
        if dynamic_y1_sizing:
            size_mult = float(np.clip(med_y1_val / (y1_entry + 1e-6), 0.25, 1.50))
        eff_lev = leverage * size_mult
        eff_liq_dist = max(0.0025, (1.0 / max(eff_lev, 1.0)) - 0.006)

        # Hold in steps of k_bars as long as hysteresis condition holds and not liquidated
        cur_p = p
        exit_bar = entry_bar + k_bars
        liquidated = 0
        while True:
            step_start = te_indices[cur_p] + 1
            step_end = min(step_start + k_bars, len(o_raw) - 1)
            # Check intrabar worst excursion over [step_start .. step_end - 1]
            if side == 1:
                min_l = float(np.min(l_raw[step_start:step_end]))
                mae = (entry_price - min_l) / entry_price
            else:
                max_h = float(np.max(h_raw[step_start:step_end]))
                mae = (max_h - entry_price) / entry_price

            if mae >= eff_liq_dist:
                liquidated = 1
                exit_bar = step_end
                break

            next_p = cur_p + k_bars
            if next_p >= n_te - k_bars - 1:
                exit_bar = step_end
                break

            # Check hysteresis hold signal at next decision point
            next_sc = te_sc[next_p]
            next_y1 = pred.test_y1_mae_long_q90[next_p] if side == 1 else pred.test_y1_mae_short_q90[next_p]
            keep_holding = (
                (side == 1 and next_sc >= th_long_hold)
                or (side == -1 and next_sc <= th_short_hold)
            )
            if use_y1_gate and next_y1 > eff_liq_dist / safety_gamma:
                keep_holding = False

            if keep_holding and (step_end - entry_bar) < 96:  # cap single continuous hold at 8 hours
                cur_p = next_p
            else:
                exit_bar = step_end
                break

        exit_price = o_raw[exit_bar] if exit_bar < len(o_raw) else c_raw[-1]
        exit_time_ms = int(idx_ms[min(exit_bar, len(idx_ms) - 1)])

        if liquidated:
            gross_r = -eff_liq_dist
            fund_r = 0.0
            net_r = (-0.999 / max(leverage, 1.0))
        else:
            gross_r = side * (exit_price - entry_price) / entry_price * size_mult
            fund_sum = _funding_sum_between(bundle.funding_ms, bundle.funding_rate, entry_time_ms, exit_time_ms)
            fund_r = -side * fund_sum * size_mult
            net_r = gross_r + fund_r - (2.0 * cost_rate * size_mult)

        net_rets.append(float(net_r))
        gross_rets.append(float(gross_r))
        funding_rets.append(float(fund_r))
        hold_bars_list.append(int(exit_bar - entry_bar))
        entry_ms_list.append(entry_time_ms)
        sides_list.append(side)
        liq_list.append(liquidated)

        # Advance pointer to first bar after exit
        p = int(np.searchsorted(te_indices, exit_bar, side="left"))

    return _compute_account_metrics(
        np.asarray(net_rets, dtype=float),
        np.asarray(gross_rets, dtype=float),
        np.asarray(funding_rets, dtype=float),
        np.asarray(hold_bars_list, dtype=int),
        np.asarray(entry_ms_list, dtype=np.int64),
        np.asarray(sides_list, dtype=int),
        np.asarray(liq_list, dtype=int),
        total_bars_in_period=n_te,
        leverage=leverage,
    )


def simulate_passive_limit_maker(
    bundle: DatasetBundle,
    pred: HorizonPredictions,
    entry_quantile: float = 0.92,
    alpha_entry_offset: float = 0.15,
    k_tp: float = 0.85,
    k_sl: float = 1.10,
    maker_fee_bp: float = 0.0,
    taker_stop_bp: float = 6.0,
    use_y1_gate: bool = True,
) -> Dict[str, float]:
    """Simulate S2_PASSIVE_LIMIT_MAKER with strict Post-Only through-price fills and SL-first ambiguity."""
    k_bars = HORIZON_BARS[pred.horizon_min]
    va_sc = pred.val_score_comp
    te_sc = pred.test_score_comp

    th_long = float(np.quantile(va_sc, entry_quantile))
    th_short = float(np.quantile(va_sc, 1.0 - entry_quantile))
    y1_cap_l = float(np.quantile(pred.val_y1_mae_long_q90, 0.85))
    y1_cap_s = float(np.quantile(pred.val_y1_mae_short_q90, 0.85))

    te_indices = np.flatnonzero(pred.test_mask)
    n_te = len(te_indices)
    idx_ms = (bundle.index.astype("int64") // 10**6).to_numpy()
    o_raw = bundle.open_raw
    h_raw = bundle.high_raw
    l_raw = bundle.low_raw
    c_raw = bundle.close_raw

    maker_cost = maker_fee_bp * 1e-4
    taker_cost = taker_stop_bp * 1e-4

    net_rets: List[float] = []
    gross_rets: List[float] = []
    funding_rets: List[float] = []
    hold_bars_list: List[int] = []
    entry_ms_list: List[int] = []
    sides_list: List[int] = []
    liq_list: List[int] = []

    n_signals = 0
    n_filled = 0
    n_tp_exits = 0
    n_sl_exits = 0

    p = 0
    while p < n_te - k_bars - 1:
        g_idx = te_indices[p]
        sc = te_sc[p]
        y1_rng = pred.test_y1_range_mean[p]
        y1_l = pred.test_y1_mae_long_q90[p]
        y1_s = pred.test_y1_mae_short_q90[p]

        side = 0
        if sc >= th_long and ((not use_y1_gate) or y1_l <= y1_cap_l):
            side = 1
        elif sc <= th_short and ((not use_y1_gate) or y1_s <= y1_cap_s):
            side = -1

        if side == 0:
            p += 1
            continue

        n_signals += 1
        eb = g_idx + 1
        o_eb = o_raw[eb]
        h_eb = h_raw[eb]
        l_eb = l_raw[eb]

        offset = np.clip(alpha_entry_offset * y1_rng, 0.0003, 0.0040)
        tp_dist = np.clip(k_tp * y1_rng, 0.0012, 0.0250)
        sl_dist = np.clip(k_sl * y1_rng, 0.0015, 0.0300)

        if side == 1:
            p_lim = o_eb * (1.0 - offset)
            filled = (l_eb < p_lim) and (o_eb >= p_lim)
        else:
            p_lim = o_eb * (1.0 + offset)
            filled = (h_eb > p_lim) and (o_eb <= p_lim)

        if not filled:
            p += 1
            continue

        n_filled += 1
        p_tp = p_lim * (1.0 + side * tp_dist)
        p_sl = p_lim * (1.0 - side * sl_dist)
        entry_time_ms = int(idx_ms[eb])

        # Check if entry bar itself already breached SL (adverse selection blow-through)
        exit_bar = eb + k_bars
        exit_price = c_raw[min(eb + k_bars - 1, len(c_raw) - 1)]
        exit_fee = maker_cost  # passive close at horizon end

        if (side == 1 and l_eb <= p_sl) or (side == -1 and h_eb >= p_sl):
            exit_bar = eb + 1
            exit_price = p_sl
            exit_fee = taker_cost
            n_sl_exits += 1
        else:
            # Scan subsequent bars [eb+1 .. eb+k_bars-1]
            for b_step in range(eb + 1, min(eb + k_bars, len(o_raw))):
                hb = h_raw[b_step]
                lb = l_raw[b_step]
                sl_hit = (lb <= p_sl) if side == 1 else (hb >= p_sl)
                tp_hit = (hb > p_tp) if side == 1 else (lb < p_tp)
                # Conservative rule: SL checked BEFORE TP on same bar
                if sl_hit:
                    exit_bar = b_step + 1
                    exit_price = p_sl
                    exit_fee = taker_cost
                    n_sl_exits += 1
                    break
                if tp_hit:
                    exit_bar = b_step + 1
                    exit_price = p_tp
                    exit_fee = maker_cost
                    n_tp_exits += 1
                    break

        exit_time_ms = int(idx_ms[min(exit_bar, len(idx_ms) - 1)])
        gross_r = side * (exit_price - p_lim) / p_lim
        fund_sum = _funding_sum_between(bundle.funding_ms, bundle.funding_rate, entry_time_ms, exit_time_ms)
        fund_r = -side * fund_sum
        net_r = gross_r + fund_r - maker_cost - exit_fee

        net_rets.append(float(net_r))
        gross_rets.append(float(gross_r))
        funding_rets.append(float(fund_r))
        hold_bars_list.append(int(max(1, exit_bar - eb)))
        entry_ms_list.append(entry_time_ms)
        sides_list.append(side)
        liq_list.append(0)

        p = int(np.searchsorted(te_indices, exit_bar, side="left"))

    res = _compute_account_metrics(
        np.asarray(net_rets, dtype=float),
        np.asarray(gross_rets, dtype=float),
        np.asarray(funding_rets, dtype=float),
        np.asarray(hold_bars_list, dtype=int),
        np.asarray(entry_ms_list, dtype=np.int64),
        np.asarray(sides_list, dtype=int),
        np.asarray(liq_list, dtype=int),
        total_bars_in_period=n_te,
        leverage=1.0,
    )
    res["fill_rate_pct"] = round((n_filled / max(1, n_signals)) * 100.0, 1)
    res["tp_exit_pct"] = round((n_tp_exits / max(1, n_filled)) * 100.0, 1)
    res["sl_exit_pct"] = round((n_sl_exits / max(1, n_filled)) * 100.0, 1)
    return res


def simulate_multi_horizon_consensus(
    bundle: DatasetBundle,
    preds_by_h: Dict[int, HorizonPredictions],
    base_hold_min: int = 30,
    entry_quantile: float = 0.93,
    hold_quantile: float = 0.58,
    one_way_cost_bp: float = 0.5,
    leverage: float = 1.0,
    use_y1_gate: bool = True,
    dynamic_y1_sizing: bool = False,
) -> Dict[str, float]:
    """Combine Y0 directional scores across {5m, 15m, 30m, 60m} with 60m Y1 liquidation gating."""
    p30 = preds_by_h[base_hold_min]
    p60 = preds_by_h[60]

    # Build multi-horizon consensus score (weighted toward 30m and 60m signal-to-noise)
    weights = {5: 0.10, 15: 0.20, 30: 0.35, 60: 0.35}
    va_blend = np.zeros_like(p30.val_score_comp)
    te_blend = np.zeros_like(p30.test_score_comp)
    for h_min, w in weights.items():
        ph = preds_by_h[h_min]
        va_blend += w * ph.val_score_comp
        te_blend += w * ph.test_score_comp

    # Clone p30 container with multi-horizon consensus score and 60m Y1 tail gate
    consensus_pred = HorizonPredictions(
        horizon_min=base_hold_min,
        fold_name=p30.fold_name,
        year=p30.year,
        tau_long=p30.tau_long,
        tau_short=p30.tau_short,
        val_mask=p30.val_mask,
        test_mask=p30.test_mask,
        val_p_pos_hgb=p30.val_p_pos_hgb,
        val_p_pos_cat=p30.val_p_pos_cat,
        val_p_pos_lin=p30.val_p_pos_lin,
        val_p_pos_ens=p30.val_p_pos_ens,
        val_score_tail_hgb=p30.val_score_tail_hgb,
        val_ret_pred_hgb=p30.val_ret_pred_hgb,
        val_score_comp=va_blend,
        val_y1_range_mean=p30.val_y1_range_mean,
        val_y1_mae_long_q90=p60.val_y1_mae_long_q90,
        val_y1_mae_short_q90=p60.val_y1_mae_short_q90,
        test_p_pos_hgb=p30.test_p_pos_hgb,
        test_p_pos_cat=p30.test_p_pos_cat,
        test_p_pos_lin=p30.test_p_pos_lin,
        test_p_pos_ens=p30.test_p_pos_ens,
        test_score_tail_hgb=p30.test_score_tail_hgb,
        test_ret_pred_hgb=p30.test_ret_pred_hgb,
        test_score_comp=te_blend,
        test_y1_range_mean=p30.test_y1_range_mean,
        test_y1_mae_long_q90=p60.test_y1_mae_long_q90,
        test_y1_mae_short_q90=p60.test_y1_mae_short_q90,
        metrics=p30.metrics,
        top_features_y0=p30.top_features_y0,
        top_features_y1=p30.top_features_y1,
    )
    return simulate_hysteresis_maker(
        bundle=bundle,
        pred=consensus_pred,
        entry_quantile=entry_quantile,
        hold_quantile=hold_quantile,
        use_y1_gate=use_y1_gate,
        y1_quantile_cap=0.85,
        one_way_cost_bp=one_way_cost_bp,
        leverage=leverage,
        dynamic_y1_sizing=dynamic_y1_sizing,
        score_source="comp",
    )

