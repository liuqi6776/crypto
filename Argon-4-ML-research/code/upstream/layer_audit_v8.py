"""Label the actual base-account fills with same-pair closed-bar RSI layers."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
CASEBOOK = STUDY / "casebook.py"
TYPE_ORDER = ("regular_bearish", "regular_bullish", "hidden_bearish", "hidden_bullish")
TF_ORDER = ("1h", "15m", "5m")
TYPE_ZH = {
    "regular_bearish": "普通顶背离",
    "regular_bullish": "普通底背离",
    "hidden_bearish": "隐藏顶背离",
    "hidden_bullish": "隐藏底背离",
}


def strict_divergence(kind: str, p1: float, p2: float, d1: float, d2: float,
                      r1: float, r2: float) -> tuple[bool, bool, bool]:
    """Return strict price, DIF, and RSI pair checks for one divergence type."""
    rules = {
        "regular_bearish": (p2 > p1, d2 < d1, r2 < r1),
        "regular_bullish": (p2 < p1, d2 > d1, r2 > r1),
        "hidden_bearish": (p2 < p1, d2 > d1, r2 > r1),
        "hidden_bullish": (p2 > p1, d2 < d1, r2 < r1),
    }
    if kind not in rules:
        raise ValueError(f"unsupported signal type: {kind}")
    return tuple(bool(x) for x in rules[kind])


def classify(kind: str, price_ok: bool, dif_ok: bool, rsi_ok: bool) -> tuple[bool, bool, str, int]:
    if kind not in TYPE_ORDER:
        raise ValueError(kind)
    macd = bool(price_ok and dif_ok)
    resonance = bool(macd and rsi_ok)
    layer = (3 if resonance else 1) if kind.startswith("regular_") else (10 if resonance else 5)
    label = f"{kind}_MACD_plus_RSI_{layer}" if resonance else f"{kind}_MACD_only_{layer}"
    return macd, resonance, label, layer


def _rsi14():
    spec = importlib.util.spec_from_file_location("v8_casebook", CASEBOOK)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load frozen casebook RSI")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.rsi14


def _json(value):
    return json.loads(value) if isinstance(value, str) else value


def classify_primary_fills(trades: pd.DataFrame, bars_by_tf: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Classify rows from independent primary accounts; never changes PnL or replay."""
    rsi_by_tf: dict[str, np.ndarray] = {}
    close_by_tf: dict[str, pd.Series] = {}
    normalized_bars: dict[str, pd.DataFrame] = {}
    out = []
    for tf in TF_ORDER:
        bars = bars_by_tf[tf].reset_index(drop=True)
        if not bars.signal_index.astype(int).equals(pd.Series(np.arange(len(bars)), name="signal_index")):
            raise AssertionError(f"noncanonical signal index for {tf}")
        op = pd.to_datetime(bars.open_time_utc, utc=True)
        close_ts = pd.to_datetime(bars.close_time_utc, utc=True)
        if not close_ts.equals(op + pd.Timedelta(minutes={"1h": 60, "15m": 15, "5m": 5}[tf])):
            raise AssertionError(f"signal close time does not match completed {tf} bar")
        rsi = _rsi14()(bars.close.to_numpy(dtype=np.float64))
        if not np.isnan(rsi[:14]).all() or not np.isfinite(rsi[14:]).all():
            raise AssertionError(f"unexpected RSI warmup/nonfinite values for {tf}")
        rsi_by_tf[tf] = rsi
        close_by_tf[tf] = close_ts
        normalized_bars[tf] = bars

    for t in trades.to_dict("records"):
        tf = str(t["timeframe"])
        kind = str(t["signal_type"])
        if tf not in TF_ORDER or kind not in TYPE_ORDER:
            raise AssertionError("primary ledger contains an out-of-scope type/timeframe")
        fv = _json(t["filled_version"])
        p1 = _json(t["p1"])
        bars = normalized_bars[tf]
        p1i = int(p1["index"])
        p2i = int(t["candidate_extreme_index_signal_tf"])
        di = int(t["decision_index_signal_tf"])
        if (fv.get("case_id"), int(fv.get("version", -1))) != (t["case_id"], int(t["version"])):
            raise AssertionError("filled lifecycle identity mismatch")
        if int(fv.get("candidate_extreme_index_signal_tf", -1)) != p2i:
            raise AssertionError("candidate index differs from filled lifecycle")
        if not (0 <= p1i < p2i <= di < len(bars)):
            raise AssertionError("invalid P1/P2/decision order")
        pxcol = "high" if kind.endswith("bearish") else "low"
        p1px = float(p1["price"])
        p2px = float(bars.iloc[p2i][pxcol])
        if fv.get("candidate_price") is not None and not np.isclose(
                p2px, float(fv["candidate_price"]), rtol=0, atol=1e-8):
            raise AssertionError("filled candidate price differs from its signal bar")
        if not np.isclose(p1px, float(bars.iloc[p1i][pxcol]), rtol=0, atol=1e-8):
            raise AssertionError("P1 price mismatches its signal bar")
        if not np.isclose(p2px, float(bars.iloc[p2i][pxcol]), rtol=0, atol=1e-8):
            raise AssertionError("P2 price mismatches its filled candidate bar")
        decision = pd.Timestamp(t["decision_close_utc"])
        entry = pd.Timestamp(t["entry_time_assumed_utc"])
        if decision.tzinfo is None or entry.tzinfo is None:
            raise AssertionError("naive decision or entry timestamp")
        decision, entry = decision.tz_convert("UTC"), entry.tz_convert("UTC")
        if decision != close_by_tf[tf].iloc[di] or max(close_by_tf[tf].iloc[p1i], close_by_tf[tf].iloc[p2i]) > decision or decision > entry:
            raise AssertionError("RSI/decision is not available before actual entry")
        rsi = rsi_by_tf[tf]
        r1, r2 = float(rsi[p1i]), float(rsi[p2i])
        d1, d2 = float(bars.iloc[p1i].dif), float(bars.iloc[p2i].dif)
        price_ok, dif_ok, rsi_ok = strict_divergence(kind, p1px, p2px, d1, d2, r1, r2)
        macd, resonance, label, layer = classify(kind, price_ok, dif_ok, rsi_ok)
        if not macd:
            raise AssertionError("selected fill failed its strict same-pair base MACD rule")
        out.append({
            "timeframe": tf, "account_id": t["account_id"], "signal_type": kind,
            "case_id": t["case_id"], "version": int(t["version"]),
            "decision_close_utc": decision.isoformat(), "activation_open_5m_utc": t.get("activation_open_5m_utc"),
            "entry_time_assumed_utc": entry.isoformat(), "exit_time_assumed_utc": t.get("exit_time_assumed_utc"),
            "p1_index": p1i, "p1_open_utc": pd.Timestamp(bars.open_time_utc.iloc[p1i]).isoformat(),
            "p1_close_utc": close_by_tf[tf].iloc[p1i].isoformat(), "p1_price": p1px, "p1_dif": d1, "p1_rsi14": r1,
            "p2_index": p2i, "p2_open_utc": pd.Timestamp(bars.open_time_utc.iloc[p2i]).isoformat(),
            "p2_close_utc": close_by_tf[tf].iloc[p2i].isoformat(), "p2_price": p2px, "p2_dif": d2, "p2_rsi14": r2,
            "price_rule_pass": price_ok, "dif_rule_pass": dif_ok, "rsi_rule_pass": rsi_ok,
            "macd_divergence": macd, "rsi_macd_resonance": resonance, "layer_label_only": layer,
            "layer_category_label_only": label, "net_pnl_usdt_original": float(t["net_pnl_usdt"]),
            "quantity_btc": float(t["quantity_btc"]), "raw_reference_price_pnl_usdt": float(t["raw_reference_price_pnl_usdt"]),
            "total_fee_usdt": float(t["total_fee_usdt"]), "slippage_cost_diagnostic_embedded_usdt": float(t["slippage_cost_diagnostic_embedded_usdt"]),
            "funding_cash_usdt": float(t["funding_cash_usdt"]), "scenario_id": t["scenario_id"],
        })
    return pd.DataFrame(out)


