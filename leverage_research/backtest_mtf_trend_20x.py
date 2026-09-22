# -*- coding: utf-8 -*-
"""
Multi-Timeframe Trend Resonance + 20X Isolated-Margin Backtester
多周期趋势共振 + 20 倍隔离保证金全链回测引擎 (SOLUSDT 永续)

Strategy under test (as specified by the user / 用户指定规则):
  1. Trend must align across 1m / 5m / 15m / 1h simultaneously.
  2. Enter with 20X leverage, one position at a time, isolated margin.
  3. Take-profit anchored at the Bollinger UPPER band, stop-loss at the LOWER band,
     both pulled in slightly ("提前止盈 / 提前止损").

Execution realism / 成交真实性:
  - Signal confirmed on a CLOSED 1m bar  ->  filled at the NEXT 1m bar open.
  - Entry & stop-loss are TAKER (0.05% + slippage); take-profit is a resting
    MAKER limit (0.02%) that fills exactly at the band level.
  - Exact intrabar sequencing on OHLC (gap-through open -> stop -> target).
  - Isolated-margin liquidation at entry * (1 -/+ 1/lev + MMR); the whole
    allocated margin is lost when it triggers.
  - Real 8-hour perpetual funding cash flows at 00:00 / 08:00 / 16:00 UTC.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mtf_trend_engine import MTFTrendEngine, build_signals

DATA_DIR = r"D:\Convertible_Bond_data\crypto_data\history"
KLINE_PATH = os.path.join(DATA_DIR, "futures_1m", "SOLUSDT_futures_1m_continuous.parquet")
FUNDING_PATH = os.path.join(DATA_DIR, "funding_rate", "SOLUSDT_funding_8h.parquet")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

MMR = 0.005           # SOLUSDT tier-1 maintenance margin rate / 维持保证金率
TAKER_FEE = 0.0005    # 币安 U 本位合约 Taker 0.05%
MAKER_FEE = 0.0002    # 挂单 Maker 0.02%
NORMAL_SLIP = 0.0002  # 市价单正常滑点
STOP_SLIP = 0.0010    # 止损单滑点 (与仓库 execution_model.py 口径一致)
GAP_SLIP = 0.0015     # 跳空穿透滑点


def funding_array(index: pd.DatetimeIndex, fund_map: dict) -> np.ndarray:
    """Funding settles at 00/08/16 UTC; the 1m bar opening there carries the charge."""
    utc = index.tz_convert("UTC")
    mask = (utc.minute == 0) & np.isin(utc.hour, (0, 8, 16))
    arr = np.zeros(len(index), dtype=np.float64)
    if mask.any():
        keys = utc[mask].floor("h")
        arr[mask] = [fund_map.get(k, 0.0) for k in keys]
    return arr


def load_data(start: str, end: str):
    bars = pd.read_parquet(KLINE_PATH)
    bars["open_time"] = pd.to_datetime(bars["timestamp"], unit="ms", utc=True).dt.tz_convert("Asia/Shanghai")
    bars = bars.set_index("open_time").sort_index()
    bars = bars.loc[start:end, ["open", "high", "low", "close", "volume"]]

    funding = pd.read_parquet(FUNDING_PATH)
    funding["fundingTime"] = pd.to_datetime(funding["fundingTime"], utc=True).dt.floor("h")
    fund_map = dict(zip(funding["fundingTime"], funding["fundingRate"]))
    return bars, fund_map


def simulate(
    features: pd.DataFrame,
    tp_tf: str,
    sl_tf: str,
    leverage: float = 20.0,
    margin_frac: float = 0.05,
    tp_pull: float = 0.15,
    sl_pull: float = 0.15,
    max_hold_bars: int = 1440,
    fund_arr: np.ndarray = None,
    min_rr: float = 0.0,
    apply_costs: bool = True,
    entry_mode: str = "immediate",
    entry_tf: str = "1m",
    pull_frac: float = 0.5,
    arm_window: int = 60,
) -> dict:
    """
    Event-driven leveraged simulation. Returns the equity curve, trade list and diagnostics.
    事件驱动杠杆仿真，返回净值曲线、逐笔交易与诊断计数。

    tp_tf / sl_tf : Bollinger band timeframe used for the take-profit / stop-loss anchor.
                    The multi-timeframe ladder is 1m / 5m / 15m / 1h, each with its own
                    upper and lower band, so the two legs are chosen independently.
                    止盈与止损可各自选用不同周期的布林带（4 周期 × 上下轨 = 8 个价位）。
    entry_mode    : 'immediate' -> buy the moment resonance confirms (price is usually
                    already riding the upper band, which crushes the payoff geometry)
                    'pullback'  -> stay armed while resonance holds, and only enter after
                    price retraces into the entry timeframe's lower half of the band
                    回踩入场：共振确认后保持待命，等价格回落到布林带下半区才开多
    pull_frac     : how deep the retrace must reach. 0 = at the mid band, 1 = at the band edge.
    min_rr        : reject an entry unless TP distance / SL distance >= min_rr
    apply_costs   : set False to run a zero-fee / zero-slippage counterfactual
    """
    taker_fee = TAKER_FEE if apply_costs else 0.0
    maker_fee = MAKER_FEE if apply_costs else 0.0
    normal_slip = NORMAL_SLIP if apply_costs else 0.0
    stop_slip = STOP_SLIP if apply_costs else 0.0
    gap_slip = GAP_SLIP if apply_costs else 0.0

    def _tag(tf: str) -> str:
        return tf.replace("m", "M").replace("h", "H")

    tp_tag, sl_tag, en_tag = _tag(tp_tf), _tag(sl_tf), _tag(entry_tf)
    tp_up, tp_lo, tp_mid = (features[f"bb_{k}_{tp_tag}"].values for k in ("up", "lo", "mid"))
    sl_up, sl_lo, sl_mid = (features[f"bb_{k}_{sl_tag}"].values for k in ("up", "lo", "mid"))
    en_up, en_lo, en_mid = (features[f"bb_{k}_{en_tag}"].values for k in ("up", "lo", "mid"))

    long_sig = features["long_signal"].values
    short_sig = features["short_signal"].values

    o = features["open"].values
    h = features["high"].values
    l = features["low"].values
    c = features["close"].values
    idx = features.index

    n = len(features)
    equity_curve = np.empty(n, dtype=np.float64)

    cash = 1.0
    in_pos = False
    direction = 0
    qty = 0.0
    entry_p = 0.0
    tp_p = 0.0
    sl_p = 0.0
    liq_p = 0.0
    entry_bar = 0
    margin_at_risk = 0.0
    tp_dist = 0.0
    sl_dist = 0.0
    armed = 0
    armed_bar = 0

    trades = []
    total_fees = 0.0
    total_funding = 0.0
    liquidations = 0
    skipped_unreachable = 0

    for t in range(n):
        # ---------- 1. manage an open position ----------
        if in_pos:
            exit_price = None
            reason = None
            fee_rate = taker_fee

            if direction == 1:
                if l[t] <= liq_p:
                    exit_price, reason, fee_rate = liq_p, "liquidation", 0.0
                elif o[t] >= tp_p:
                    exit_price, reason, fee_rate = o[t], "take_profit", maker_fee
                elif o[t] <= sl_p:
                    exit_price, reason = o[t] * (1.0 - gap_slip), "stop_loss_gap"
                elif l[t] <= sl_p:
                    exit_price, reason = sl_p * (1.0 - stop_slip), "stop_loss"
                elif h[t] >= tp_p:
                    exit_price, reason, fee_rate = tp_p, "take_profit", maker_fee
            else:
                if h[t] >= liq_p:
                    exit_price, reason, fee_rate = liq_p, "liquidation", 0.0
                elif o[t] <= tp_p:
                    exit_price, reason, fee_rate = o[t], "take_profit", maker_fee
                elif o[t] >= sl_p:
                    exit_price, reason = o[t] * (1.0 + gap_slip), "stop_loss_gap"
                elif h[t] >= sl_p:
                    exit_price, reason = sl_p * (1.0 + stop_slip), "stop_loss"
                elif l[t] <= tp_p:
                    exit_price, reason, fee_rate = tp_p, "take_profit", maker_fee

            if exit_price is None and (t - entry_bar) >= max_hold_bars:
                exit_price, reason = c[t], "timeout"

            if exit_price is not None:
                if reason == "liquidation":
                    cash -= margin_at_risk
                    liquidations += 1
                    pnl_pct = -1.0
                    notional = qty * entry_p
                else:
                    notional = qty * exit_price
                    gross = direction * qty * (exit_price - entry_p)
                    fee = qty * exit_price * fee_rate
                    cash += gross - fee
                    total_fees += fee
                    pnl_pct = gross / margin_at_risk
                trades.append(
                    {
                        "entry_time": idx[entry_bar],
                        "exit_time": idx[t],
                        "direction": direction,
                        "entry_price": entry_p,
                        "exit_price": exit_price,
                        "bars_held": t - entry_bar,
                        "reason": reason,
                        "pnl_pct_of_margin": pnl_pct,
                        "notional": notional,
                        "tp_dist_pct": tp_dist,
                        "sl_dist_pct": sl_dist,
                    }
                )
                in_pos = False
                direction = 0

        # ---------- 2. funding settlement ----------
        if in_pos:
            fr = fund_arr[t]
            if fr != 0.0:
                pay = direction * qty * c[t] * fr
                cash -= pay
                total_funding += pay

        # ---------- 3. mark-to-market equity ----------
        unrealized = direction * qty * (c[t] - entry_p) if in_pos else 0.0
        equity_curve[t] = cash + unrealized

        # ---------- 4. look for a new entry (fill at NEXT bar open) ----------
        if not in_pos:
            if t + 1 >= n:
                continue
            if long_sig[t]:
                armed, armed_bar = 1, t
            elif short_sig[t]:
                armed, armed_bar = -1, t
            if armed != 0 and (t - armed_bar) > arm_window:
                armed = 0

            sig = 0
            if entry_mode == "immediate":
                sig = armed if (long_sig[t] or short_sig[t]) else 0
            elif armed != 0 and np.isfinite(en_mid[t]):
                mid_v, lo_v, up_v = en_mid[t], en_lo[t], en_up[t]
                if armed == 1:
                    trigger = mid_v - pull_frac * (mid_v - lo_v)
                    if c[t] <= trigger:
                        sig = 1
                else:
                    trigger = mid_v + pull_frac * (up_v - mid_v)
                    if c[t] >= trigger:
                        sig = -1

            if sig != 0:
                # Take-profit leg: the selected timeframe's band on the profit side.
                # Stop-loss leg : the selected timeframe's band on the adverse side.
                if sig == 1:
                    tp_base, tp_anchor = tp_up[t], tp_mid[t]
                    sl_base, sl_anchor = sl_lo[t], sl_mid[t]
                    tp = tp_base - (tp_base - tp_anchor) * tp_pull
                    sl = sl_base + (sl_anchor - sl_base) * sl_pull
                else:
                    tp_base, tp_anchor = tp_lo[t], tp_mid[t]
                    sl_base, sl_anchor = sl_up[t], sl_mid[t]
                    tp = tp_base + (tp_anchor - tp_base) * tp_pull
                    sl = sl_base - (sl_base - sl_anchor) * sl_pull

                if not all(np.isfinite(x) for x in (tp, sl)):
                    continue

                fill = o[t + 1] * (1.0 + normal_slip * sig)   # taker market order
                # Reject a trade whose band target is already behind the fill price.
                if (sig == 1 and (tp <= fill or sl >= fill)) or (sig == -1 and (tp >= fill or sl <= fill)):
                    skipped_unreachable += 1
                    continue

                tp_distance = abs(tp - fill) / fill
                sl_distance = abs(fill - sl) / fill
                if tp_distance / sl_distance < min_rr:
                    skipped_unreachable += 1
                    continue

                margin_at_risk = cash * margin_frac
                qty = margin_at_risk * leverage / fill
                fee = qty * fill * taker_fee
                cash -= fee
                total_fees += fee
                entry_p = fill
                tp_p, sl_p = tp, sl
                tp_dist = tp_distance
                sl_dist = sl_distance
                liq_p = fill * (1.0 - 1.0 / leverage + MMR) if sig == 1 else fill * (1.0 + 1.0 / leverage - MMR)
                direction = sig
                entry_bar = t + 1
                in_pos = True

    equity = pd.Series(equity_curve, index=idx, name="equity")
    return {
        "equity": equity,
        "trades": pd.DataFrame(trades),
        "total_fees": total_fees,
        "total_funding": total_funding,
        "liquidations": liquidations,
        "skipped_unreachable": skipped_unreachable,
    }


def compute_metrics(equity: pd.Series, res: dict, initial_notional_leverage: float) -> dict:
    ret = equity.iloc[-1] / equity.iloc[0] - 1.0
    years = (equity.index[-1] - equity.index[0]).total_seconds() / (365.0 * 86400.0)
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0 if years > 0 and equity.iloc[-1] > 0 else -1.0

    daily = equity.resample("1D").last().dropna()
    dret = daily.pct_change().dropna()
    sharpe = dret.mean() / (dret.std() + 1e-12) * np.sqrt(365) if len(dret) > 2 else np.nan

    roll_max = equity.cummax()
    dd = equity / roll_max - 1.0
    mdd = dd.min()
    calmar = cagr / abs(mdd) if mdd < 0 else np.nan

    tr = res["trades"]
    if len(tr):
        wins = tr[tr["pnl_pct_of_margin"] > 0]
        losses = tr[tr["pnl_pct_of_margin"] <= 0]
        win_rate = len(wins) / len(tr)
        gross_win = wins["pnl_pct_of_margin"].sum()
        gross_loss = abs(losses["pnl_pct_of_margin"].sum())
        pf = gross_win / gross_loss if gross_loss > 0 else np.nan
        avg_hold = tr["bars_held"].mean()
        avg_win = wins["pnl_pct_of_margin"].mean() if len(wins) else np.nan
        avg_loss = losses["pnl_pct_of_margin"].mean() if len(losses) else np.nan
        tp_hit = (tr["reason"] == "take_profit").mean()
    else:
        win_rate = pf = avg_hold = avg_win = avg_loss = tp_hit = np.nan

    return {
        "total_return": ret,
        "cagr": cagr,
        "max_drawdown": mdd,
        "daily_sharpe": sharpe,
        "calmar": calmar,
        "trades": len(tr),
        "trades_per_day": len(tr) / (years * 365.0) if years > 0 else np.nan,
        "win_rate": win_rate,
        "profit_factor": pf,
        "avg_win_pct_margin": avg_win,
        "avg_loss_pct_margin": avg_loss,
        "tp_hit_rate": tp_hit,
        "avg_hold_min": avg_hold,
        "avg_tp_dist_pct": tr["tp_dist_pct"].mean() if len(tr) else np.nan,
        "avg_sl_dist_pct": tr["sl_dist_pct"].mean() if len(tr) else np.nan,
        "fees_pct_of_initial_equity": res["total_fees"],
        "funding_pct_of_initial_equity": res["total_funding"],
        "liquidations": res["liquidations"],
        "skipped_signals": res["skipped_unreachable"],
        "years": years,
    }


def build_feature_frame(bars: pd.DataFrame, engine_kwargs: dict, signal_mode: str) -> pd.DataFrame:
    engine = MTFTrendEngine(**engine_kwargs)
    feats = engine.build(bars)
    feats = build_signals(feats, mode=signal_mode)
    feats = pd.concat([bars, feats], axis=1)
    return feats


def run_one(bars, fund_map, fund_arr, engine_kwargs, signal_mode, tp_tf, sl_tf, margin_frac,
            leverage=20.0, min_rr=0.0, apply_costs=True, **sim_kwargs):
    feats = build_feature_frame(bars, engine_kwargs, signal_mode)
    res = simulate(feats, tp_tf, sl_tf, leverage=leverage, margin_frac=margin_frac,
                   fund_arr=fund_arr, min_rr=min_rr, apply_costs=apply_costs, **sim_kwargs)
    m = compute_metrics(res["equity"], res, margin_frac * leverage)
    m.update(
        {
            "signal_mode": signal_mode,
            "tp_tf": tp_tf,
            "sl_tf": sl_tf,
            "adx_threshold": engine_kwargs.get("adx_threshold", 20.0),
            "require_sr_breakout": engine_kwargs.get("require_sr_breakout", False),
            "leverage": leverage,
            "margin_frac": margin_frac,
            "long_signals": int(feats["long_signal"].sum()),
            "short_signals": int(feats["short_signal"].sum()),
            **sim_kwargs,
        }
    )
    return m, res


def run_grid(args):
    """
    Two-stage sweep:
      Stage 1 - entry geometry: immediate vs pullback depth, crossed with the Bollinger
                timeframe used for both legs (same-TF band is the natural band trade).
      Stage 2 - leverage sweep on the best entry geometries.
    """
    bars, fund_map = load_data(args.start, args.end)
    fund_arr = funding_array(bars.index, fund_map)
    print(f"Loaded {len(bars):,} 1m bars  {bars.index[0]} -> {bars.index[-1]}")

    timeframes = ("1m", "5m", "15m", "1h")
    leverages = (1.0, 3.0, 5.0, 10.0, 20.0)
    entry_variants = [
        ("immediate", 0.0),
        ("pullback", 0.0),
        ("pullback", 0.3),
        ("pullback", 0.5),
        ("pullback", 0.8),
    ]
    ref_leverage = 5.0

    feats = build_feature_frame(bars, {"adx_threshold": args.adx_threshold}, args.signal_mode)
    print(
        f"Signal mode={args.signal_mode} adx>={args.adx_threshold} | "
        f"long={int(feats['long_signal'].sum()):,} short={int(feats['short_signal'].sum()):,} "
        f"| margin {args.margin_frac*100:g}% of equity\n"
    )

    rows = []
    header = (
        f"{'entry':<10} {'pull':>5} {'band':>5} | {'return':>11} {'CAGR':>10} {'MDD':>9} "
        f"{'sharpe':>7} {'trades':>7} {'win%':>6} {'PF':>6} {'R:R':>6} {'liq':>4} {'skip':>7}"
    )

    print(f"=== Stage 1: entry geometry @ leverage {ref_leverage:g}x ===")
    print(header)
    print("-" * len(header))
    for mode, pull in entry_variants:
        for tf in timeframes:
            res = simulate(
                feats, tf, tf, leverage=ref_leverage, margin_frac=args.margin_frac,
                fund_arr=fund_arr, entry_mode=mode, entry_tf=tf, pull_frac=pull,
            )
            m = compute_metrics(res["equity"], res, args.margin_frac * ref_leverage)
            tr = res["trades"]
            rr = (tr["tp_dist_pct"].mean() / tr["sl_dist_pct"].mean()) if len(tr) else np.nan
            rows.append(
                {
                    "leverage": ref_leverage,
                    "entry_mode": mode,
                    "pull_frac": pull,
                    "tp_tf": tf,
                    "sl_tf": tf,
                    **m,
                    "realized_rr": rr,
                }
            )
            print(
                f"{mode:<10} {pull:>5.2f} {tf:>5} | {m['total_return']*100:>10.2f}% "
                f"{m['cagr']*100:>9.2f}% {m['max_drawdown']*100:>8.2f}% {m['daily_sharpe']:>7.2f} "
                f"{m['trades']:>7} {m['win_rate']*100:>5.1f}% {m['profit_factor']:>6.3f} "
                f"{rr:>6.3f} {m['liquidations']:>4} {m['skipped_signals']:>7}"
            )
        print()

    stage1 = pd.DataFrame(rows)
    ranked = stage1.sort_values("total_return", ascending=False)
    top = ranked.head(3)
    print("Top 3 entry geometries:")
    print(top[["entry_mode", "pull_frac", "tp_tf", "total_return", "cagr", "max_drawdown",
               "daily_sharpe", "trades", "win_rate", "profit_factor", "realized_rr"]].to_string(index=False))

    print(f"\n=== Stage 2: leverage sweep on the top-3 geometries ===")
    print(f"{'entry':<10} {'pull':>5} {'band':>5} {'lev':>5} | {'return':>11} {'CAGR':>10} "
          f"{'MDD':>9} {'sharpe':>7} {'trades':>7} {'win%':>6} {'liq':>4}")
    print("-" * 96)
    for _, cfg in top.iterrows():
        for lev in leverages:
            res = simulate(
                feats, cfg["tp_tf"], cfg["sl_tf"], leverage=lev, margin_frac=args.margin_frac,
                fund_arr=fund_arr, entry_mode=cfg["entry_mode"], entry_tf=cfg["tp_tf"],
                pull_frac=float(cfg["pull_frac"]),
            )
            m = compute_metrics(res["equity"], res, args.margin_frac * lev)
            tr = res["trades"]
            rr = (tr["tp_dist_pct"].mean() / tr["sl_dist_pct"].mean()) if len(tr) else np.nan
            rows.append(
                {
                    "leverage": lev,
                    "entry_mode": cfg["entry_mode"],
                    "pull_frac": float(cfg["pull_frac"]),
                    "tp_tf": cfg["tp_tf"],
                    "sl_tf": cfg["sl_tf"],
                    **m,
                    "realized_rr": rr,
                }
            )
            print(
                f"{cfg['entry_mode']:<10} {float(cfg['pull_frac']):>5.2f} {cfg['tp_tf']:>5} "
                f"{lev:>5g} | {m['total_return']*100:>10.2f}% {m['cagr']*100:>9.2f}% "
                f"{m['max_drawdown']*100:>8.2f}% {m['daily_sharpe']:>7.2f} {m['trades']:>7} "
                f"{m['win_rate']*100:>5.1f}% {m['liquidations']:>4}"
            )
        print()

    summary = pd.DataFrame(rows)
    out_csv = os.path.join(OUT_DIR, "summary_data", "mtf_trend_band_leverage_grid.csv")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    summary.to_csv(out_csv, index=False)
    print(f"Saved entry-geometry x leverage grid -> {out_csv}")

    print("\nBest 8 overall:")
    print(summary.sort_values("total_return", ascending=False).head(8)[
        ["entry_mode", "pull_frac", "tp_tf", "leverage", "total_return", "cagr", "max_drawdown",
         "daily_sharpe", "trades", "win_rate", "profit_factor", "realized_rr", "liquidations"]
    ].to_string(index=False))
    return summary


def run_diagnose(args):
    """
    Decomposes WHY the strategy loses: is it the signal, the 1:0.04 payoff geometry,
    or the 20X fee friction?
    """
    bars, fund_map = load_data(args.start, args.end)
    fund_arr = funding_array(bars.index, fund_map)
    feats = build_feature_frame(bars, {"adx_threshold": args.adx_threshold}, args.signal_mode)
    print(f"Loaded {len(bars):,} 1m bars | mode={args.signal_mode} adx>={args.adx_threshold} "
          f"tp_band={args.tp_tf} sl_band={args.sl_tf} leverage={args.leverage:g}x")
    print(f"Signals: long={int(feats['long_signal'].sum()):,} short={int(feats['short_signal'].sum()):,}\n")

    scenarios = [
        ("A. As specified (real fees)", dict(apply_costs=True, min_rr=0.0)),
        ("B. Zero fee / zero slippage", dict(apply_costs=False, min_rr=0.0)),
        ("C. Min R:R >= 1.0 gate", dict(apply_costs=True, min_rr=1.0)),
        ("D. Min R:R >= 1.5 gate", dict(apply_costs=True, min_rr=1.5)),
        ("E. Min R:R >= 2.0 gate", dict(apply_costs=True, min_rr=2.0)),
        ("F. Min R:R >= 1.5 + zero fee", dict(apply_costs=False, min_rr=1.5)),
    ]

    header = (
        f"{'scenario':<32} {'return':>10} {'CAGR':>10} {'MDD':>9} {'sharpe':>8} "
        f"{'trades':>7} {'win%':>6} {'PF':>6} {'avgW%':>7} {'avgL%':>8} "
        f"{'R:R':>6} {'liq':>4} {'skip':>7}"
    )
    print(header)
    print("-" * len(header))
    rows = []
    curves = {}
    for name, kw in scenarios:
        res = simulate(
            feats, args.tp_tf, args.sl_tf, leverage=args.leverage, margin_frac=args.margin_frac,
            fund_arr=fund_arr, **kw,
        )
        m = compute_metrics(res["equity"], res, args.margin_frac * args.leverage)
        tr = res["trades"]
        rr = (tr["tp_dist_pct"].mean() / tr["sl_dist_pct"].mean()) if len(tr) else np.nan
        if name.startswith(("A.", "B.")):
            curves[name] = res["equity"]
        print(
            f"{name:<32} {m['total_return']*100:>9.2f}% {m['cagr']*100:>9.2f}% "
            f"{m['max_drawdown']*100:>8.2f}% {m['daily_sharpe']:>8.2f} {m['trades']:>7} "
            f"{m['win_rate']*100:>5.1f}% {m['profit_factor']:>6.3f} "
            f"{m['avg_win_pct_margin']*100:>6.2f}% {m['avg_loss_pct_margin']*100:>7.2f}% "
            f"{rr:>6.3f} {m['liquidations']:>4} {m['skipped_signals']:>7}"
        )
        rows.append({"scenario": name, **m, "realized_rr": rr})

    out_csv = os.path.join(OUT_DIR, "summary_data", "mtf_trend_20x_diagnosis.csv")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    print(f"\nSaved diagnosis -> {out_csv}")

    plot_diagnosis(curves, feats, args)


def plot_diagnosis(curves: dict, feats: pd.DataFrame, args):
    """Equity curves + the TP / SL / liquidation distance anatomy that breaks the design."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    close = feats["close"]
    daily_close = close.resample("1D").last().dropna()
    bh = daily_close / daily_close.iloc[0]
    ax1.plot(bh.index, bh.values, color="#888888", lw=1.4, label="SOL buy & hold (1x)")
    colors = {"A.": "#d62728", "B.": "#1f77b4"}
    for name, eq in curves.items():
        de = eq.resample("1D").last().dropna()
        de = de / eq.iloc[0]
        c = colors[name[:2]]
        tag = "as specified (20X, real fees)" if name.startswith("A.") else "zero fee / zero slippage"
        ax1.plot(de.index, de.values, color=c, lw=1.8, label=f"{name} {tag}")
    ax1.set_yscale("log")
    ax1.set_title(
        f"SOLUSDT  MTF resonance + {args.leverage:g}X  "
        f"(TP band = {args.tp_tf}, SL band = {args.sl_tf})"
    )
    ax1.set_ylabel("Equity (log scale, start = 1.0)")
    ax1.grid(alpha=0.3)
    ax1.legend(loc="lower left", fontsize=8)

    # Payoff anatomy: every evaluated entry's TP vs SL distance against the liquidation line
    tp_d = []
    sl_d = []
    liq_d = 1.0 / args.leverage - MMR
    long_sig = feats["long_signal"].values
    short_sig = feats["short_signal"].values
    tp_tag = args.tp_tf.replace("m", "M").replace("h", "H")
    sl_tag = args.sl_tf.replace("m", "M").replace("h", "H")
    tp_u, tp_l, tp_m = (feats[f"bb_{k}_{tp_tag}"].values for k in ("up", "lo", "mid"))
    sl_u, sl_l, sl_m = (feats[f"bb_{k}_{sl_tag}"].values for k in ("up", "lo", "mid"))
    cl = feats["close"].values
    for i in np.flatnonzero(long_sig | short_sig):
        if not np.isfinite(tp_u[i]) or not np.isfinite(sl_l[i]) or cl[i] <= 0:
            continue
        if long_sig[i]:
            tp_d.append((tp_u[i] - (tp_u[i] - tp_m[i]) * 0.15 - cl[i]) / cl[i])
            sl_d.append((cl[i] - (sl_l[i] + (sl_m[i] - sl_l[i]) * 0.15)) / cl[i])
        else:
            tp_d.append((cl[i] - (tp_l[i] + (tp_m[i] - tp_l[i]) * 0.15)) / cl[i])
            sl_d.append(((sl_u[i] - (sl_u[i] - sl_m[i]) * 0.15) - cl[i]) / cl[i])

    tp_d = np.array(tp_d) * 100
    sl_d = np.array(sl_d) * 100
    ax2.scatter(sl_d, tp_d, s=4, alpha=0.12, color="#1f77b4", label=f"evaluated signals (n={len(tp_d):,})")
    lim = max(np.nanpercentile(np.abs(tp_d), 99.5), np.nanpercentile(sl_d, 99.5), liq_d * 100 * 1.4)
    grid = np.linspace(0, lim, 50)
    ax2.plot(grid, grid, color="#2ca02c", lw=1.2, ls="--", label="R:R = 1:1 (break-even geometry)")
    ax2.axvline(liq_d * 100, color="#d62728", lw=1.6, ls=":", label=f"20X liquidation ({liq_d*100:.2f}% adverse)")
    ax2.axhline(0.0, color="#999999", lw=0.8)
    ax2.set_xlim(0, lim)
    ax2.set_ylim(min(-1.0, np.nanpercentile(tp_d, 0.5)), lim)
    ax2.set_xlabel("Stop-loss distance (% price move)")
    ax2.set_ylabel("Take-profit distance (% price move)")
    ax2.set_title("Why it fails: band TP is tiny, band SL is far outside the 20X liquidation line")
    ax2.grid(alpha=0.3)
    ax2.legend(loc="upper left", fontsize=8)

    fig.tight_layout()
    charts_dir = os.path.join(OUT_DIR, "charts")
    os.makedirs(charts_dir, exist_ok=True)
    out_png = os.path.join(
        charts_dir, f"mtf_trend_tp{args.tp_tf}_sl{args.sl_tf}_{args.leverage:g}x.png"
    )
    fig.savefig(out_png, dpi=130)
    plt.close(fig)
    print(f"Saved chart  -> {out_png}")


