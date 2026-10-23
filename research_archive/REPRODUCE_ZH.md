> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 可复核内容与复现边界

本次检查使用Python标准库，不需交易所账户、密钥、网络、行情下载或服务器。以下从仓库根执行：

```sh
python -m unittest discover -s tools/research_archive -p "test_*.py" -v
python tools/research_archive/archive_validator.py research_archive
python tools/research_archive/verify_aggregate_evidence.py research_archive
```

第一项检查去敏、路径拒绝、链接和manifest篡改检测等合成案例；第二项检查归档的文件类型/大小、哈希、JSON、敏感信息模式和本地链接；第三项独立核算精选导出表的成本/权益恒等式与事件计数。执行结果见[本次验证记录](VALIDATION_RESULTS.json)。启发式敏感信息扫描不是完整安全认证。

`archive_manifest.json`中的`original_sha256`对应已读源文件，`export_sha256`对应公开去敏版，二者不应混用。公开文件经过路径去敏、链接整理、明确的内容删除及历史说明后哈希可能不同；原研究配置里的data/code hashes仍是当时证据，不意味着本次重新访问了数据。

研究级完整重放需要各研究绑定的引擎/代码、参数、版本、冻结输入及真实数据时钟。当前包有精选报告、配置、汇总和原验收记录，缺少全部原始行情、逐事件账本及完整依赖代码，**不提供一键完整历史重放**。原报告里的运行命令仅保留当时来源引用，不能视为已经移植到此仓库；路径占位须依据合法来源明确绑定。

数据应来自报告标识的交易所原始来源和已验证本地快照。实际获取前需分别核实许可、市场身份、可用时点、结算事件、缺口、mark口径和哈希；不得把期货改称现货、用插补制造funding/mark，或使用受拒绝路径替代方案。此次没有下载数据，没有访问被拒分钟文件，也没有代用户接受新的数据许可。

**没有执行**：策略重训/寻优、行情复制与转换、全量历史策略pytest、Freqtrade回测/分析、逐笔交易完整再核算、collector安装/重启、30日前向、实盘或模拟订单。没有修改源研究目录，因此其依赖原始行情的再生成流水线不在此次文档归档执行范围。

旧测试收据保留各自日期和失败项。报告提到45测试、25合成测试或数千通过项，不等于本次重跑；存在旧失败的全量套件也没有被“定向通过”改写为全绿。

