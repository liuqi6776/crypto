> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 本地复现说明

工作区：`<SOURCE_ROOT:research-runs>/2026-10-22/task-2`。

原数据路径及 SHA256 见批次目录的 `source_audit.json`；它们只读使用。本任务没有下载或复制原始行情到交付目录。复现需要这些原文件仍可读取且哈希一致。若哈希不一致，程序应停止，不应重新选数据维持收益。

已验证环境为 Python 3.12.11、pandas 2.2.3、numpy 2.2.6、pyarrow 21.0.0、pytest 8.4.2。既有解释器位于 `<SOURCE_ROOT:crypto-leverage>/.venv/Scripts/python.exe`；只是调用解释器，不运行原工程入口。不需要账户、密钥或网络连接，也不要启动原采集器或实盘进程。

在 PowerShell 中进入工作区后执行。新回测必须使用尚不存在的直接子目录，例如 `outputs/v4`，程序拒绝覆盖 v1/v2/v3。以下是复现命令，不代表本轮额外执行了一遍：

```powershell
Set-Location '<SOURCE_ROOT:research-runs>/2026-10-22/task-2'
$studyPython = '<SOURCE_ROOT:crypto-leverage>/.venv/Scripts/python.exe'
& $studyPython -B -m pytest -q -p no:cacheprovider --basetemp .\test_scratch_reproduction tests
& $studyPython -B .\run_study.py --protocol .\protocol_config.json --expected-sha256 50e3c6873501ca14c2c6ce05ba4f02aae5e013778f6529af41121f4c2ecaeff3 --output .\outputs\v4
& $studyPython -B .\verify_results.py .\outputs\v4
& $studyPython -B .\verify_summary.py .\outputs\v4
& $studyPython -B .\capacity_diagnostic.py --run-dir .\outputs\v4
```

`make_report_tables.py --run-dir .\outputs\v4 --output .\REPORT_TABLES_REPRODUCED_ZH.md` 可从完成的矩阵重建中文全表。程序会拒绝覆盖既有文件，不要删除原报告以强行重跑。容量诊断默认写入工作区 `diagnostics/v4`，与已完成批次分开保存。

pytest 的 basetemp 必须选工作区内尚不存在的新专用目录；先核实其绝对路径。pytest 可能清空既有 basetemp，因此不要指向有价值目录。此环境的默认系统临时路径曾拒绝写入，不要重试该受限路径，详见 PERMISSION_EVENTS_ZH.md。

`run_study.py` 每个情景完成后保存进度，全部完成才把 manifest 标记为 COMPLETED；中断或 FAILED 不能视为完整结果。程序同时保存协议、配置、引擎、审计器、运行器、依赖版本的输入快照，并在结束时检查其字节哈希未改变。源数据审计在读取前后核对身份。

每个情景的 `trades.csv` 是按从开仓至最终平仓汇总的完整生命周期账本，机械部分减仓不重复计为新交易；`events.csv` 保存每次入场、退出、资金费及状态事件；`equity.csv` 保存资金、敞口、分币损益贡献及事件序号。事件时间可含纳秒，应保留 CSV 原文本精度，不要先用 Excel 覆写再核算。

独立核算器不导入引擎。`verify_results.py` 从原价、原资金费率、近似 mark 与事件序号重放账本；`verify_summary.py` 从账本重算 36 行组合及 108 行分币指标。`capacity_diagnostic.py` 仅对已完成账本做参与率和分钟内歧义统计，不改变成交或收益。

本轮为尽早验收核心结果，先核算八个全期核心情景，再由 `verify_incremental.py` 使用同一核算函数跟随剩余情景。该驱动仅在核心检查点及其账本哈希匹配时复用已有验收，最终要求 36 个精确情景、完成 manifest 与全部哈希再次一致。普通复现使用上面的 `verify_results.py` 一次核算全量即可，无须先准备旧检查点。

本轮 v1、v2 均在零情景完成时主动中断，保存作实现纠错记录；最终完整结果位置及验收状态以 REPORT_ZH.md 为准。它们不是三套参数试验。