def run_leverage_scan(args):
    """
    Isolates the leverage decision on the current strategy geometry, under two sizing policies:
      A. fixed margin per trade  -> higher leverage means a bigger position
      B. fixed notional exposure -> higher leverage means less margin locked (closer liquidation)
    """
    bars, fund_map = load_data(args.start, args.end)
    fund_arr = funding_array(bars.index, fund_map)
    feats = build_feature_frame(bars, {"adx_threshold": args.adx_threshold}, args.signal_mode)

    kwargs = dict(
        entry_mode=args.entry_mode, entry_tf=args.entry_tf,
        pull_frac=args.pull_frac, arm_window=args.arm_window,
    )
    leverages = (1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 50.0)
    liq_dist = {lev: (1.0 / lev - MMR) * 100 for lev in leverages}

    header = (
        f"{'lev':>4} {'liq.line':>9} {'margin%':>8} {'notional':>9} | {'return':>10} {'CAGR':>9} "
        f"{'MDD':>9} {'sharpe':>7} {'trades':>7} {'win%':>6} {'PF':>6} {'liq':>4}"
    )
    print(f"Geometry: TP band={args.tp_tf} SL band={args.sl_tf} entry={args.entry_mode} "
          f"pull={args.pull_frac} | adx>={args.adx_threshold}\n")

    rows = []
    for policy, label in (
        ("fixed_margin", f"A. fixed margin {args.margin_frac*100:g}% of equity per trade"),
        ("fixed_notional", "B. fixed notional exposure 0.25x equity"),
    ):
        print(f"=== {label} ===")
        print(header)
        print("-" * len(header))
        for lev in leverages:
            mf = args.margin_frac if policy == "fixed_margin" else 0.25 / lev
            res = simulate(feats, args.tp_tf, args.sl_tf, leverage=lev, margin_frac=mf,
                           fund_arr=fund_arr, apply_costs=not args.no_costs, **kwargs)
            m = compute_metrics(res["equity"], res, mf * lev)
            print(
                f"{lev:>4g} {liq_dist[lev]:>8.2f}% {mf*100:>7.2f}% {mf*lev:>8.2f}x | "
                f"{m['total_return']*100:>9.2f}% {m['cagr']*100:>8.2f}% {m['max_drawdown']*100:>8.2f}% "
                f"{m['daily_sharpe']:>7.2f} {m['trades']:>7} {m['win_rate']*100:>5.1f}% "
                f"{m['profit_factor']:>6.3f} {m['liquidations']:>4}"
            )
            rows.append({"policy": policy, "leverage": lev, "margin_frac": mf, **m})
        print()

    out_csv = os.path.join(OUT_DIR, "summary_data", "mtf_trend_leverage_scan.csv")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    print(f"Saved leverage scan -> {out_csv}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2026-09-21")
    parser.add_argument("--signal-mode", default="unanimous")
    parser.add_argument("--band-tf", default=None,
                        help="shorthand: use the same Bollinger timeframe for both legs")
    parser.add_argument("--tp-tf", default=None, help="Bollinger timeframe anchoring the take-profit")
    parser.add_argument("--sl-tf", default=None, help="Bollinger timeframe anchoring the stop-loss")
    parser.add_argument("--adx-threshold", type=float, default=25.0)
    parser.add_argument("--leverage", type=float, default=10.0)
    parser.add_argument("--margin-frac", type=float, default=0.05)
    parser.add_argument("--entry-mode", default="pullback", choices=("immediate", "pullback"))
    parser.add_argument("--entry-tf", default=None, help="band timeframe governing the pullback trigger")
    parser.add_argument("--pull-frac", type=float, default=0.5,
                        help="0 = enter at the mid band, 1 = enter at the band edge")
    parser.add_argument("--arm-window", type=int, default=60,
                        help="how many 1m bars a confirmed resonance stays armed")
    parser.add_argument("--min-rr", type=float, default=0.0)
    parser.add_argument("--no-costs", action="store_true")
    parser.add_argument("--grid", action="store_true")
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--leverage-scan", action="store_true")
    args = parser.parse_args()

    if args.band_tf:
        args.tp_tf = args.tp_tf or args.band_tf
        args.sl_tf = args.sl_tf or args.band_tf
    args.tp_tf = args.tp_tf or "1h"
    args.sl_tf = args.sl_tf or "1m"
    args.entry_tf = args.entry_tf or args.tp_tf

    if args.grid:
        run_grid(args)
        return
    if args.diagnose:
        run_diagnose(args)
        return
    if args.leverage_scan:
        run_leverage_scan(args)
        return

    bars, fund_map = load_data(args.start, args.end)
    fund_arr = funding_array(bars.index, fund_map)
    print(f"Loaded {len(bars):,} 1m bars  {bars.index[0]} -> {bars.index[-1]}")

    m, res = run_one(
        bars, fund_map, fund_arr,
        {"adx_threshold": args.adx_threshold},
        args.signal_mode, args.tp_tf, args.sl_tf, args.margin_frac, args.leverage,
        min_rr=args.min_rr, apply_costs=not args.no_costs,
        entry_mode=args.entry_mode, entry_tf=args.entry_tf,
        pull_frac=args.pull_frac, arm_window=args.arm_window,
    )
    print(f"Long signals: {m['long_signals']:,} | Short signals: {m['short_signals']:,}")
    for k, v in m.items():
        print(f"  {k:>32}: {v}")

    tr = res["trades"]
    if len(tr):
        print("\nExit reason breakdown:")
        print(tr["reason"].value_counts().to_string())


if __name__ == "__main__":
    main()