def build_24_row_table(classified: pd.DataFrame, account_summaries: pd.DataFrame) -> pd.DataFrame:
    rows = []
    summary_by_account = account_summaries.set_index("account_id")
    for tf in TF_ORDER:
        for kind in TYPE_ORDER:
            account_id = f"{tf}_{kind}"
            if account_id not in summary_by_account.index:
                raise AssertionError(f"missing independent account summary: {account_id}")
            account_net = float(summary_by_account.loc[account_id, "net_trade_pnl_usdt"])
            for layer, with_rsi in ((1 if kind.startswith("regular_") else 5, False),
                                    (3 if kind.startswith("regular_") else 10, True)):
                group = classified.loc[classified.timeframe.eq(tf) & classified.signal_type.eq(kind)
                                       & classified.layer_label_only.eq(layer)]
                pnl = group.net_pnl_usdt_original.to_numpy(dtype=float)
                n = len(group)
                rows.append({"timeframe": tf, "signal_type": kind, "signal_type_zh": TYPE_ZH[kind],
                             "rsi_layer": "有RSI共振" if with_rsi else "无RSI共振", "layer_label_only": layer,
                             "trade_count": n, "win_count": int(np.count_nonzero(pnl > 0)),
                             "net_win_rate_pct": float(np.count_nonzero(pnl > 0) / n * 100) if n else None,
                             "original_position_net_pnl_attribution_usdt": float(pnl.sum()),
                             "independent_account_total_net_pnl_usdt": account_net,
                             "account_id": account_id})
    table = pd.DataFrame(rows)
    if len(table) != 24:
        raise AssertionError("expected exactly 24 rows")
    for (tf, kind), group in table.groupby(["timeframe", "signal_type"], sort=False):
        account_net = float(group.independent_account_total_net_pnl_usdt.iloc[0])
        if not np.isclose(group.original_position_net_pnl_attribution_usdt.sum(), account_net, atol=1e-7, rtol=0):
            raise AssertionError(f"layer attribution does not reconcile for {tf}/{kind}")
        if int(group.trade_count.sum()) != int(classified.timeframe.eq(tf).mul(classified.signal_type.eq(kind)).sum()):
            raise AssertionError("layer trade counts do not reconcile to actual fills")
    return table

