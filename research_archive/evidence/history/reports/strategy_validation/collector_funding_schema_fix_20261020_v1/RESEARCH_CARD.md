> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 资金费采集记录兼容性修复卡

- 日期：2026-10-20 北京时间；对应 2026-10-19 UTC。
- 状态：REGRESSION_CONFIRMED / PATCH_OFFLINE_VERIFIED / DEPLOYMENT_BLOCKED。
- 缺陷：升级新增的精确四字段校验拒绝官方 rateType=Regular，300 条已有本地样本可复现。
- 最小修复：仅一个记录模块；Regular 兼容，原核心检查保留，Special/未知字段拒收，增加不含任意值的结构诊断。
- 验证：两运行时合计 78 通过、2 跳过；全量未运行。
- 自然运行：此前资金费 108 次 HTTP 200 拒收；原文缺失，逐次字段原因未知，不重建。
- 部署：两次被系统拒绝创建保护锁；源文件未改，旧校验仍在。
- 约束：没有新增采集、调度、账户动作、观察期或回测；PnL=N/A。
- 决策：保留补丁，待具有源目录写入能力的已授权会话完成保护安装，再以已有任务自然执行证据验收。前向准入仍阻塞、30 天观察未启动。

详见 最终审查 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/collector_funding_schema_fix_20261020_v1/FINAL_REVIEW_ZH.md`) 和 [机器结论](OUTCOME.json)。旧 v1 的冻结报告保持不变，本卡追加说明实际自然运行与后续修复状态。
