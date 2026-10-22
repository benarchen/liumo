# P1／P2 整改结项

当前范围内的 G1、G3、G4 已完成实施与验收。备份任务 G2／问题 R4 按用户指令移出，不计入本次验收，也不标为验证通过。施工过程和检查点见 [清单](/Users/chenge/project/liumo/goals/20261022-2046-p1-p2-remediation.md) 。本次结项是工作区代码与文档交付，不包含 Git 提交、集成、标签或推送。

## 问题与证据

| 问题 | 结果 | 交付与证据 |
| --- | --- | --- |
| R1 历史损坏 complete 不能重试 | 已修复 | 先复现，再统一校验和显式恢复；旧快照保留。[G1 证据](/Users/chenge/project/liumo/evidence/feasibility/archive-integrity.json) |
| R2 账本状态未区分文件完整性 | 已关闭 | 三类 `verify` 与单篇 `repair`，状态口径分开。[使用说明](/Users/chenge/project/liumo/docs/archive-integrity.md) |
| R3 历史入口缺专项验收 | 已关闭 | 18 项历史专项与两篇真实隔离归档；给定输入处理已验收，全年覆盖另计。[G3 证据](/Users/chenge/project/liumo/evidence/feasibility/history-import-validation.json) 、[用法](/Users/chenge/project/liumo/docs/history-import.md) |
| R5 正式运行依赖旧实验 | 已关闭 | 正式共享模块归属 `liumo/`，旧模块保留反向兼容导入；静态及新进程导入边界通过。[G4 证据](/Users/chenge/project/liumo/evidence/feasibility/engineering-consolidation.json) |
| R6 设计、状态及实现口径冲突 | 已关闭当前范围 | 统一归档类型、时间、完整性与来源覆盖；README、AGENTS、Roadmap 和产品设计同步，历史记录保留当时语境 |
| R7 环境复现和质量入口不足 | 已关闭当前 Mac 范围 | 新核心虚拟环境离线重建；产品／浏览器／旧实验分层入口，失败和跳过非零退出。[开发说明](/Users/chenge/project/liumo/docs/development.md) |

## 最终验收

- 版本化入口 `.venv/bin/python -m tools.check --suite all`：491 项收集、491 项运行并通过，无跳过，45.077 秒；产品 108、本地浏览器 11、旧实验 372。
- 必需 unittest 全量入口在新增最后 1 项工程报告回归前完成 490 项通过、无跳过；最终版本由上方质量入口运行全部 491 项，不将两次计数混用。
- 全新核心环境仅装既有 5 个固定包，无 Playwright 或抓包包；移除测试 PATH 中的 Node 后，108 项产品逻辑及普通 CLI 帮助通过，`pip check` 通过。本机 Chrome 仍在，没有卸载；核心测试不启动它。
- 共享迁移的 17 个函数 AST 相同；固定构造输入下 RSS／手动元数据、Markdown、文章 key 和上海门控结果迁移前后一致。
- 正式 RSS 2 篇、手动 2 篇只读核验均 intact，20 条 RSS baseline 不计文章；正式历史账本为空。G3 的两篇真实样本在独立验证目录，不冒充正式历史全集。
- 静态检查覆盖语法、正式导入边界、Markdown 链接／锚点与围栏、Roadmap 顺序及上限；`git diff --check` 通过。

真实和构造证据各自限定：G1 的恢复演练使用真实 RSS 的隔离副本，G3 使用此前保存的公开 RSS 原始输入及实际图片请求；浏览器回归都是本地构造页面，不访问微信。G4 未运行旧代理、证书、凭证或抓包实验。

## 保留的产品边界

猫笔刀自动追更仍依赖公开 RSS 的可见窗口和上游延迟；不承诺当日零延迟或全年无遗漏。历史日期来自未核实的 RSS pubDate。评论、原页截图、多号自动追更及微信通知仍暂缓。

全年历史任务仍缺完整来源清单；休眠／唤醒、物理断网及注销／重登的设备行为仍未实测。环境复现仅证明当前 Mac 与所列版本，在线重新下载依赖及其他系统／Python 版本未在本轮测试。

下一轮宜优先量化来源延迟和窗口覆盖；全年导入只有在获得可核对的完整来源后才能验收。用户已另行授权 Git 提交、快进集成、附注标签与推送，版本标识采用 `remediation-20261022`；具体范围与实际引用见 [版本管理说明](/Users/chenge/project/liumo/docs/version-control.md#2026-10-22-p1p2-整改版本) 。
