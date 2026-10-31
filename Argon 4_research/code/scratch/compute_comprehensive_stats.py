import pandas as pd
import numpy as np

# Load dataset
df = pd.read_parquet('scratch/funding_dataset_with_returns.parquet')

# Define bins
bins = [
    -np.inf, 
    -0.01,     # <= -1.0%
    -0.005,    # -1.0% to -0.5%
    -0.002,    # -0.5% to -0.2%
    -0.0005,   # -0.2% to -0.05%
    0.0,       # -0.05% to 0%
    0.0002,    # 0% to +0.02% (Neutral)
    0.0005,    # +0.02% to +0.05%
    0.001,     # +0.05% to +0.1%
    0.003,     # +0.1% to +0.3%
    0.005,     # +0.3% to +0.5%
    np.inf     # >= +0.5%
]

labels = [
    '1. 极度负值 (<= -1.0%)',
    '2. 深度负值 (-1.0% ~ -0.5%)',
    '3. 高度负值 (-0.5% ~ -0.2%)',
    '4. 中度负值 (-0.2% ~ -0.05%)',
    '5. 轻度负值 (-0.05% ~ 0%)',
    '6. 中性基准 (0% ~ +0.02%)',
    '7. 轻度正值 (+0.02% ~ +0.05%)',
    '8. 中度正值 (+0.05% ~ +0.1%)',
    '9. 高度正值 (+0.1% ~ +0.3%)',
    '10. 深度正值 (+0.3% ~ +0.5%)',
    '11. 极度正值 (>= +0.5%)'
]

df['bin'] = pd.cut(df['fundingRate'], bins=bins, labels=labels, right=False)

def analyze_df(sub_df, name="全部标的"):
    print(f"\n=======================================================")
    print(f"       【统计分布报告: {name} (样本量 N = {len(sub_df)})】")
    print(f"=======================================================")
    
    results = []
    for b in labels:
        b_df = sub_df[sub_df['bin'] == b]
        n = len(b_df)
        if n == 0:
            continue
        
        # Returns
        p1 = b_df['ret_prev_1'].dropna() * 100
        f1 = b_df['ret_fwd_1'].dropna() * 100
        f3 = b_df['ret_fwd_3'].dropna() * 100
        f6 = b_df['ret_fwd_6'].dropna() * 100
        
        win_rate_1 = (f1 > 0).mean() * 100
        win_rate_3 = (f3 > 0).mean() * 100
        
        mean_p1 = p1.mean()
        mean_f1 = f1.mean()
        med_f1 = f1.median()
        std_f1 = f1.std()
        
        mean_f3 = f3.mean()
        med_f3 = f3.median()
        
        q25 = f1.quantile(0.25)
        q75 = f1.quantile(0.75)
        
        pos_gains = f1[f1 > 0]
        neg_losses = f1[f1 < 0]
        avg_gain = pos_gains.mean() if len(pos_gains) > 0 else 0
        avg_loss = abs(neg_losses.mean()) if len(neg_losses) > 0 else 1
        pl_ratio = avg_gain / avg_loss if avg_loss > 0 else 0
        
        results.append({
            '资金费率区间': b,
            '样本数N': n,
            '前8h涨跌%': f"{mean_p1:+.2f}%",
            '次8h均值%': f"{mean_f1:+.2f}%",
            '次8h中位%': f"{med_f1:+.2f}%",
            '次8h上涨率%': f"{win_rate_1:.1f}%",
            '次8h标准差%': f"{std_f1:.2f}%",
            '25%分位': f"{q25:+.2f}%",
            '75%分位': f"{q75:+.2f}%",
            '盈亏比': f"{pl_ratio:.2f}",
            '次24h均值%': f"{mean_f3:+.2f}%",
            '次24h上涨率%': f"{win_rate_3:.1f}%",
        })
    
    res_df = pd.DataFrame(results)
    print(res_df.to_string(index=False))
    return res_df

res_all = analyze_df(df, "全市场所有合约样本 (2023-2026)")

# Analyze Majors vs Altcoins
major_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'DOGEUSDT']
res_majors = analyze_df(df[df['symbol'].isin(major_symbols)], "主流币 (BTC, ETH, SOL, BNB, DOGE)")
res_alts = analyze_df(df[~df['symbol'].isin(major_symbols)], "山寨币与高波动代币")

# Extreme Deep Dive:
print("\n" + "="*70)
print("【极度负费率 (<= -0.5%) 案例深挖与胜率陷阱】")
print("="*70)
neg_extreme = df[df['fundingRate'] <= -0.005]
print(f"极度负费率样本总数: {len(neg_extreme)}")
print("极度负费率事件的前10大涨幅案例 (次8小时):")
top_gains = neg_extreme.sort_values('ret_fwd_1', ascending=False)[['symbol', 'fundingTime', 'fundingRate', 'ret_prev_1', 'ret_fwd_1', 'ret_fwd_3']].head(5)
top_gains['fundingRate'] = (top_gains['fundingRate']*100).map(lambda x: f"{x:.3f}%")
top_gains['ret_prev_1'] = (top_gains['ret_prev_1']*100).map(lambda x: f"{x:+.2f}%")
top_gains['ret_fwd_1'] = (top_gains['ret_fwd_1']*100).map(lambda x: f"{x:+.2f}%")
top_gains['ret_fwd_3'] = (top_gains['ret_fwd_3']*100).map(lambda x: f"{x:+.2f}%")
print(top_gains.to_string())

print("\n极度负费率事件的前10大崩盘腰斩案例 (次8小时 - 轧空末期直接砸盘爆多头):")
top_losses = neg_extreme.sort_values('ret_fwd_1', ascending=True)[['symbol', 'fundingTime', 'fundingRate', 'ret_prev_1', 'ret_fwd_1', 'ret_fwd_3']].head(5)
top_losses['fundingRate'] = (top_losses['fundingRate']*100).map(lambda x: f"{x:.3f}%")
top_losses['ret_prev_1'] = (top_losses['ret_prev_1']*100).map(lambda x: f"{x:+.2f}%")
top_losses['ret_fwd_1'] = (top_losses['ret_fwd_1']*100).map(lambda x: f"{x:+.2f}%")
top_losses['ret_fwd_3'] = (top_losses['ret_fwd_3']*100).map(lambda x: f"{x:+.2f}%")
print(top_losses.to_string())

print("\n" + "="*70)
print("【极度正费率 (>= +0.3%) 表现分析】")
print("="*70)
pos_extreme = df[df['fundingRate'] >= 0.003]
print(f"极度正费率样本总数: {len(pos_extreme)}")
print("次8小时上涨比例:", f"{(pos_extreme['ret_fwd_1'] > 0).mean()*100:.2f}%")
print("次8小时均值:", f"{pos_extreme['ret_fwd_1'].mean()*100:+.2f}%")
print("次24小时上涨比例:", f"{(pos_extreme['ret_fwd_3'] > 0).mean()*100:.2f}%")
print("次24小时均值:", f"{pos_extreme['ret_fwd_3'].mean()*100:+.2f}%")
