# 留墨 liumo

当前提供猫笔刀单号的 **RSS 内容快照归档**：读取公开 RSS，保存 Markdown、本地配图、公开原链接和元数据；有去重、失败恢复、上海时区门控及本机通知出口。默认运行不打开微信原文、不使用账号会话、不读取评论。

`complete` 表示 RSS 快照产物齐全。原文发布时间仍待核实，原页截图暂缓；不能解释为已对照原站完整归档。新内容按启用后的首次发现处理，初始化时列表中的文章只建立基线。详细状态见 [ROADMAP](/Users/chenge/project/liumo/ROADMAP.md) ，运行与恢复说明见 [MVP 使用说明](/Users/chenge/project/liumo/docs/maobidao-mvp.md) 。

## 使用

在 `/Users/chenge/project/liumo` 运行，沿用项目 `.venv/` 和现有依赖：

```bash
.venv/bin/python -m liumo --help
.venv/bin/python -m liumo status
.venv/bin/python -m liumo check
.venv/bin/python -m liumo tick
```

- `check` 立即检查 RSS，串行处理最多 3 篇待处理文章；可用 `--limit 1` 至 `--limit 5` 调整本次预算。
- `tick` 只在北京时间 22:00、22:30、23:00、23:30 到期或需要恢复补查时执行，错过多次合并。普通空闲心跳不请求 RSS。
- `status` 查看启用时间、成功检查、任务与人工处理项；未初始化返回 `not_initialized`，不创建空数据库。
- `retry` 有限处理未完成任务，包含已用尽自动次数的任务。访问／来源拒绝时先检查原因，不盲目循环执行。

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
- 每份 RSS 快照包含 `article.md`、`images/` 和 `metadata.json`，图片使用相对路径与校验值；没有伪造的 `article.png`。

状态、内容、缓存与会话均按 `.gitignore` 留在本机，Git 不包含它们。运行无需读取 `.auth/`。公开 RSS 请求只发往 Wechat2RSS；配图按 RSS 明示的腾讯原图地址通过 HTTPS 下载，不把浏览器凭证发送给第三方。

## 调度配置

[本机 plist 模板](/Users/chenge/project/liumo/examples/local.liumo.maobidao.plist) 已按用户确认安装到 [LaunchAgents](/Users/chenge/Library/LaunchAgents/local.liumo.maobidao.plist) 并加载；实际心跳和退出 0、停用／恢复均已验证。当前登录会话内可在后台自动运行，无需保持终端打开。也可生成另一份供审阅：

```bash
.venv/bin/python -m liumo plist --output .tmp/maobidao-mvp/review.plist
```

配置是每分钟的轻量 `tick`；实际是否访问 RSS 由 Python 按 `Asia/Shanghai` 判定，不修改 Mac 时区。后台已完成正式新增文章的 RSS 快照归档，通知使用 Mac 系统通知，无新增时不通知。停用与恢复见 [后台运行说明](/Users/chenge/project/liumo/docs/maobidao-scheduler.md) ，验收与限制统一见 [ROADMAP](/Users/chenge/project/liumo/ROADMAP.md) 。

## 验证

```bash
mkdir -p .tmp/wechat-session-validation
.venv/bin/python -m unittest discover -s tests -v
LIUMO_BROWSER_TESTS=1 .venv/bin/python -m unittest discover -s tests -v
```

首行准备历史组件测试使用的空临时父目录，不包含账号或运行数据。后一入口显式运行本地构造页面测试，不访问微信原文。RSS MVP 默认不需要启动浏览器；完整历史回归仍使用现有 Chrome／Node／Acorn。依赖清单见 [requirements.txt](/Users/chenge/project/liumo/requirements.txt) 。

## 版本管理

日常开发使用 `dev`，通过检查的集成快照同步到 `main`。附注标签 `baseline-20261020` 标识首次工程基线，`mvp-rss-20261021` 标识猫笔刀单号 RSS MVP 结项快照。源码仓库为 [benarchen/liumo](https://github.com/benarchen/liumo) ；版本操作、标签范围与本机数据边界见 [版本管理说明](/Users/chenge/project/liumo/docs/version-control.md) 。Git 只保存代码、文档、脱敏证据与构造样本，不备份真实归档、凭证或运行数据库。

[施工与验收记录](/Users/chenge/project/liumo/goal/20261019-2328-maobidao-mvp.md) 、[历史验证工具](/Users/chenge/project/liumo/docs/legacy-validation-commands.md) 。原页诊断保留为显式的 `page-sample` 命令，退出默认运行链，不作为当前正常使用步骤。
