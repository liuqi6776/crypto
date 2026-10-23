> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Codex 最终独立审查：三策略有限比较

本轮已完成唯一一次冻结历史回放，12 个资产／策略／成本组合、24 个独立连续段案例全部输出。全部组合的已闭合交易净收益上下界为负，未满足预注册净盈利支持条件。结论针对本轮机械定义及已接触历史；策略仍为 EXPLORATORY／UNVERIFIED，未获实盘就绪结论。

## 实际执行证据

正式命令为 `.venv/Scripts/python.exe -B scripts/pattern_comparison_round2_20261009.py --replay`。调用开始观察时间 2026-10-09 12:39:08 UTC，managed session 2906、启动标识 `615d93`；输出清单最后写入 12:43:23.243192 UTC，12:45:20.871267 UTC 观察到程序退出 0，完成标识 `a421fc`。未独立记录精确进程退出时刻，因此不把文件写入时间冒称退出时间。没有第二次正式回放或结果后调参。

原始输出清单 SHA256 为 `525d4736142d062ec56f9fd5e4d9d6824177da697ad23e365d9fcd05b632d3c4`。其 246 项原始产物的大小和 SHA256 均匹配，详见 产物与冻结身份审计 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/pattern_comparison_round2_20261009/codex_final_artifact_hash_audit.json`)。

## 独立核对

- 正常项目环境最终焦点及相关旧回归测试 **95 项通过**（32 项新测试＋63 项旧回归），exit 0、输出标识 `721df8`。包含完整公共入口的合成 24 案例、空／非空／删失账本、JSON/CSV 保存后读取、错误哈希拒绝和禁止覆盖。
- CLI 只读预检 98 个分钟分区＋14 项其他输入固定信息通过，8,841 条资金事件全部匹配真实注册小时 mark，最大差 31 ms；真实 dry-run 前后无文件或目录变化。
- 保存账本审计 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/pattern_comparison_round2_20261009/codex_final_saved_ledger_audit.json`)：**24 案例、18,257 笔已闭合交易、6 个删失仓位、6,865 条持仓资金费记录**，零核对失败。核对实际源开盘、模型价格冲击、固定 1,000 名义金额、双边实际名义金额费用、ATR 几何、因果时序、阶段／TTL、单仓／资金约束、退出参考价、替代路径经济值、真实资金时刻及每日现金归属。已闭合与删失费用／资金分开。
- 小时权益审计 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/pattern_comparison_round2_20261009/codex_final_mtm_audit.json`)：独立累计入场费、闭仓现金和资金事件，再加单一活动仓位的真实小时 mark 浮动价值。**420,048 行、24 案例**的六列现金／权益／预留额及回撤代理一致，最大金额差约 `1.66e-11` USDT。没有使用新信号、填单回放或合成 mark。
- 112 项输入固定信息、537 项受保护旧工件核对无变化，冻结协议、执行脚本、测试、澄清、预运行清单及内部授权的身份均匹配。
- 48 项配对比较中 **26 项 COMPUTED，22 项因账户路径不完整 NOT_RUN**；不对删失或部分现金伪造完整区间。

## 结果与范围

A 为 15m 布林下轨触及收回后，1–4 根后续完整 bar 内的反弹确认。B 为排除当前 bar 的前 20 根 high 阻力突破，再由不同 bar 回踩、确认。C 为共同趋势有效时每个 15m 完整收盘的纯趋势候选。三者共同使用已完成 4h EMA20>EMA50 且 EMA20>前 6 根值；下一分钟观察开盘的模型成交；1.5 ATR 止损、3 ATR 止盈和 24 小时限时。Wilder ATR14 在信号时冻结。

基础双边 taker 5 bp、双边不利冲击 2 bp；压力成本分别为 10 bp、4 bp。冲击已经进入成交价格和 gross，不能再扣。资金费保留实际 calc_time，采用 1 秒内真实小时 mark 开盘作估值代理；不是精确结算 mark 的证明。

ETH B 基础的毛收益 +70.79 USDT，扣费用 185.04 和资金费约 7.94 后净收益 −122.18。B 的绝对损失较小，同时交易量／暴露明显不同，不能因此认定有效或稳健。

每个币种／策略／连续段／成本场景独立 10,000 USDT，固定入场名义 1,000 USDT。每臂每场景 ETH 一段、SOL 三段，共分配 40,000 USDT，四个钱包不串联；SOL 汇总不是同一钱包年收益。6 个未闭合仓位保留入场费、已观测资金费和敞口，其完整账户／年度窗口收益 UNKNOWN。

净上下界是 **STOP_FIRST 主模型路径的资金费边界**，不覆盖全部真实价格路径。单笔同分钟替代路径单独列出；它不是重跑后的完整替代账户。模型点成交、分钟退出区间、小时回撤均为模型／观测网格代理。真实执行时刻、真实持仓时长、价差／深度／容量、真实盘中回撤和强平路径未知。2022–2025 全部受既往研究接触，没有未触碰 OOS。

## AGENTS 变更后检查链

下列四个命令均未执行；只读自定义 preflight 不等同于它们。跳过依据是此前及本轮持续保护旧观察策略、旧数据和研究工件的范围。

| 顺序 | 命令 | 实际状态与具体冲突 |
| --- | --- | --- |
| 1 | fetch_local_source_copies.py --verify | 跳过：仍会写 source_data/MANIFEST.json（1476–1477 行），并可能重复制不可变源。 |
| 2 | import_perp_data.py | 跳过：会写旧转换 feather、conversion_report.json 和 data_provenance.json。 |
| 3 | build_inventory.py | 跳过：默认写旧 inventory_manifest.json、external_path_catalog.json、mark_candle_gate.json。 |
| 4 | build_reports.py | 跳过：写旧 CONVERSION_REPORT.md 和 INVENTORY_SUMMARY.md。 |
| 5 | python -m pytest tests -q | 已按项目 .venv、-B、-p no:cacheprovider 执行；收集阶段 exit 1，既有 r3i_pytest_guard_v2 缺失（标识 174269）。未修旧环境或绕过工具自动审批。 |

完整套件不是 PASS。95 项针对本轮及相关回归的通过，不替代完整仓库检查、Freqtrade lookahead／recursive 工具或策略九门验证。没有实盘下单、市场数据下载、账户操作、服务或调度注册，原冻结观察策略和数据保留。

