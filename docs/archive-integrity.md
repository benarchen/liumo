# 归档完整性检查与显式修复

`verify` 离线核验账本指向的快照；`repair` 只处理明确指定的一篇。两者与自动追更的 `check`／`retry` 分开，不增加定时扫描，也不重置启用时间或基线。

## 只读检查

在 `/Users/chenge/project/liumo` 运行：

```bash
.venv/bin/python -m liumo verify
.venv/bin/python -m liumo verify --scope rss
.venv/bin/python -m liumo verify --scope manual
.venv/bin/python -m liumo verify --scope history
```

默认 `all` 检查正式 RSS、手动索引，以及 `state/history/`／`archives/history/` 下账号目录的并集；`history` 单独使用时默认猫笔刀。技术样本、旧实验和本次隔离演练目录不计入正式归档。

单一 scope 可用 `--data-dir` 和 `--archive-dir` 选择隔离副本或其他历史账号目录；不要只改其中一个而让副本账本仍指向正式文章。`all` 不接受自定义根目录。命令不会创建数据库、目录或锁，不读取浏览器会话，不下载内容；SQLite 以只读模式打开。

| 字段／状态 | 含义 |
| --- | --- |
| `ledger_status` | 账本记录的任务状态，不能证明文件至今完整 |
| `integrity_status=intact` | 本次检查中身份、类型、正文 SHA-256、本地图片大小／SHA-256 与图片引用一致 |
| `missing` | 账本已有任务但文件或输出位置缺失 |
| `corrupt` | 哈希、身份、类型、图片引用不一致，或路径／体积边界不满足 |
| `unverifiable` | 旧元数据缺字段、非 complete 快照、JSON 损坏或不能读取；不能当完整 |
| `affected_file`／`reasons` | 归档内受影响文件和固定错误类别；不输出原始异常或正文 |
| `unindexed` | 支持的目录布局中未被当前账本引用的尝试，包括保留的旧快照；只列出，不自动入库、删除或宣称已校验 |
| `empty`／`baseline_count` | 没有待核验快照时明确空范围；初始化基线与无需归档条目另计，不冒充已存文章 |

退出码 `0` 表示所检登记快照全部通过，或明确为空；`2` 表示发现问题／未核实／无法检查。只有未索引目录而没有登记快照时也返回 `2`。重复图片引用允许指向同一文件；`checked_files` 按元数据引用计数，不保证等于去重后的文件数。

`status` 保持轻量，返回 `status_basis=task_ledger`、`integrity_checked=false`。本次核验通过也不是备份，不证明原文、评论、截图齐全或之后不会损坏；文件和元数据中的哈希同时被恶意改写不在本地哈希校验的真实性保证范围内。核验是逐份读取，不冻结其他进程的全部归档；若恰遇并发写入造成异常，应待该任务结束后重查。

## 单篇修复

先从 `verify` 输出取得 scope 与 24 位文章 key，再显式运行。以下 `<article-key>` 是占位符，必须替换：

```bash
.venv/bin/python -m liumo repair --scope rss --key <article-key>
.venv/bin/python -m liumo repair --scope manual --key <article-key> --headless
.venv/bin/python -m liumo repair --scope history --key <article-key>
```

- RSS／历史使用对应账本保留的原始输入；只有 HTML 指纹与图片索引映射匹配、图片大小／哈希通过，才复用本地图，否则沿既有 HTTPS 白名单限量获取缺失资源。不会重新拉取 RSS 列表。缺少正文输入或历史来源存在冲突时返回 `unrecoverable`。
- 手动入口复用原有正常浏览器流程，从索引中的公开链接重新读取；缺少可用别名时返回 `unrecoverable`。必须取得与所选 key 相同的文章身份。已有手动元数据没有图片来源映射，不能仅凭图片顺序复用；该路径重新读取可访问原文与配图，可能需要用户正常验证。
- 修复使用与相应写入入口相同的互斥锁。冲突立即返回 `already_running`，不停止后台，不并发写账本。
- 已完整的目标直接复用。需要恢复时创建新的尝试目录，完成元数据落盘并核验后才发布新的账本引用；从不覆盖旧文章、旧配图或旧尝试。
- RSS／历史显式修复的回执在相应状态目录的 `repair-attempts/`。失败或中断保留旧账本引用，回执可能仍是 `running`，这不证明进程仍活着；核对实际进程后可再次执行单篇修复。手动失败尝试由其独立快照元数据记录。
- 回执的 `body_changed` 比较新旧可用 RSS 正文指纹；旧指纹不足时为 `null`。新快照不等于逐字恢复当初原文，尤其手动入口的原文可能已经变化。无可用来源、网络／图片失败或写盘失败都不能提前标完整。
- 修复不会通知、补导基线、推进来源检查位置或改变其他 scope。自动追更的暂停状态不会被修复命令清除；仍需按原有流程处理来源拒绝。

`history --retry` 另已修复：候选筛选前检查已完成快照，显式重试纳入损坏项；无 `--retry` 时只报告损坏。成功结果必须经过实际文件校验；原目录保留，失败后的任务仍可重试。history 的帮助与回执保持 `experimental`，不代表历史模块专项验收或全年来源完整。

## 复现与证据

专项回归均使用隔离样本，不修改正式数据：

```bash
.venv/bin/python -m unittest discover -s tests -p test_integrity.py -v
.venv/bin/python -m unittest discover -s tests -p test_history.py -v
mkdir -p .tmp/wechat-session-validation
LIUMO_BROWSER_TESTS=1 .venv/bin/python -m unittest discover -s tests -v
```

真实演练使用一份本机 RSS 归档的隔离副本和独立 SQLite，故意改变副本 Markdown，执行修复后核对原始 Markdown 哈希与本地图，再重复执行确认复用。它证明真实既有数据可以离线恢复；不代表真实网络恢复、历史全年覆盖、备份或灾难恢复已验收。

演练保留在忽略的 `state/integrity-validation/` 和 `archives/integrity-validation/` 中；具体相对路径、源文件哈希、实际测试结果和代码身份见 [脱敏证据](/Users/chenge/project/liumo/evidence/feasibility/archive-integrity.json) 。施工要求与分项回执见 [G1 清单](/Users/chenge/project/liumo/goals/20261022-2046-p1-p2-remediation.md) 。
