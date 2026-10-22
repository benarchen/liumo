# 留墨 liumo

当前提供猫笔刀单号的 **RSS 内容快照归档**：读取公开 RSS，保存 Markdown、本地配图、公开原链接和元数据；有去重、失败恢复、上海时区门控及本机通知出口。默认运行不打开微信原文、不使用账号会话、不读取评论。

也提供独立的 `save URL`，立即保存任意微信公众号可正常访问的标准图文文章，不等待 RSS。这个显式入口使用项目专用 Chrome 页面，保存原文正文快照及本地配图，不读取评论、不生成截图。

`complete` 表示对应类型的正文快照、配图与元数据在归档时齐全；RSS 原文发布时间仍待核实，手动原文时间独立核对。两者均不含评论与原页截图，不能解释为整页完整归档。新内容按启用后的首次发现处理，初始化时列表中的文章只建立基线。详细状态见 [ROADMAP](/Users/chenge/project/liumo/ROADMAP.md) ，运行与恢复说明见 [MVP 使用说明](/Users/chenge/project/liumo/docs/maobidao-mvp.md) 。

## 使用

在 `/Users/chenge/project/liumo` 运行，沿用项目 `.venv/`。新环境可仅安装 `requirements-core.txt`，显式手动页面另需 `requirements-browser.txt`；环境与检查入口见 [开发说明](/Users/chenge/project/liumo/docs/development.md) ：

```bash
.venv/bin/python -m liumo --help
.venv/bin/python -m liumo status
.venv/bin/python -m liumo verify
.venv/bin/python -m liumo check
.venv/bin/python -m liumo tick
.venv/bin/python -m liumo save 'https://mp.weixin.qq.com/s/aZD7YZl0Fjsjsa7MHVyMoA'
```

- `check` 立即检查 RSS，串行处理最多 3 篇待处理文章；可用 `--limit 1` 至 `--limit 5` 调整本次预算。
- `tick` 只在北京时间 22:00、22:30、23:00、23:30 到期或需要恢复补查时执行，错过多次合并。普通空闲心跳不请求 RSS。
- `status` 查看启用时间、成功检查、任务与人工处理项；未初始化返回 `not_initialized`，不创建空数据库。它只报告账本状态，`integrity_checked=false`，不证明文件当前完整。
- `verify` 离线只读核验 RSS、手动和历史账本指向的正文／配图；显式 `repair --scope rss|manual|history --key <article-key>` 单篇修复，先验证新快照再更新索引，保留旧文件。状态、隔离参数与限制见 [完整性与修复说明](/Users/chenge/project/liumo/docs/archive-integrity.md) 。
- `retry` 有限处理未完成任务，包含已用尽自动次数的任务。访问／来源拒绝时先检查原因，不盲目循环执行。
- `history` 按上海日期范围导入给定 RSS 输入，独立账本、去重与恢复；处理完成和来源覆盖分开报告。命令及退出码见 [历史导入说明](/Users/chenge/project/liumo/docs/history-import.md) 。
- `save URL` 立即归档单篇公开微信文章，输出保存目录；重复成功结果校验后直接复用，`--refresh` 保留新的读取结果。使用方法与访问限制见 [链接归档说明](/Users/chenge/project/liumo/docs/manual-archive.md) 。

当前 Mac 的正式基线已初始化，**不要重复执行 init**。新环境首次使用才运行：

```bash
.venv/bin/python -m liumo init
```

`init` 正常读取当前列表后记录启用时间，将当时已有文章记为 `baseline`，不归档这些历史内容，也不会覆盖现有初始化状态。上游延迟可能让启用前发布的文章在之后首次出现；RSS 时间和原文时间均不用于已核实发布时间声明。

## 查看来源与技术样本

```bash
.venv/bin/python -m liumo source
.venv/bin/python -m liumo sample
```

`source` 输出安全列表摘要，不打印正文 HTML。`sample` 只保存一篇当前 RSS 技术样本，不改变正式启用时间或补历史策略；所有样本使用新目录，不覆盖旧产物。

## 数据与产物

