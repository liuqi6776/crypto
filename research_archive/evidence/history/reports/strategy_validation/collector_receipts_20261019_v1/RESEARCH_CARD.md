> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 2026-10-19：公共采集记录升级 v1

- **状态：DEPLOYED / OFFLINE_VERIFIED / NATURAL_RUN_PENDING。**
- 授权：用户明确同意现有采集的接收时钟、原始版本和失败日志升级；未授权启动 30 天观察。
- 变更：部署 5 个代码/说明文件，增加原始响应哈希版本、UTC 接收与落盘记录、请求 ID、缓存版本映射、计划起点及重启恢复。
- 验证：18 项专项 + 8 项根代理检查在 Python 3.12 和既有调度 Python 3.11 均通过；部署前后各 79 项完整性检查通过；实际入口 dry-run 通过。
- 旧证据：25 个源缓存、三个 D 盘样本和旧冻结研究产物哈希未变；三个离线样本接收时钟保持 LEGACY_UNKNOWN。
- 自然运行：尚未观察。下一次既有任务为 2026-10-20 04:00 北京时间；源账本仅含计划/初始化记录，真实 HTTP 尝试与新前向记录均为 0。
- 研究边界：forward admission 仍 BLOCKED，30 天观察 NOT_STARTED，PnL N/A，不构成新 OOS 或有效性证明。
- 测试异常：初次有一次未完整解码的不稳定失败，原证据保留；全新锁竞争加固后的最终双环境复测全部通过。未运行全局再生成或全量 pytest。
- 决策：继续核验既有自然采集的记录链；暂停前瞻研究准入与策略晋级。

详见 中文审核报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/collector_receipts_20261019_v1/FINAL_REVIEW_ZH.md`)、机器结果 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/collector_receipts_20261019_v1/OUTCOME.json`)、下一次自然运行验收 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/collector_receipts_20261019_v1/review/NEXT_NATURAL_RUN_REVIEW_ZH.md`)。
