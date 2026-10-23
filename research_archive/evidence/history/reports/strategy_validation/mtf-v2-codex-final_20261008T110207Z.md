> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 通道边缘与均线交叉：最终研究结论

完成72个固定候选比较，尚未找到在所检查前后历史均稳定盈利的候选。普通MA5/10交叉组在开发段排名靠前；SOL开发有微正，固定后检查Q4和2023均转负。不能称为最佳交易点或十倍可用。

## 规则和计算

比较通道边缘预挂、完成均线交叉、边缘与交叉结合三类。通道为完成5m/15m BB20，小时方向为EMA20/50，完成5m交叉为EMA5/20或普通MA5/10。入口为通道内侧5%/10%，没有15%收回条件。目标比例比较60%/80%/90%；两组通道内止损是研究假设，不是用户实际止损。开发为2022年1–9月，固定后检查Q4与2023；全部历史已被研究过，不是 untouched OOS。

设下沿L、上沿U、W=U−L：
- 做空：入场U−eW，目标U−tW，止损U−sW；做多对称为L+eW、L+tW、L+sW。
- 用户例子e=.10、t=.80：100–110通道，109做空、102止盈。研究假设s=.025/.05分别给109.75/109.5止损。
- 计算水平不保证成交或赚钱。独立MA族在确认交叉后相对已知close改善1bp入场，可能位于通道中部，不能视为相同的边缘入场。

## 逐币开发排名最高候选的固定后段结果

两币均是完成5m普通MA5/10交叉族；ETH使用15m通道，SOL使用5m通道。百分比为每笔入场名义本金平均净盈亏，含研究费用/资金估值代理，非账户收益。

|币种|2022年1–9月开发|2022Q4历史检查|2023历史检查|
|:---|---:|---:|---:|
|ETH|−0.0438%（323笔）|−0.0299%（93笔）|−0.0983%（333笔）|
|SOL|+0.0146%（226笔）|−0.0608%（84笔）|−0.1224%（330笔）|

逐币选择是查看原joint比较后追加的事后补充，只从开发段选原72成员，未增候选、改参数或按后段补选。全部后段压力情景也负。

## 发现和限制

入场点之外，止损距离会决定净结果。2022-11-10 SOL均线例子中，代理模型约11做空，通道止损12.74；真实价格55分钟连续上涨并穿止损，基础净亏约15.918%入场本金。没有跨数据缺口或虚构跳价。通道中部的交叉入口若仍套边缘止损，可能目标很近、风险很大；这不是用户实际止损证据。

基准entry/TP maker0.02%单边，stop/time taker0.05%+2bps为代理。固定模拟成交不变、全部按maker0.02%并取消退出滑点，选中候选2023均值仍负；此乐观核算不能证明maker止损成交。

独立30相关测试通过。主研究60,374条；连同补充复用开发记录共62,323条账本、1,315条已记账资金现金流核算误差远小于1e-8bps。50价格分区身份与开发排序已核对。SOL缺7200分钟未填补，跨缺口待单取消，完成账本无未知跨缺口持仓。

仍缺quotes/queue/spread、精确mark事件、每笔signal/decision/order-active/stop/target/通道计划字段、untouched OOS和保证金/强平路径。时间检查仅entry/exit/窗口/60分钟，不是完整生命周期因果证明。全仓verify/import/full pytest受旧证据/缺模块阻碍，未宣称通过。

10x账户收益/回撤/清算距离均N/A。强平以mark price为基础，cross还受余额影响；缺这些输入不能从价格代理亏损计算清算时点。[币安说明](https://www.binance.com/en/blog/futures/5845477141003990750)

## 可核对产物

72候选完整比较 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/mtf_trend_range_maker_v2_r1_20261008.md`)；逐币选择 (`provenance:external/dd8c86d60fc2d0ed`)；Codex独立审计 (`provenance:external/170553ddae968731`)；费用敏感性 (`provenance:external/a599254babada688`)；最大亏损计划核验 (`provenance:external/d58bf47be7f3c743`)。

- [mtf-v2-ethusdt-posthoc_20261008T110207Z.md](<SOURCE_ROOT:crypto-leverage>/reports/strategy_validation/mtf-v2-ethusdt-posthoc_20261008T110207Z.md
- [mtf-v2-solusdt-posthoc_20261008T110207Z.md](<SOURCE_ROOT:crypto-leverage>/reports/strategy_validation/mtf-v2-solusdt-posthoc_20261008T110207Z.md

消费时元数据/代码已保留SHA匹配快照。最终维护仅刷新source manifest的generated_utc，entries与价格字节未变；原冻结报告仍绑定其消费身份。维护链verify exit1、import exit3、inventory/reports exit0、full pytest exit1（既有缺r3i模块）；本任务30相关测试独立通过。
