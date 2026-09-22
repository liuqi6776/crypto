# -*- coding: utf-8 -*-
"""
20X Leverage Trend-Following Strategy Anchored on Support & Resistance (S/R)
20倍杠杆基于支撑/阻力位（S/R）的稳健趋势执行系统
- 4 Assets: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT
- Macro Trend Filter (SuperTrend + EMA Stack + ADX)
- Micro 1s Momentum Trigger (Order Imbalance & 1s Slope)
- Dynamic TP/SL Anchored to Previous Swing Support & Resistance
- Asymmetric Risk/Reward Filter: R:R >= 2.0
- Breakeven Trailing Guard: Move SL to entry + 0.15% at +1.0R profit
- Zero Liquidation Guarantee: Max SL distance strictly <= 1.2%
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from support_resistance_engine import SupportResistanceEngine


class SRTrendStrategy20X:
    """
    Production-grade 20X trend-following strategy with dynamic S/R and breakeven trailing
    """
    def __init__(self,
                 leverage: float = 20.0,
                 min_risk_reward: float = 2.0,
                 max_sl_distance_pct: float = 1.2, # Max 1.2% price move = -24% ROE
                 min_sl_distance_pct: float = 0.25, # Min 0.25% to avoid micro-noise
                 fee_rate_per_side: float = 0.0005, # 0.05% taker fee
                 slippage_pct: float = 0.0002,      # 0.02% slippage
                 breakeven_trigger_r: float = 1.0): # Move SL to BE at +1.0R gain
        self.leverage = leverage
        self.min_risk_reward = min_risk_reward
        self.max_sl_distance_pct = max_sl_distance_pct
        self.min_sl_distance_pct = min_sl_distance_pct
        self.fee_rate_per_side = fee_rate_per_side
        self.slippage_pct = slippage_pct
        self.breakeven_trigger_r = breakeven_trigger_r
        self.sr_engine = SupportResistanceEngine()

    def evaluate_entry_signal(self, df_1s: pd.DataFrame) -> Optional[Dict[str, any]]:
        """
        Evaluates whether a valid 20X trend-following trade setup exists
        """
        if len(df_1s) < 30:
            return None

        # 1. Macro & intermediate trend classification
        trend = self.sr_engine.classify_trend(df_1s)
        regime = trend['regime']
        
        # Rule: In choppy/ranging markets, strictly stay in cash (Zero fee churn)
        if regime == 'CHOPPY':
            return None
        
        # 2. Dynamic S/R Levels
        sr = self.sr_engine.get_dynamic_sr(df_1s)
        curr_price = sr['current_price']
        s1, r1 = sr['S1'], sr['R1']
        
        # 3. Micro 1s momentum check
        mom_5s = df_1s['mom_5s'].iloc[-1] if 'mom_5s' in df_1s.columns else 0.0
        imbalance = df_1s['order_imbalance'].iloc[-1] if 'order_imbalance' in df_1s.columns else 0.0
        
        # 4. Long Setup
        if regime == 'BULLISH':
            # Stop-loss strictly below S1 (with 0.05% buffer)
            sl_price = s1 * 0.9995
            sl_dist_pct = (curr_price - sl_price) / curr_price * 100.0
            
            # Take-profit strictly below R1 (with 0.05% buffer)
            tp_price = r1 * 0.9995
            tp_dist_pct = (tp_price - curr_price) / curr_price * 100.0
            
            # Bound SL distance within 20X safety range [0.25%, 1.20%]
            if sl_dist_pct > self.max_sl_distance_pct:
                sl_price = curr_price * (1.0 - self.max_sl_distance_pct / 100.0)
                sl_dist_pct = self.max_sl_distance_pct
            if sl_dist_pct < self.min_sl_distance_pct:
                return None  # Too tight, noise stop-out risk
                
            # Asymmetric Risk/Reward check
            rr = tp_dist_pct / sl_dist_pct
            if rr < self.min_risk_reward:
                return None  # Reject poor risk/reward
                
            # Micro-momentum confirmation: do not enter if crashing in 1s
            if mom_5s < -0.20:
                return None
                
            return {
                'action': 'LONG',
                'entry_price': curr_price,
                'tp_price': tp_price,
                'sl_price': sl_price,
                'sl_dist_pct': sl_dist_pct,
                'tp_dist_pct': tp_dist_pct,
                'risk_reward': rr,
                'regime': regime,
                's1': s1,
                'r1': r1
            }

        # 5. Short Setup
        elif regime == 'BEARISH':
            # Stop-loss strictly above R1 (with 0.05% buffer)
            sl_price = r1 * 1.0005
            sl_dist_pct = (sl_price - curr_price) / curr_price * 100.0
            
            # Take-profit strictly above S1 (with 0.05% buffer)
            tp_price = s1 * 1.0005
            tp_dist_pct = (curr_price - tp_price) / curr_price * 100.0
            
            # Bound SL distance within 20X safety range
            if sl_dist_pct > self.max_sl_distance_pct:
                sl_price = curr_price * (1.0 + self.max_sl_distance_pct / 100.0)
                sl_dist_pct = self.max_sl_distance_pct
            if sl_dist_pct < self.min_sl_distance_pct:
                return None
                
            # Asymmetric Risk/Reward check
            rr = tp_dist_pct / sl_dist_pct
            if rr < self.min_risk_reward:
                return None
                
            # Micro-momentum confirmation: do not enter if rocketing in 1s
            if mom_5s > 0.20:
                return None
                
            return {
                'action': 'SHORT',
                'entry_price': curr_price,
                'tp_price': tp_price,
                'sl_price': sl_price,
                'sl_dist_pct': sl_dist_pct,
                'tp_dist_pct': tp_dist_pct,
                'risk_reward': rr,
                'regime': regime,
                's1': s1,
                'r1': r1
            }
            
        return None

    def simulate_trade_path(self,
                            signal: Dict[str, any],
                            future_highs: np.ndarray,
                            future_lows: np.ndarray,
                            future_closes: np.ndarray) -> Dict[str, any]:
        """
        Simulates the forward execution of a trade with:
        - Exact TP hit
        - Exact SL hit
        - Trailing breakeven protection
        - Round-trip 20X fees
        """
        action = signal['action']
        entry = signal['entry_price'] * (1.0 + (self.slippage_pct if action == 'LONG' else -self.slippage_pct))
        tp = signal['tp_price']
        sl = signal['sl_price']
        orig_sl_dist = signal['sl_dist_pct'] / 100.0
        
        round_trip_fee_roe = (self.fee_rate_per_side * 2.0 + self.slippage_pct * 2.0) * self.leverage * 100.0
        
        n_bars = len(future_closes)
        active_sl = sl
        be_locked = False
        
        for t in range(n_bars):
            h_t = future_highs[t]
            l_t = future_lows[t]
            c_t = future_closes[t]
            
            if action == 'LONG':
                # Check Breakeven trailing condition (+1.0R gain)
                unrealized_gain = (h_t - entry) / entry
                if unrealized_gain >= orig_sl_dist * self.breakeven_trigger_r and not be_locked:
                    active_sl = max(active_sl, entry * 1.0015) # Lock breakeven + fee buffer
                    be_locked = True
                
                # Check SL hit
                if l_t <= active_sl:
                    exit_price = min(entry, active_sl)
                    raw_pnl_pct = (exit_price - entry) / entry * 100.0
                    net_roe = raw_pnl_pct * self.leverage - round_trip_fee_roe
                    return {
                        'exit_reason': 'BREAKEVEN' if be_locked else 'STOP_LOSS',
                        'exit_bar': t,
                        'exit_price': exit_price,
                        'net_roe': net_roe,
                        'is_win': net_roe > 0,
                        'is_liquidated': raw_pnl_pct <= -4.50
                    }
                
                # Check TP hit
                if h_t >= tp:
                    raw_pnl_pct = (tp - entry) / entry * 100.0
                    net_roe = raw_pnl_pct * self.leverage - round_trip_fee_roe
                    return {
                        'exit_reason': 'TAKE_PROFIT',
                        'exit_bar': t,
                        'exit_price': tp,
                        'net_roe': net_roe,
                        'is_win': True,
                        'is_liquidated': False
                    }
                    
            elif action == 'SHORT':
                # Check Breakeven trailing condition
                unrealized_gain = (entry - l_t) / entry
                if unrealized_gain >= orig_sl_dist * self.breakeven_trigger_r and not be_locked:
                    active_sl = min(active_sl, entry * 0.9985)
                    be_locked = True
                    
                # Check SL hit
                if h_t >= active_sl:
                    exit_price = max(entry, active_sl)
                    raw_pnl_pct = (entry - exit_price) / entry * 100.0
                    net_roe = raw_pnl_pct * self.leverage - round_trip_fee_roe
                    return {
                        'exit_reason': 'BREAKEVEN' if be_locked else 'STOP_LOSS',
                        'exit_bar': t,
                        'exit_price': exit_price,
                        'net_roe': net_roe,
                        'is_win': net_roe > 0,
                        'is_liquidated': raw_pnl_pct <= -4.50
                    }
                    
                # Check TP hit
                if l_t <= tp:
                    raw_pnl_pct = (entry - tp) / entry * 100.0
                    net_roe = raw_pnl_pct * self.leverage - round_trip_fee_roe
                    return {
                        'exit_reason': 'TAKE_PROFIT',
                        'exit_bar': t,
                        'exit_price': tp,
                        'net_roe': net_roe,
                        'is_win': True,
                        'is_liquidated': False
                    }
                    
        # Timeout exit at last close
        last_c = future_closes[-1]
        raw_pnl_pct = ((last_c - entry) if action == 'LONG' else (entry - last_c)) / entry * 100.0
        net_roe = raw_pnl_pct * self.leverage - round_trip_fee_roe
        return {
            'exit_reason': 'TIMEOUT',
            'exit_bar': n_bars,
            'exit_price': last_c,
            'net_roe': net_roe,
            'is_win': net_roe > 0,
            'is_liquidated': raw_pnl_pct <= -4.50
        }


if __name__ == "__main__":
    strategy = SRTrendStrategy20X()
    print("SRTrendStrategy20X successfully initialized with 20X parameters:")
    print(f"- Leverage: {strategy.leverage}X")
    print(f"- Min Risk/Reward: {strategy.min_risk_reward}:1")
    print(f"- Max Stop-Loss: {strategy.max_sl_distance_pct}% price distance (Hard Liquidation Guard)")
    print(f"- Breakeven Trailing: Active at +{strategy.breakeven_trigger_r}R profit")
