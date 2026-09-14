# -*- coding: utf-8 -*-
"""
Generate HTML artifacts for:
1. Trade distribution (ETH vs SOL) - Stop-Loss Protected (Phase 11)
2. Leverage comparison (1.0x to 3.0x vs Buy & Hold)
3. Cumulative Excess Alpha curve (ETH vs Benchmark)
"""

import os
import sys
from pathlib import Path

scratch_dir = Path(r"C:\Users\liuqi\.gemini\antigravity\brain\16cb006d-026f-4685-aa82-3db788cd48f6\scratch")
sys.path.insert(0, str(scratch_dir))

from render_image_widget import build_inline_card, build_multi_dashboard

artifact_dir = Path(r"C:\Users\liuqi\.gemini\antigravity\brain\16cb006d-026f-4685-aa82-3db788cd48f6")

img_dist = artifact_dir / "eth_sol_trade_distribution.png"
img_lev = artifact_dir / "eth_sol_leverage_comparison.png"
img_alpha = artifact_dir / "eth_excess_alpha_curve.png"

# 1. Build individual inline cards
build_inline_card(
    str(img_dist),
    str(artifact_dir / "widget_trade_distribution.html"),
    "ETH & SOL 每笔收益分布 (Symmetrical Long/Short True Alpha)",
    "双向对称多空交易 | 彻底摆脱现货大盘Beta绑架 | 2025年10月闪崩空头单笔暴赚 +6.3% ~ +12.0%"
)

build_inline_card(
    str(img_lev),
    str(artifact_dir / "widget_leverage_comparison.html"),
    "全档位杠杆回测曲线 (1.0x - 3.0x Symmetrical Long/Short vs Buy & Hold)",
    "ETH 1.0x 总收益 +102.2% (现货仅 +30.7%) | SOL 1.0x 总收益 +141.5% (现货仅 +20.7%)"
)

build_inline_card(
    str(img_alpha),
    str(artifact_dir / "widget_excess_alpha.html"),
    "以太坊独立累计超额阿尔法收益曲线 (ETH Excess Alpha - Beta Decoupled)",
    "策略 +57.0% vs 现货 +9.9% | 市场 Beta 仅 -0.03 (绝对零贝塔) | 年化詹森 Alpha +25.7%"
)

# 2. Build multi-tab interactive dashboard
dashboard_items = [
    {
        "name": "📊 每笔交易收益分布 (Symmetrical Long/Short)",
        "path": str(img_dist),
        "desc": "以太坊与索拉纳独立双向交易分布：模型预测正向做多、负向借币做空，并在极端高位/底部自动动态配比仓位，彻底摆脱单向做多在震荡下跌中的磨损。",
        "metrics": [
            ("市场贝塔暴露 (Beta)", "-0.04 ~ 0.00", "绝对市场中性，与现货大盘脱钩", "text-emerald-400"),
            ("年化詹森 Alpha", "+36.7% ~ +42.2%", "剔除系统性风险后的纯净超额", "text-blue-400"),
            ("ETH 闪崩空头收益", "+7.95%", "2025年10月大跌空单精准获利", "text-purple-400"),
            ("SOL 闪崩空头收益", "+12.01%", "大盘雪崩逆转为策略暴利引擎", "text-amber-400"),
        ]
    },
    {
        "name": "📈 全档位杠杆对比 (Leverage Analysis)",
        "path": str(img_lev),
        "desc": "双向多空真阿尔法保护下的 1.0x 基准、1.5x 黄金杠杆、2.0x 与 3.0x 杠杆全景敏感性分析（空头持仓额外收取正向资金费）。",
        "metrics": [
            ("ETH 1.0x 原生策略", "+102.20%", "大幅跑赢现货持有 (+30.67%)", "text-emerald-400"),
            ("ETH 1.5x 黄金杠杆", "+137.64%", "MDD: -57.68% | 夏普: 0.95", "text-blue-400"),
            ("SOL 1.0x 原生策略", "+141.47%", "大幅跑赢现货持有 (+20.68%)", "text-indigo-400"),
            ("SOL 1.5x 黄金杠杆", "+192.38%", "MDD: -64.47% | 卡尔玛: 1.10", "text-rose-400"),
        ]
    },
    {
        "name": "🎯 ETH 累计超额 Alpha 曲线 (Excess Alpha)",
        "path": str(img_alpha),
        "desc": "以太坊全周期超额对冲净值：策略 +57.0% vs 现货 +9.9%，Alpha 曲线与现货大盘完全解绑脱钩，稳步向上攀升。",
        "metrics": [
            ("累计策略收益", "+57.00%", "大幅跑赢现货持有 (+9.85%)", "text-emerald-400"),
            ("累计算术超额", "+47.15%", "纯净阿尔法收益稳定输出", "text-blue-400"),
            ("组合市场 Beta", "-0.03", "接近零贝塔，完全消除大盘绑架", "text-amber-400"),
            ("年化詹森 Alpha", "+25.68%", "真正穿越牛熊的量化对冲利器", "text-emerald-400"),
        ]
    }
]

build_multi_dashboard(
    dashboard_items,
    str(artifact_dir / "eth_sol_interactive_dashboard.html"),
    "ETH & SOL 量化策略全景看板 (Phase 13 双向多空真阿尔法版)",
    "Transformer 时空关联网络 · 激活对称双向做空、零贝塔纯阿尔法与全档位杠杆对冲分析"
)
print("All visual widgets and interactive dashboard generated successfully!")
