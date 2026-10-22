# RSS 历史输入导入

已验证给定 RSS 输入与日期范围的处理能力。它保存 RSS 内容快照，不请求原文、评论或截图；不能证明来源覆盖完整或猫笔刀全年文章齐全。

## 命令与目录

在项目根目录运行，猫笔刀身份预置；其他公众号必须同时指定名称与公开 `--biz`，输入频道和每篇链接均须匹配。

```bash
.venv/bin/python -m liumo history --account 猫笔刀 --start 2026-10-01 --end 2026-10-31 --rss-file /absolute/path/feed.xml --limit 2
.venv/bin/python -m liumo history --account 猫笔刀 --start 2026-10-01 --end 2026-10-31 --resume
```

`--rss-file` 可重复提供；不指定时猫笔刀读取配置中的公开 RSS。`--feed-url` 只接受已允许的公开 Wechat2RSS 地址，与本地文件、`--resume` 互斥。`--limit` 为每次 1 至 100 篇；不是来源覆盖范围。

默认账本在 `state/history/maobidao/`，快照在 `archives/history/maobidao/`；其他号使用公开 biz 的哈希目录。可用 `--data-dir`、`--archive-dir` 指定独立目录。不会改自动追更基线、启用时间、账本或调度。输入、账本和产物均留在 Git 忽略目录。

## 日期与结果

以 RSS pubDate 转为 Asia/Shanghai 后的日期做含首尾筛选。它不是已核实的原文发布时间。缺失／无效时间单列 `unknown_time`；未来时间列 `future_time`，不提前归档，不以首次发现时间代替。

- `maturity=validated_rss_input`：仅指已验收的给定输入处理能力。
- `processing_status=complete`：本次匹配日期范围的已知任务处理完成且文件核验通过。
- `coverage.complete=false`：未有完整来源清单，不证明整段日期或全年无遗漏。
- 总 `status=partial`、退出码 `2`：当前来源覆盖未核实，即使处理已经完成也如此。自动化调用应分别读取处理和覆盖字段；输入拒绝或运行失败也非零退出，原因另列。
- `source_conflicts` 只影响本次匹配范围；`outside_selection_conflicts` 单列其他范围冲突，账本保留这些条目。

整账本 `verify --scope history` 会检查范围外待处理条目和旧尝试，可能报告缺少产物／未索引。单次日期处理完成不能冒充整账本核验全部通过。

## 去重与恢复

全部输入先通过 XML、账号和链接身份验证，才保存输入与任务。重复输入不重复入队；同身份正文、时间或规范链接变化记录冲突，旧输入与快照保留，不擅自决定采用变稿。

每次尝试新目录，产物通过正文、配图和元数据校验后才标 complete。失败自动尝试最多 3 次，之后用 `--retry` 显式重试；访问受限先处理原因，不反复运行。`--resume` 不请求 RSS，仅使用已存输入，但缺失配图仍可能需要公开图片请求。完成快照损坏时普通续跑报告异常，`--retry` 才重新处理；可校验的图片优先复用。中断保留运行状态，后续可恢复。

## 验收与限制

[证据摘要](/Users/chenge/project/liumo/evidence/feasibility/history-import-validation.json) 区分构造测试与真实样本：既有公开 RSS 副本含 20 条，选择 2026-10-17 至 2026-10-18 两篇，生成 Markdown 与 11 条本地图片记录，重复执行没有新归档；正式账本不变。发现微信官方表情静态目录原先未允许，限定路径修复后只补取两张缺图，旧失败快照保留。输入读取来自旧副本，不代表今天的来源窗口或全年覆盖。

日期、身份、全输入验证、跨文件去重／冲突、跨范围报告、重试预算、互斥、中断与 CLI 退出码有构造专项。复现：

```bash
.venv/bin/python -m unittest discover -s tests -p test_history.py -v
```

真实输入使用当前公开来源或自己保留的 RSS 文件；不要用构造输入代替真实覆盖证据。全年任务仍按 [独立清单](/Users/chenge/project/liumo/goals/20261020-2339-rss-history.md) 验收。
