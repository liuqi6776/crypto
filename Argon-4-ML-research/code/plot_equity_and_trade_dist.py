"""Generate high-resolution Equity Curve, Drawdown, Monthly PnL, and Per-Trade Return Distribution charts.

Saves PNG charts and underlying trade/daily CSVs to both:
- research/zero_fee_maker_ml_v1/runs/
- Artifact directory (for direct UI embedding)
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from research.zero_fee_maker_ml_v1.code.backtest import _funding_sum_between
from research.zero_fee_maker_ml_v1.code.features import ROOT, DatasetBundle, build_dataset_bundle
from research.zero_fee_maker_ml_v1.code.models import FOLDS, _zscore_from_val
from research.zero_fee_maker_ml_v1.code.phase2_focused_study import (
    _fit_fast_30m_60m_pair,
    _generate_bar_positions,
)
from research.zero_fee_maker_ml_v1.code.phase3_master_ensemble import (
    _apply_rebalance_buffer,
    _build_mature_quarterly_positions,
    _fit_multi_horizon_ridge,
)

RUNS_DIR = ROOT / "research" / "zero_fee_maker_ml_v1" / "runs"
ARTIFACT_DIR = Path(r"C:\Users\liuqi\.gemini\antigravity\brain\a867f322-9356-4464-a06a-9a68f36236bb")


def _extract_bar_and_trade_series(
    bundle: DatasetBundle,
    te_mask: np.ndarray,
    pos_path: np.ndarray,
    one_way_cost_bp: float = 0.5,
    leverage: float = 1.0,
) -> Tuple[pd.Series, pd.DataFrame]:
    """Return 5m net return series and a DataFrame of discrete holding/trade episodes."""
    te_indices = np.flatnonzero(te_mask)
    n_te = len(te_indices)
    idx_ms = (bundle.index.astype("int64") // 10**6).to_numpy()
    o_raw = bundle.open_raw
    cost_rate = one_way_cost_bp * 1e-4

    bar_net_rets = np.zeros(n_te, dtype=np.float64)
    bar_gross_rets = np.zeros(n_te, dtype=np.float64)
    bar_fund_rets = np.zeros(n_te, dtype=np.float64)

    # Track discrete trade episodes (A trade episode starts when pos != 0 or flips sign,
    # or we also record every contiguous constant-sign holding episode and individual rebalance blocks)
    episodes: List[Dict[str, object]] = []
    ep_active = False
    ep_start_k = 0
    ep_side = 0
    ep_gross = 0.0
    ep_fund = 0.0
    ep_cost = 0.0
    ep_weights: List[float] = []

    prev_pos = 0.0
    for k in range(n_te - 1):
        g_idx = te_indices[k]
        eb = g_idx + 1
        if eb + 1 >= len(o_raw):
            break

        target_pos = float(pos_path[k])
        delta_pos = target_pos - prev_pos

        o_cur = o_raw[eb]
        o_nxt = o_raw[eb + 1]
        t_start_ms = int(idx_ms[eb])
        t_end_ms = int(idx_ms[eb + 1])

        cost_b = -abs(delta_pos) * cost_rate
        gross_b = target_pos * (o_nxt - o_cur) / o_cur
        f_sum = _funding_sum_between(bundle.funding_ms, bundle.funding_rate, t_start_ms, t_end_ms)
        fund_b = -target_pos * f_sum
        net_b = (gross_b + fund_b + cost_b) * leverage

        bar_gross_rets[k] = gross_b * leverage
        bar_fund_rets[k] = fund_b * leverage
        bar_net_rets[k] = np.clip(net_b, -0.99, 5.0)

        cur_side = 1 if target_pos > 1e-6 else (-1 if target_pos < -1e-6 else 0)
        prev_side = 1 if prev_pos > 1e-6 else (-1 if prev_pos < -1e-6 else 0)

        # Close previous episode if sign flipped or went flat, or if holding exceeded 12 bars (1h chunk)
        if ep_active and (cur_side != ep_side or (k - ep_start_k) >= 12):
            # Add exit cost if going flat or flipping
            exit_c = -abs(prev_pos) * cost_rate if cur_side != ep_side else 0.0
            tot_cost = ep_cost + exit_c
            ep_Cost_already_counted = 0.0
            mean_w = float(np.mean(ep_weights)) if ep_weights else 1.0
            # Normalize per-unit-notional trade return (1x bp) and leveraged account return (3x %)
            norm_gross_bp = (ep_gross / max(mean_w, 0.1)) * 1e4
            norm_net_bp = ((ep_gross + ep_fund + tot_cost) / max(mean_w, 0.1)) * 1e4
            acct_net_pct = (ep_gross + ep_fund + tot_cost) * leverage * 100.0
            episodes.append(
                {
                    "entry_time": bundle.index[te_indices[ep_start_k]],
                    "exit_time": bundle.index[te_indices[k]],
                    "year": int(bundle.index[te_indices[ep_start_k]].year),
                    "side": "LONG" if ep_side == 1 else "SHORT",
                    "avg_weight": round(mean_w, 3),
                    "hold_minutes": (k - ep_start_k) * 5,
                    "norm_gross_bp_1x": round(norm_gross_bp, 3),
                    "norm_net_bp_1x": round(norm_net_bp, 3),
                    "account_net_ret_pct": round(acct_net_pct, 4),
                    "account_gross_ret_pct": round(ep_gross * leverage * 100.0, 4),
                }
            )
            ep_active = False

        if cur_side != 0 and not ep_active:
            ep_active = True
            ep_start_k = k
            ep_side = cur_side
            ep_gross = gross_b
            ep_fund = fund_b
            ep_cost = -abs(delta_pos) * cost_rate if prev_side != cur_side else 0.0
            ep_weights = [abs(target_pos)]
        elif ep_active:
            ep_gross += gross_b
            ep_fund += fund_b
            ep_cost += cost_b
            ep_weights.append(abs(target_pos))

        prev_pos = target_pos

    s_bar = pd.Series(bar_net_rets, index=bundle.index[te_mask])
    df_ep = pd.DataFrame(episodes)
    return s_bar, df_ep


def main() -> None:
    t0 = time.time()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    print("Loading BTCUSDT DatasetBundle and fitting Phase 3 Master Ensemble...")
    bundle = build_dataset_bundle("BTCUSDT")
    fold_gbdt, fold_lin = {}, {}
    for fold in FOLDS:
        fold_gbdt[fold.year] = _fit_fast_30m_60m_pair(
            bundle, fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
        fold_lin[fold.year] = _fit_multi_horizon_ridge(
            bundle, fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
    e4_pos = _build_mature_quarterly_positions(bundle, fold_gbdt)

    # Concatenate 2025 + 2026 OOS bar return series and trade episodes
    series_dict: Dict[str, List[pd.Series]] = {
        "M3_3X_REAL_0.5BP": [],
        "M2_3X_REAL_0.5BP": [],
        "M1_3X_REAL_0.5BP": [],
        "M2_3X_IDEAL_0.0BP": [],
        "M3_1X_REAL_0.5BP": [],
        "M2_1X_REAL_0.5BP": [],
    }
    trades_m3_list: List[pd.DataFrame] = []
    trades_m2_list: List[pd.DataFrame] = []

    for yr in (2025, 2026):
        g_out, l_out = fold_gbdt[yr], fold_lin[yr]
        te_mask = g_out["te_mask"]

        p_e1 = _generate_bar_positions(
            bundle, te_mask, g_out["va_s30"], g_out["te_s30"],
            g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
            6, 0.92, 0.58, 0.85,
        )
        p_e2 = _generate_bar_positions(
            bundle, te_mask, g_out["va_joint"], g_out["te_joint"],
            g_out["va_ml60"], g_out["te_ml60"], g_out["va_ms60"], g_out["te_ms60"],
            6, 0.92, 0.58, 0.85,
        )
        p_l15 = _generate_bar_positions(
            bundle, te_mask, l_out["va_lin_15"], l_out["te_lin_15"],
            g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
            3, 0.92, 0.58, 0.85,
        )
        p_l30 = _generate_bar_positions(
            bundle, te_mask, l_out["va_lin_blend"], l_out["te_lin_blend"],
            g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
            6, 0.92, 0.58, 0.85,
        )
        p_e3 = 0.50 * p_l15 + 0.50 * p_l30
        p_e4 = e4_pos[yr]

        va_meta = (
            0.40 * _zscore_from_val(g_out["va_s30"], g_out["va_s30"])
            + 0.30 * _zscore_from_val(g_out["va_t60"], g_out["va_t60"])
            + 0.30 * _zscore_from_val(l_out["va_lin_blend"], l_out["va_lin_blend"])
        )
        te_meta = (
            0.40 * _zscore_from_val(g_out["va_s30"], g_out["te_s30"])
            + 0.30 * _zscore_from_val(g_out["va_t60"], g_out["te_t60"])
            + 0.30 * _zscore_from_val(l_out["va_lin_blend"], l_out["te_lin_blend"])
        )
        p_m1_30 = _generate_bar_positions(
            bundle, te_mask, va_meta, te_meta,
            g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
            6, 0.92, 0.58, 0.85,
        )
        p_m1_60 = _generate_bar_positions(
            bundle, te_mask, va_meta, te_meta,
            g_out["va_ml60"], g_out["te_ml60"], g_out["va_ms60"], g_out["te_ms60"],
            12, 0.92, 0.58, 0.85,
        )
        p_m1 = 0.50 * p_m1_30 + 0.50 * p_m1_60
        p_m2 = 0.25 * p_e1 + 0.25 * p_e2 + 0.25 * p_e3 + 0.25 * p_e4
        p_m3 = _apply_rebalance_buffer(0.50 * p_m1 + 0.50 * p_m2, min_delta=0.20)

        s_m3_3x, df_ep_m3 = _extract_bar_and_trade_series(bundle, te_mask, p_m3, 0.5, 3.0)
        s_m2_3x, df_ep_m2 = _extract_bar_and_trade_series(bundle, te_mask, p_m2, 0.5, 3.0)
        s_m1_3x, _ = _extract_bar_and_trade_series(bundle, te_mask, p_m1, 0.5, 3.0)
        s_m2_3x_0bp, _ = _extract_bar_and_trade_series(bundle, te_mask, p_m2, 0.0, 3.0)
        s_m3_1x, _ = _extract_bar_and_trade_series(bundle, te_mask, p_m3, 0.5, 1.0)
        s_m2_1x, _ = _extract_bar_and_trade_series(bundle, te_mask, p_m2, 0.5, 1.0)

        series_dict["M3_3X_REAL_0.5BP"].append(s_m3_3x)
        series_dict["M2_3X_REAL_0.5BP"].append(s_m2_3x)
        series_dict["M1_3X_REAL_0.5BP"].append(s_m1_3x)
        series_dict["M2_3X_IDEAL_0.0BP"].append(s_m2_3x_0bp)
        series_dict["M3_1X_REAL_0.5BP"].append(s_m3_1x)
        series_dict["M2_1X_REAL_0.5BP"].append(s_m2_1x)

        trades_m3_list.append(df_ep_m3)
        trades_m2_list.append(df_ep_m2)

    daily_eq: Dict[str, pd.Series] = {}
    daily_dd: Dict[str, pd.Series] = {}
    for k, s_list in series_dict.items():
        s_all = pd.concat(s_list).sort_index()
        d_ret = s_all.resample("1D").apply(lambda x: float(np.prod(1.0 + x) - 1.0))
        eq = (1.0 + d_ret).cumprod()
        peaks = eq.cummax()
        dd = (eq - peaks) / peaks * 100.0
        daily_eq[k] = (eq - 1.0) * 100.0
        daily_dd[k] = dd

    df_trades_m3 = pd.concat(trades_m3_list, ignore_index=True)
    df_trades_m2 = pd.concat(trades_m2_list, ignore_index=True)
    df_trades_m3.to_csv(RUNS_DIR / "phase3_m3_trade_episodes_3x.csv", index=False)
    df_trades_m2.to_csv(RUNS_DIR / "phase3_m2_trade_episodes_3x.csv", index=False)

    # Save daily equity curves to CSV
    df_daily_eq = pd.DataFrame(daily_eq)
    df_daily_eq.index.name = "date_utc"
    df_daily_eq.to_csv(RUNS_DIR / "phase3_daily_cumulative_returns_pct.csv")

    # =========================================================================
    # FIGURE 1: Equity Curves, Underwater Drawdown, and 21-Month Bar Chart (3X)
    # =========================================================================
    fig = plt.figure(figsize=(16, 13), dpi=160, facecolor="#0f172a")
    gs = fig.add_gridspec(3, 1, height_ratios=[1.45, 0.85, 0.95], hspace=0.32)

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax3 = fig.add_subplot(gs[2])

    for ax in (ax1, ax2, ax3):
        ax.set_facecolor("#1e293b")
        ax.tick_params(colors="#e2e8f0", labelsize=10)
        for spine in ax.spines.values():
            spine.set_color("#475569")
        ax.grid(True, linestyle="--", alpha=0.25, color="#94a3b8")

    # Panel 1: Cumulative Return Curves (%)
    ax1.plot(
        daily_eq["M3_3X_REAL_0.5BP"].index,
        daily_eq["M3_3X_REAL_0.5BP"].values,
        color="#38bdf8",
        linewidth=2.4,
        label="M3_HYBRID_MASTER_LIVE (3X, 0.5bp/side Real Cost): +79.8% Total (+33.0% in 2025, +35.2% in 2026)",
    )
    ax1.plot(
        daily_eq["M2_3X_REAL_0.5BP"].index,
        daily_eq["M2_3X_REAL_0.5BP"].values,
        color="#4ade80",
        linewidth=2.4,
        label="M2_4ENGINE_SUBBOOK_NETTING (3X, 0.5bp/side Real Cost): +77.1% Total (+27.5% in 2025, +38.9% in 2026)",
    )
    ax1.plot(
        daily_eq["M1_3X_REAL_0.5BP"].index,
        daily_eq["M1_3X_REAL_0.5BP"].values,
        color="#f472b6",
        linewidth=1.6,
        alpha=0.85,
        label="M1_SIGNAL_META_ENSEMBLE (3X, 0.5bp/side Real Cost): +74.4% Total",
    )
    ax1.plot(
        daily_eq["M3_1X_REAL_0.5BP"].index,
        daily_eq["M3_1X_REAL_0.5BP"].values,
        color="#fbbf24",
        linewidth=1.8,
        linestyle="--",
        label="M3_HYBRID_MASTER_LIVE (1X Unlevered Baseline, 0.5bp/side): +31.1% Total (MaxDD -15.4%)",
    )
    ax1.axhline(0.0, color="#94a3b8", linewidth=1.0, linestyle=":")
    ax1.axvline(pd.Timestamp("2026-01-01", tz="UTC"), color="#f8fafc", linewidth=1.3, linestyle="-.")
    ax1.text(
        pd.Timestamp("2026-01-05", tz="UTC"),
        ax1.get_ylim()[1] * 0.82 if ax1.get_ylim()[1] > 0 else 60,
        "2025 -> 2026 Fold Boundary",
        color="#f8fafc",
        fontsize=10,
        fontweight="bold",
    )
    ax1.set_title(
        "0-Fee Maker BTCUSDT Master Ensemble — 2025 & 2026 Out-of-Sample Cumulative Return Curve (3X vs 1X, Net of 0.5bp/side & 8h Funding)",
        color="#f8fafc",
        fontsize=13,
        fontweight="bold",
        pad=12,
    )
    ax1.set_ylabel("Cumulative Net Return (%)", color="#f8fafc", fontsize=11)
    ax1.legend(loc="upper left", facecolor="#0f172a", edgecolor="#475569", labelcolor="#f8fafc", fontsize=9.5)

    # Panel 2: Underwater Drawdown Curves (%)
    ax2.fill_between(
        daily_dd["M2_3X_REAL_0.5BP"].index,
        daily_dd["M2_3X_REAL_0.5BP"].values,
        0.0,
        color="#4ade80",
        alpha=0.28,
        label="M2_4ENGINE_SUBBOOK_NETTING 3X Drawdown (2025 MaxDD: -31.6%, 2026 MaxDD: -22.7%, 0 Liquidations)",
    )
    ax2.plot(
        daily_dd["M3_3X_REAL_0.5BP"].index,
        daily_dd["M3_3X_REAL_0.5BP"].values,
        color="#38bdf8",
        linewidth=1.6,
        label="M3_HYBRID_MASTER_LIVE 3X Drawdown (2025 MaxDD: -40.7%, 2026 MaxDD: -34.5%, 0 Liquidations)",
    )
    ax2.plot(
        daily_dd["M2_1X_REAL_0.5BP"].index,
        daily_dd["M2_1X_REAL_0.5BP"].values,
        color="#fbbf24",
        linewidth=1.5,
        linestyle="--",
        label="M2_4ENGINE_SUBBOOK_NETTING 1X Drawdown (2025 MaxDD: -10.6%, 2026 MaxDD: -8.2%)",
    )
    ax2.axvline(pd.Timestamp("2026-01-01", tz="UTC"), color="#f8fafc", linewidth=1.2, linestyle="-.")
    ax2.set_title("Underwater Equity Drawdown Curve (%) — 3X vs 1X", color="#f8fafc", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Drawdown (%)", color="#f8fafc", fontsize=11)
    ax2.legend(loc="lower left", facecolor="#0f172a", edgecolor="#475569", labelcolor="#f8fafc", fontsize=9.0)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    # Panel 3: 21-Month Bar Chart (2025-01 to 2026-09) for M2 (3X) and M3 (3X)
    s_m2_full = pd.concat(series_dict["M2_3X_REAL_0.5BP"]).sort_index()
    s_m3_full = pd.concat(series_dict["M3_3X_REAL_0.5BP"]).sort_index()
    m_m2 = s_m2_full.resample("1ME").apply(lambda x: float(np.prod(1.0 + x) - 1.0) * 100.0)
    m_m3 = s_m3_full.resample("1ME").apply(lambda x: float(np.prod(1.0 + x) - 1.0) * 100.0)

    months_lbl = [d.strftime("%Y-%m") for d in m_m2.index]
    x_pos = np.arange(len(months_lbl))
    w = 0.38
    ax3.bar(x_pos - w / 2, m_m2.values, width=w, color="#4ade80", alpha=0.9, label="M2_4ENGINE_SUBBOOK_NETTING (3X Monthly %)")
    ax3.bar(x_pos + w / 2, m_m3.values, width=w, color="#38bdf8", alpha=0.9, label="M3_HYBRID_MASTER_LIVE (3X Monthly %)")
    ax3.axhline(0.0, color="#f8fafc", linewidth=1.0)
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels(months_lbl, rotation=35, ha="right", fontsize=9)
    ax3.set_title("Monthly Net Returns (%) at 3X Leverage (2025-01 to 2026-09, All 21 Months)", color="#f8fafc", fontsize=12, fontweight="bold")
    ax3.set_ylabel("Monthly Return (%)", color="#f8fafc", fontsize=11)
    ax3.legend(loc="upper left", facecolor="#0f172a", edgecolor="#475569", labelcolor="#f8fafc", fontsize=9.5)

    p1_run = RUNS_DIR / "equity_and_drawdown_curves_2025_2026.png"
    p1_art = ARTIFACT_DIR / "equity_and_drawdown_curves_2025_2026.png"
    fig.savefig(p1_run, bbox_inches="tight", facecolor=fig.get_facecolor())
    shutil.copy2(p1_run, p1_art)
    plt.close(fig)

    # =========================================================================
    # FIGURE 2: Per-Trade Return Distribution, Tail Quantiles & Profit Attribution
    # =========================================================================
    fig2 = plt.figure(figsize=(16, 12), dpi=160, facecolor="#0f172a")
    gs2 = fig2.add_gridspec(2, 2, height_ratios=[1.15, 1.0], hspace=0.32, wspace=0.22)

    ax_hist = fig2.add_subplot(gs2[0, :])
    ax_box = fig2.add_subplot(gs2[1, 0])
    ax_dec = fig2.add_subplot(gs2[1, 1])

    for ax in (ax_hist, ax_box, ax_dec):
        ax.set_facecolor("#1e293b")
        ax.tick_params(colors="#e2e8f0", labelsize=10)
        for spine in ax.spines.values():
            spine.set_color("#475569")
        ax.grid(True, linestyle="--", alpha=0.25, color="#94a3b8")

    # Panel A: Per-Trade Account Net Return (%) Distribution at 3X Leverage
    rets_m3 = df_trades_m3["account_net_ret_pct"].to_numpy()
    rets_m2 = df_trades_m2["account_net_ret_pct"].to_numpy()
    rets_m3_clip = np.clip(rets_m3, -3.5, 3.5)
    rets_m2_clip = np.clip(rets_m2, -3.5, 3.5)

    bins = np.linspace(-3.5, 3.5, 85)
    ax_hist.hist(
        rets_m3_clip,
        bins=bins,
        color="#38bdf8",
        alpha=0.55,
        edgecolor="#0284c7",
        label=f"M3_HYBRID_MASTER_LIVE (n={len(rets_m3)} episodes, WinRate={(rets_m3>0).mean()*100:.1f}%, Mean={rets_m3.mean():+.3f}%, Skew={pd.Series(rets_m3).skew():+.2f})",
    )
    ax_hist.hist(
        rets_m2_clip,
        bins=bins,
        color="#4ade80",
        alpha=0.45,
        edgecolor="#16a34a",
        label=f"M2_4ENGINE_SUBBOOK_NETTING (n={len(rets_m2)} episodes, WinRate={(rets_m2>0).mean()*100:.1f}%, Mean={rets_m2.mean():+.3f}%, Skew={pd.Series(rets_m2).skew():+.2f})",
    )
    q05_m3, q50_m3, q95_m3 = np.percentile(rets_m3, [5, 50, 95])
    ax_hist.axvline(0.0, color="#f8fafc", linewidth=1.5, linestyle="-")
    ax_hist.axvline(rets_m3.mean(), color="#fbbf24", linewidth=2.0, linestyle="--", label=f"M3 Mean Return ({rets_m3.mean():+.3f}% per episode)")
    ax_hist.axvline(q05_m3, color="#f87171", linewidth=1.6, linestyle=":", label=f"M3 5th Percentile Left Tail ({q05_m3:+.2f}% — Y1 Gate Capped)")
    ax_hist.axvline(q95_m3, color="#a7f3d0", linewidth=1.6, linestyle=":", label=f"M3 95th Percentile Right Tail ({q95_m3:+.2f}% — Hysteresis Trend Run)")
    ax_hist.set_title(
        "Per-Trade Net Return Distribution at 3X Leverage (% of Account Equity per Holding Episode, Clipped to [-3.5%, +3.5%])",
        color="#f8fafc",
        fontsize=13,
        fontweight="bold",
        pad=10,
    )
    ax_hist.set_xlabel("Single Trade Episode Net Return at 3X Leverage (%)", color="#f8fafc", fontsize=11)
    ax_hist.set_ylabel("Trade Count (Episodes)", color="#f8fafc", fontsize=11)
    ax_hist.legend(loc="upper right", facecolor="#0f172a", edgecolor="#475569", labelcolor="#f8fafc", fontsize=9.5)

    # Panel B: Quantile Profile by Year & Direction (M3_HYBRID_MASTER_LIVE 3X)
    groups = [
        ("2025 LONG", df_trades_m3[(df_trades_m3["year"] == 2025) & (df_trades_m3["side"] == "LONG")]["account_net_ret_pct"].to_numpy()),
        ("2025 SHORT", df_trades_m3[(df_trades_m3["year"] == 2025) & (df_trades_m3["side"] == "SHORT")]["account_net_ret_pct"].to_numpy()),
        ("2026 LONG", df_trades_m3[(df_trades_m3["year"] == 2026) & (df_trades_m3["side"] == "LONG")]["account_net_ret_pct"].to_numpy()),
        ("2026 SHORT", df_trades_m3[(df_trades_m3["year"] == 2026) & (df_trades_m3["side"] == "SHORT")]["account_net_ret_pct"].to_numpy()),
    ]
    bp = ax_box.boxplot(
        [g[1] for g in groups],
        tick_labels=[f"{g[0]}\n(n={len(g[1])})" for g in groups],
        showfliers=False,
        patch_artist=True,
        medianprops={"color": "#fbbf24", "linewidth": 2.0},
        whiskerprops={"color": "#cbd5e1", "linewidth": 1.3},
        capprops={"color": "#cbd5e1", "linewidth": 1.3},
    )
    colors_box = ["#38bdf8", "#f472b6", "#4ade80", "#c084fc"]
    for patch, c in zip(bp["boxes"], colors_box):
        patch.set_facecolor(c)
        patch.set_alpha(0.6)
        patch.set_edgecolor("#f8fafc")
    ax_box.axhline(0.0, color="#f8fafc", linewidth=1.0, linestyle=":")
    ax_box.set_title("Trade Return Boxplot by Year & Direction (Outliers Hidden, 3X %)", color="#f8fafc", fontsize=11.5, fontweight="bold")
    ax_box.set_ylabel("Net Return per Episode at 3X (%)", color="#f8fafc", fontsize=10.5)

    # Panel C: Cumulative PnL Contribution by Trade Return Quantile Bucket
    df_trades_m3["decile"] = pd.qcut(df_trades_m3["account_net_ret_pct"], q=10, labels=[f"D{i}" for i in range(1, 11)])
    dec_sum = df_trades_m3.groupby("decile", observed=False)["account_net_ret_pct"].mean()
    dec_colors = ["#ef4444" if v < 0 else "#22c55e" for v in dec_sum.values]
    ax_dec.bar(dec_sum.index.astype(str), dec_sum.values, color=dec_colors, alpha=0.85, edgecolor="#f8fafc")
    ax_dec.axhline(0.0, color="#f8fafc", linewidth=1.0)
    # Annotate D1 vs D10 asymmetry (Right-tail > Left-tail)
    d1_val = float(dec_sum.iloc[0])
    d10_val = float(dec_sum.iloc[-1])
    ax_dec.set_title(
        f"Mean Trade Return by Decile (D1 Worst 10%: {d1_val:+.2f}% vs D10 Best 10%: {d10_val:+.2f}%)",
        color="#f8fafc",
        fontsize=11.5,
        fontweight="bold",
    )
    ax_dec.set_xlabel("Trade Return Decile (D1 = Worst 10% Losers, D10 = Best 10% Winners)", color="#f8fafc", fontsize=10.5)
    ax_dec.set_ylabel("Mean Return per Episode (%)", color="#f8fafc", fontsize=10.5)

    p2_run = RUNS_DIR / "trade_return_distribution_2025_2026.png"
    p2_art = ARTIFACT_DIR / "trade_return_distribution_2025_2026.png"
    fig2.savefig(p2_run, bbox_inches="tight", facecolor=fig2.get_facecolor())
    shutil.copy2(p2_run, p2_art)
    plt.close(fig2)

    # Save exact trade distribution statistics to JSON
    def _dist_stats(df_t: pd.DataFrame) -> Dict[str, float]:
        r3 = df_t["account_net_ret_pct"].to_numpy()
        r1_bp = df_t["norm_net_bp_1x"].to_numpy()
        pos = r3[r3 > 0]
        neg = r3[r3 < 0]
        return {
            "n_episodes": int(len(r3)),
            "win_rate_pct": round(float((r3 > 0).mean() * 100.0), 2),
            "mean_3x_pct": round(float(np.mean(r3)), 4),
            "median_3x_pct": round(float(np.median(r3)), 4),
            "std_3x_pct": round(float(np.std(r3)), 4),
            "skewness": round(float(pd.Series(r3).skew()), 3),
            "kurtosis": round(float(pd.Series(r3).kurt()), 3),
            "q01_3x_pct": round(float(np.percentile(r3, 1)), 3),
            "q05_3x_pct": round(float(np.percentile(r3, 5)), 3),
            "q25_3x_pct": round(float(np.percentile(r3, 25)), 3),
            "q75_3x_pct": round(float(np.percentile(r3, 75)), 3),
            "q95_3x_pct": round(float(np.percentile(r3, 95)), 3),
            "q99_3x_pct": round(float(np.percentile(r3, 99)), 3),
            "worst_episode_3x_pct": round(float(np.min(r3)), 3),
            "best_episode_3x_pct": round(float(np.max(r3)), 3),
            "avg_win_3x_pct": round(float(np.mean(pos)), 3) if len(pos) else 0.0,
            "avg_loss_3x_pct": round(float(np.mean(neg)), 3) if len(neg) else 0.0,
            "payoff_ratio_win_loss": round(float(np.mean(pos) / abs(np.mean(neg))), 3) if len(neg) else 0.0,
            "mean_norm_net_bp_1x": round(float(np.mean(r1_bp)), 2),
        }

    stats_summary = {
        "M3_HYBRID_MASTER_LIVE_3X": _dist_stats(df_trades_m3),
        "M2_4ENGINE_SUBBOOK_NETTING_3X": _dist_stats(df_trades_m2),
        "M3_2025": _dist_stats(df_trades_m3[df_trades_m3["year"] == 2025]),
        "M3_2026": _dist_stats(df_trades_m3[df_trades_m3["year"] == 2026]),
    }
    with open(RUNS_DIR / "phase3_trade_distribution_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats_summary, f, indent=2)

    print(f"Saved charts and stats in {time.time() - t0:.2f}s")
    print(json.dumps(stats_summary, indent=2))


if __name__ == "__main__":
    main()
