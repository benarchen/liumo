# 猫笔刀 RSS MVP 使用与验收

当前交付的是猫笔刀单号 RSS 内容快照版，支持手动与已安装后台自动运行；实际夜间新增归档、后续去重及停用／恢复通过，用户已要求按该范围结项。用户明确接受暂缓原页截图及原文发布时间核实，不依赖微信读书、微信扫码或本机微信凭证。长期可靠性与设备行为保留后续观察。

## 内容与时间语义

公开源：[Wechat2RSS 猫笔刀 RSS](https://wechat2rss.xlab.app/feed/33d986064f59be5263de2ca822fb3e0bdd59eb81.xml) 。解析 `content:encoded`，没有时才使用 description；不执行文章脚本，清理脚本、表单和明确隐藏节点。正文仍来自第三方 RSS，不能保证与原文完全一致或无截断。

配图代理在本轮未下载成功；没有将失败唯一归因于权限或代理失效。代码改为从 RSS 图片 URL 中明确携带的 `u` 提取 HTTPS 腾讯原图地址，校验 qpic／qlogo 主机后直接下载，不做失败后切换或隐式回退。真实样本 6 张图片全部下载，按内容校验值保存。本机账号 Cookie、图片代理参数及凭证不参与请求认证。

- 原文公开链接、账号与 biz／mid／idx 从固定单号源核对；这些属于 RSS 身份核对，不是原站身份验收。
- `feed_time_candidate` 只保留 RSS 时间，`original_publication_time=null`、`publication_time_verified=false`。
- 初始化时先取得当前列表，再记录 start_at，当前已有的 20 篇只建 baseline，不下载正文产物或配图。
- 后续第一次出现在列表的候选记录真实 first_seen_at，再保存 RSS 快照。上游晚到的旧发布可能被暂存；不会把首次发现时间冒充原文发布时间。
- `comments_status=not_requested`，截图 `deferred`；没有伪造的原页图。当前 `complete` 只表示 RSS 提供的正文已转换、配图齐全及元数据落盘。

## 运行入口

在 `/Users/chenge/project/liumo` 使用现有 `.venv/`：

```bash
.venv/bin/python -m liumo status
.venv/bin/python -m liumo check
.venv/bin/python -m liumo retry --limit 1
.venv/bin/python -m liumo tick
```

本机已于北京时间 2026-10-19 23:51 初始化正式状态：[state/maobidao/](/Users/chenge/project/liumo/state/maobidao) 。`check` 实测为 20 条基线、0 新增、0 归档，`tick` 在非到期时返回 idle。此空跑只证明入口／基线／门控工作，不能当作正式启用后新增文章归档通过。

2026-10-20 07:59 再次实际 check 仍为 20 条源记录、0 新增／0 归档，正式库没有技术样本或失败任务。用户无需重新初始化、扫码或手工刷新微信。

`source` 查看列表摘要，不打印正文 HTML；`sample` 保存一篇技术样本到独立目录。未初始化时才使用 `init`；重复初始化拒绝覆盖。所有命令的 `--data-dir` 放在子命令之后；日常使用省略该选项。正式运行不依赖 `.tmp/`。

## 状态与失败恢复

候选及来源正文先提交 SQLite，再归档。每个任务有独立状态、尝试次数与产物目录；程序被打断后 running 任务可以继续，图片／写盘等失败默认最多自动处理 3 次。后续发现位置前进或文章滑出 RSS 窗口不删除已有候选；需要人工处理的任务继续显示，不能当作无更新。

- `baseline`：启用时已有条目，不自动补历史。
- `pending`／`running`：待处理或上次中断。
- `complete`：当前 RSS 快照齐全，原站核实和截图仍暂缓。
- `partial`／`failed`：保留已生成成果，后续有限重试；每次新目录，旧结果不覆盖。
- `blocked` 或来源格式／身份拒绝：暂停，需要检查证据后显式 retry，不换账号或传输绕过。

来源正文／标题／链接变化会提示 `source_metadata_changed`，既有快照和首次候选不被静默覆盖；当前不自动生成改稿版本。前后列表完全无重叠时提示 `feed_window_gap_possible`，有重叠也不保证原服务从未漏文。当前窗口实测为 20 条；服务范围与延迟见 [官方说明](https://wechat2rss.xlab.app/deploy/qa) ，不承诺永久补齐。

## 调度与通知

[plist 模板](/Users/chenge/project/liumo/examples/local.liumo.maobidao.plist) 每分钟调用一次轻量 tick，由 Python 计算上海时间的四个点；重叠运行共用非阻塞锁。错过多次时合并一次，来源网络／服务失败按 15 分钟至最多 6 小时退避；退避未到期不请求 RSS，恢复后允许窗口外补查。设备实际恢复的响应速度受退避及每分钟心跳影响。

配置已安装并 bootstrap 到当前用户域，后台空闲心跳、停用与重新加载通过，没有修改系统时区。2026-10-21 夜间正式新增归档成功，后续检查无重复；实际休眠、唤醒和重登仍未验收。通知使用既有本机 sender，错误不回滚归档；测试通知桌面可见性已有用户确认，正式归档通知调用成功。操作与最新恢复记录见 [后台运行说明](/Users/chenge/project/liumo/docs/maobidao-scheduler.md) 。未来微信提醒可接同一函数出口，当前没有实现。

2026-10-20 21:03 自然后台补查成功：读取 20 条 RSS、0 新增／0 未完成，安装前的失败退避已清除。没有手动检查替代，正式启用时间和基线保持不变；这不等于正式新增或夜间时点已通过。

## 本轮证据

- [真实样本《撒钱100亿》](/Users/chenge/project/liumo/archives/mvp-samples/20261019T155011296684Z/article.md) ：6473 字节 Markdown、6 张本地配图，标记为 RSS 快照。
- [真实 RSS 到队列再到归档的隔离闭环](/Users/chenge/project/liumo/evidence/feasibility/maobidao-rss-roundtrip.json) ：以早前真实列表作技术基线，当前真实列表发现 1 篇，默认 RSS 归档完成；重复执行 0 新增／0 重复归档，重开状态库保留结果。验收 start_at 为构造边界，不改正式启用时间，不冒充正式启用后新增。
- [此前 RSS 两份列表增量核对](/Users/chenge/project/liumo/evidence/feasibility/maobidao-rss-increment.json) 只证明真实列表差异及本地入队，不追溯改成原站通过。
- [本轮总证据](/Users/chenge/project/liumo/evidence/feasibility/maobidao-mvp.json) 汇总代码与产物校验值、正式基线、失败尝试和回归结果。

用户已明确按猫笔刀单号 RSS MVP 范围结项；正式启用后的实际新增文章、后台归档和后续去重已验收，见 [结项报告](/Users/chenge/project/liumo/docs/maobidao-mvp-closeout.md) 。长期服务稳定性、设备行为和项目外备份恢复保留后续；旧原站失败及验证异常反馈不改为通过，没有新增原站时间／截图通过事实。