- 运行代码：[liumo/](/Users/chenge/project/liumo/liumo) 。
- 正式状态：[state/maobidao/](/Users/chenge/project/liumo/state/maobidao) 下的 SQLite、互斥锁及最近回执。
- 正式归档：位于 [archives/maobidao/](/Users/chenge/project/liumo/archives/maobidao) 下的 `<article-key>/<attempt-id>/`，保存自动追更结果。
- 技术样本：[archives/mvp-samples/](/Users/chenge/project/liumo/archives/mvp-samples) ，不混入正式追更状态。
- 手动文章：[archives/manual/](/Users/chenge/project/liumo/archives/manual) ，状态在 [state/manual/](/Users/chenge/project/liumo/state/manual) ，与 RSS 账本独立；元数据为 `archive_kind=manual_page_snapshot`，`complete` 表示当次可见正文与配图齐全。
- 每份 RSS 快照包含 `article.md`、`images/` 和 `metadata.json`，图片使用相对路径与校验值；没有伪造的 `article.png`。

状态、内容、缓存与会话均按 `.gitignore` 留在本机，Git 不包含它们。自动 RSS 运行无需读取 `.auth/`；显式 `save` 仅使用 [.auth/manual-article/](/Users/chenge/project/liumo/.auth/manual-article) 专用会话。公开 RSS 请求只发往 Wechat2RSS；配图按来源明示的腾讯原图地址通过 HTTPS 下载，不把浏览器凭证发送给第三方。

## 调度配置

[本机 plist 模板](/Users/chenge/project/liumo/examples/local.liumo.maobidao.plist) 已按用户确认安装到 [LaunchAgents](/Users/chenge/Library/LaunchAgents/local.liumo.maobidao.plist) 并加载；实际心跳和退出 0、停用／恢复均已验证。当前登录会话内可在后台自动运行，无需保持终端打开。也可生成另一份供审阅：

```bash
.venv/bin/python -m liumo plist --output .tmp/maobidao-mvp/review.plist
```

配置是每分钟的轻量 `tick`；实际是否访问 RSS 由 Python 按 `Asia/Shanghai` 判定，不修改 Mac 时区。后台已完成正式新增文章的 RSS 快照归档，通知使用 Mac 系统通知，无新增时不通知。停用与恢复见 [后台运行说明](/Users/chenge/project/liumo/docs/maobidao-scheduler.md) ，验收与限制统一见 [ROADMAP](/Users/chenge/project/liumo/ROADMAP.md) 。

## 验证

```bash
.venv/bin/python -m tools.check --static-only
.venv/bin/python -m tools.check --suite product
.venv/bin/python -m tools.check --suite browser
.venv/bin/python -m tools.check --suite legacy
.venv/bin/python -m tools.check --suite all
```

检查报告收集、通过、失败及跳过数，分组和完整回归入口见 [开发说明](/Users/chenge/project/liumo/docs/development.md) 。核心测试无需 Chrome／Node／抓包环境；浏览器与历史实验分组使用对应环境。跳过不等于通过。

## 版本管理

日常开发使用 `dev`，通过检查的集成快照同步到 `main`。附注标签 `baseline-20261020` 标识首次工程基线，`mvp-rss-20261021` 标识猫笔刀单号 RSS MVP 结项快照。源码仓库为 [benarchen/liumo](https://github.com/benarchen/liumo) ；版本操作、标签范围与本机数据边界见 [版本管理说明](/Users/chenge/project/liumo/docs/version-control.md) 。Git 只保存代码、文档、脱敏证据与构造样本，不备份真实归档、凭证或运行数据库。

`snapshot-20261022` 保存手动链接归档与当时历史代码的工程快照；`remediation-20261022` 标识后续 G1、G3、G4 整改验收版本。各标签范围和验证边界见版本管理说明，当前功能验收状态以 Roadmap 为准。

[施工与验收记录](/Users/chenge/project/liumo/goal/20261019-2328-maobidao-mvp.md) 、[历史验证工具](/Users/chenge/project/liumo/docs/legacy-validation-commands.md) 。原页诊断迁至显式的 `validation page-sample` 命令，退出默认运行链，不作为当前正常使用步骤。
