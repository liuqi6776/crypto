> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 主代理验证记录

日期：2026-10-21 UTC。最终权威统计运行开始记录：2026-10-21T04:16:58.929407+00:00。代码由GPT-6 Luna实现；主代理独立审查、提出修复、运行和对账。

## 已完成检查

1. 审计器11项测试、账本诊断9项测试，共20项通过（主代理独立运行，unittest exit0）。覆盖空/坏数据、null/非正OHLC、epoch单位、hash变动、输出隔离与拒绝覆盖、随机对照种子/分层、midrank ties、缺失资金费保持UNKNOWN、保留交易身份、风险分母不能向上缩放等。没有为原项目工程全套测试宣称通过。
2. 5个代表性源文件结构审计成功，输出 `data_audit_run_v1/audit_report.json` 与 `audit_summary.csv`；PASS仅是结构检查。每文件读取前后SHA/bytes一致。配置是 `audit_manifest_v1.json`。
3. 最终 `ledger_reanalysis.py --output-dir root_review_run_v1` exit0；固定5个CSV/JSON输入、原FINAL_MANIFEST、旧代码身份、协议哈希读取前后复核。源文件未修改。
4. 主代理用独立PowerShell Import-Csv/Measure-Object复核BASE/C3毛额、费用、滑点、净额、删除11笔且零盈利，和Python输出一致。41条模拟交易的两档成本算术容差1e-8 USDT，保留15笔价格、数量、持有区间、gross/费用/滑点/net完全一致。
5. 用同一最终代码再次运行 `--output-dir root_reproduction_v1` exit0，12个确定性CSV/Markdown产物逐字节SHA一致。summary.json排除不同运行元数据hash后完全一致。见 `REPRODUCTION_HASHES.csv`。run_metadata的时间/目录及其identity hash不同是预期，不是统计差异。
6. 人工核对报告主要表格与最终机器结果；月度保留零交易月份，上/下半年均披露；成本压力同账本；真实资金费/延迟成交/容量/保证金未知项没有填零或补造。

## 代码审查及修复

初稿发现并修复：审计器缺null/空数据/非正OHLC检查及覆盖旧输出风险；加入scan前后hash闭合；整数时钟需显式单位。账本诊断修正midrank ties重复计入、缺资金费字段误作零事件的风险、禁止向上缩放BASE、输出目录检查顺序；增加15笔保留交易逐字段身份检查。没有调整候选、参数、时间窗、成本档位或随机种子。

最终实现SHA256：`7ac5cf2a895fda0e87e7cb0912aa90bc691b221c26f38e60738376983647e349`。
冻结配置SHA256：`18f46c0776dd34e5436dba426fc035c22ee9ff85c6f9429219c88aea9264189a`。
协议SHA256：`8a16cf75aa284473e7bd3ef93b027e00660422a3237b3fa3f656d78044685f63`。
运行环境：既有Python3.12.11，pandas2.2.3，numpy2.2.6。完整源与代码hash见 `root_review_run_v1/run_metadata.json`；交付文件hash见 `DELIVERABLE_SHA256.csv`。

## 范围与剩余限制

没有执行新撮合、共享账户风险预算重放或微观结构回测；没有重跑原项目122项/全项目检查，本轮20项测试不能替代它们。数量子集抽样存在共同事件依赖，不是显著性检验。风险/实际持有分钟归一化只是事后分母诊断；旧规则事后提出、历史已暴露，不能升格样本外。

原始接收时间、队列、真实订单撤单确认、连续盘口、强平资料在已审计范围不足，新机制实验NOT_RUN。读取操作成功，没有本轮读取拒绝；上游已知crypto写PermissionError未重试，也未触碰安装/权限/锁。NBER网页403仅影响该网站原文获取，已用原作者机构资料核验机制并注明版本，不影响本地账本再分析。
