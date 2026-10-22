# 留墨 Roadmap

## 当前状态

- 2026-10-22 23:18：用户授权发布当前整改工程版本，标签采用 remediation-20261022：dev 提交后 main 快进集成，推送两个分支与附注标签。范围与实际引用核对方式见 [版本管理说明](/Users/chenge/project/liumo/docs/version-control.md#2026-10-22-p1p2-整改版本) 。
- 2026-10-22 23:09：G1、G3、G4 均已完成并按当前范围结项，R1／R2／R3／R5／R6／R7 验收通过；G2 已按用户指令移出。给定 RSS 历史处理与全年来源覆盖分别判断。[结项报告](/Users/chenge/project/liumo/docs/p1-p2-remediation-closeout.md) 、[施工回执](/Users/chenge/project/liumo/goals/20261022-2046-p1-p2-remediation.md) 。
- 2026-10-22 20:18：按用户指令准备提交整个 `dev` 工程工作区，包含已验收手动归档和未完成历史导入实现；完整 436 项回归通过、无跳过，公开候选检查通过。集成采用 `main --ff-only`，附注标签为 `snapshot-20261022`；实际提交、推送结果以 Git 引用为准。历史任务不因版本化升级为已完成。[快照范围](/Users/chenge/project/liumo/docs/version-control.md#2026-10-22-工作区快照) 。
- 2026-10-22 08:13：任意公众号链接的独立 `save URL` 已实现并验收，Goal 工具返回 `complete`。用户指定文章猫笔刀《-12%，跌太狠了》真实保存为 6385 字节 Markdown、2 张本地图片，重复命令直接复用。436 项完整回归全部通过、无跳过；自动基线、正式状态计数与既有历史实现保全。使用正常项目浏览器，本次无需人工验证，不包含评论／截图。[用法](/Users/chenge/project/liumo/docs/manual-archive.md) 、[施工验收](/Users/chenge/project/liumo/goals/20261022-0800-manual-url-archive.md) 、[证据](/Users/chenge/project/liumo/evidence/feasibility/manual-url-archive.json) 。
- 2026-10-22 00:08：按用户授权将 MVP 结项材料与历史任务待办说明纳入一次文档提交，`main` 快进集成后创建附注标签 `mvp-rss-20261021`，推送两个分支和标签，最后回到 `dev`。标签日期沿用 2026-10-21 的验收日期；未完成历史导入代码留在本机，提交快照的运行代码／测试／依赖与首次基线相同。[快照验证](/Users/chenge/project/liumo/evidence/feasibility/maobidao-mvp-release.json) 。
- 2026-10-21 23:56：首个 Goal 按用户明确修订的猫笔刀单号 RSS MVP 范围结项，Goal 工具已返回 `complete`；正式新增已自动归档，后台保持运行。最终交付、范围修订与后续边界见 [结项报告](/Users/chenge/project/liumo/docs/maobidao-mvp-closeout.md) 、[施工清单](/Users/chenge/project/liumo/goal/20261019-2328-maobidao-mvp.md) 。
- 2026-10-21 23:54：复核 22:00:05 正式新增《带头大哥肿么了...》，22:00:07 归档完成；5998 字节 Markdown、3 图及哈希／本地引用通过。随后三次检查无重复、无未完成，最近 23:30 来源检查成功；正式归档通知调用成功，测试通知桌面可见性由用户确认。[正式证据](/Users/chenge/project/liumo/evidence/feasibility/maobidao-mvp-closeout.json) 。
- 2026-10-21 23:54：结项工作区完整回归 415 项全部通过、无跳过，耗时 46.725 秒；该工作区包含未提交历史改动，与本次排除历史代码的提交快照分别验收。构造异常、隔离闭环、正式自动归档及用户可见通知证据分别记录，不互相替代。
- 正式启用时间保持 2026-10-19 23:51（北京时间），20 条历史仅作 baseline；截至 2026-10-22 22:29，RSS 已存 2 篇、手动已存 2 篇，本次文件核验均通过。默认运行仍为 RSS 快照，原文时间未核实、评论 not_requested、截图 deferred，不声称原站完整归档。
- 首次 Git 基线为 `66373d8`／`baseline-20261020`，日常分支 `dev`，公开仓库 `benarchen/liumo`。`mvp-rss-20261021` 的历史代码排除范围不变；本轮工作区快照纳入当前工程改动，快照当时历史导入尚未验收；当前给定输入已通过 G3，全年覆盖仍未完成。

## 进行中

- 历史导入：当前实现纳入工作区工程快照，按 [历史归档清单](/Users/chenge/project/liumo/goals/20261020-2339-rss-history.md) 继续验收；未证明猫笔刀 2026 年历史完整，给定输入处理能力已完成 G3 验收；全年完整性仍需独立来源清单。
- 延迟及覆盖：本次用户观察到约一天滞后，尚未分别记录上游首次可见时间与本机等待；来源保留窗口与群发范围有限，不保证当日收齐。持续试用和更及时来源评估保留后续。
- 设备可靠性：休眠／唤醒、物理断网恢复及注销／重登仍未实测，不影响本次用户修订范围结项，不能写成已验证。
- 自动 RSS 原文时间、原页截图、评论与 stormzhang 自动追更：按用户范围暂缓；手动入口可在页面 epoch 与渲染时间相符时单篇核实原文时间。旧原站失败证据保留，不重启旧实验。

## 当前验收快照

| 对象 | 状态 | 证据边界 |
| --- | --- | --- |
| 猫笔刀公开 RSS 多篇发现 | 通过分项 | 真实 20 条及跨两份快照新增 1 条；只覆盖源可见范围 |
| RSS 正文及配图快照 | 通过 | 真实 Markdown、6 张本地配图；不声称对照原站完整 |
| 任意公众号链接手动归档 | 通过当前范围 | 用户指定文章真实 Markdown／2 图及重复复用通过；其他号为构造测试，不承诺全版式或绕过访问限制 |
| 入队、去重、失败与恢复 | 通过 | 真实 RSS 隔离闭环；故障注入、中断、有限重试和保留旧产物回归 |
| 上海四点、合并补查与互斥 | 分项通过 | 四点与锁逻辑、已知失败后自动补查通过；正式夜间新增归档及后续三次检查通过，物理断网及设备唤醒另验 |
| 正式 start_at 后新增文章 | 通过 | 2026-10-21 22:00 自动发现并归档 1 篇，Markdown／3 图校验通过，后续无重复 |
| 后台调度、通知 | 分项通过 | 已加载／自然心跳／停用恢复／夜间 RSS 检查通过，用户确认通知可见；设备行为另验 |
| 给定 RSS 历史输入处理 | 通过 | 18 项专项、两篇真实隔离产物及重复运行通过；来源覆盖未核实，全年任务另验 |
| 工程边界与核心环境 | 通过当前 Mac 范围 | 新核心环境 108 项，分层全量 491 项通过；其他平台未验 |
| 原站截图／RSS 原文时间／评论／第二号自动追更 | 用户暂缓 | 不影响 RSS 快照 complete；手动入口单篇时间核实另有真实证据，不改写历史失败 |

## 下一步执行顺序

1. 首个 RSS MVP 已结项，手动链接归档已交付；保留后台与正式基线继续自动运行，不重新初始化。手动归档不代表已实现跨公众号自动发现。
2. 当前范围内 G1、G3、G4 已全部验收；使用版本化质量入口持续回归，后续 Git 提交与发布按用户指令执行。G2 已移出范围。
3. 历史模块的专项验收与猫笔刀全年历史覆盖分别判定；G3 通过不代表 2026 年文章收齐，全年任务继续保留独立清单及未完成状态。
4. 后续量化上游收录与本机检查延迟，再决定检查窗口或来源变更；设备中断实测独立安排。原页、原文时间、评论及第二号保持暂缓，不重新开展旧微信实验。

## 最近完成

- 2026-10-22 23:18：同步整改工程版本范围、附注标签及公开边界说明；保留 G1／G3／G4 的验收状态与全年覆盖限制，不改运行代码或本机数据。
- 2026-10-22 23:09：G4 完成正式共享模块归属、延迟加载浏览器、依赖分组、新核心环境、分层质量入口及文档收敛；旧诊断迁至 validation page-sample，未改正式数据格式、调度或 Git。[开发说明](/Users/chenge/project/liumo/docs/development.md) 。
- 2026-10-22 22:53：G3 完成日期／身份／冲突／重试／续跑专项，修复跨范围冲突和官方表情路径；两篇真实隔离归档、11 条配图记录及重复去重通过。[用法](/Users/chenge/project/liumo/docs/history-import.md) 。
- 2026-10-22 22:42：按用户指令删除当前整改中的 G2 备份恢复计划、R4 活跃问题及相关依赖；保留 G1 验收，剩余顺序为 G3 → G4。仅调整文档范围，未修改运行代码或归档数据。[清单](/Users/chenge/project/liumo/goals/20261022-2046-p1-p2-remediation.md) 。
- 2026-10-22 22:29：交付 G1 三类只读核验及显式单篇修复，修正历史损坏 complete 被排除、手动索引早于元数据发布的问题；保留旧快照与原账本引用，增加 35 项专项测试，状态及文档同步。没有修复正式数据、安装依赖、改系统或提交 Git。[交付说明](/Users/chenge/project/liumo/docs/archive-integrity.md) 。
- 2026-10-22 20:56：编制 P1／P2 整改清单，逐项对应 7 个问题、4 个 Goal 的依赖、检查点、失败路径、自测、验收及交付文档；明确真实数据保护、后台工作树影响和备份目的地待决条件。仅完成规划，未创建 Goal。[清单](/Users/chenge/project/liumo/goals/20261022-2046-p1-p2-remediation.md) 。
- 2026-10-22 20:18：完成当前工作区提交范围核对与版本说明同步，明确手动链接归档和历史导入代码均纳入 `snapshot-20261022`，保留历史未验收标记；公开范围排除凭证、文章、状态、日志和依赖，无运行代码变更。[版本说明](/Users/chenge/project/liumo/docs/version-control.md) 。
- 2026-10-22 08:10：新增任意公众号 `save URL`，独立会话／索引／归档，输入与页面身份核对、短长链去重、图片失败恢复、刷新保留旧快照及损坏重取齐备。真实指定文章已保存，文档与验收证据同步；不新增依赖，不提交或推送 Git，不修改调度或既有历史代码。[交付](/Users/chenge/project/liumo/docs/manual-archive.md) 。
- 2026-10-22 00:08：明确 MVP 结项提交与附注标签范围，历史导入计划以未交付状态版本化，4 份未完成程序留在本机。补齐完整历史测试的空临时目录准备说明，区分工作区证据与独立 Git 快照验证。[版本说明](/Users/chenge/project/liumo/docs/version-control.md) 。
- 2026-10-21 23:54：按用户指令完成 RSS MVP 结项验收、正式自动归档证据和当前文档同步；后台继续运行，历史导入和设备可靠性独立保留后续。[结项报告](/Users/chenge/project/liumo/docs/maobidao-mvp-closeout.md) 。
- 2026-10-20 23:31：新增 Git 分支／基线及公开同步约定，提交排除凭证、文章、日志、依赖和状态；同步用户确认的通知可见性及 23:30 无新增检查。首次工程基线范围与限制见 [说明](/Users/chenge/project/liumo/docs/version-control.md) 。
- 2026-10-20 21:04：按用户指令安装专用 LaunchAgent，加载、自然心跳、停用／恢复和通知提交完成；21:03 自动 RSS 补查成功，退避清除。没有修改其他任务、系统时区、代理或证书。[运行与恢复](/Users/chenge/project/liumo/docs/maobidao-scheduler.md) 。
- 2026-10-20 08:01：完成 RSS MVP 总证据、样本文件／配图哈希、正式基线隔离及文档交付核对；可手动运行核心，未安装系统后台。[交付说明](/Users/chenge/project/liumo/docs/maobidao-mvp.md) 。
- 2026-10-19 23:55：交付单号 RSS MVP、真实快照及 6 张配图，隔离真实入队归档／重复检查通过，正式 20 篇基线已初始化；原页截图与原文时间按用户决定暂缓。[交付](/Users/chenge/project/liumo/docs/maobidao-mvp.md) 。

- 2026-10-19 22:22：完成正常微信读书首页两号搜索核对，保存 DOM 摘要和 stormzhang 结果提示裁剪图，正常关闭项目窗口；来源关口仍未通过。[记录](/Users/chenge/project/liumo/docs/weread-discovery-validation.md) 。
- 2026-10-19 22:09：交付自动会话观察，免终端 Enter；正式授权环境与两号初次来源核对已执行，受限后停止；公开猫笔刀 RSS 多篇核对及单个备选限制审阅完成。没有完整来源通过或购买部署。[交付](/Users/chenge/project/liumo/docs/weread-discovery-validation.md) 。

- 2026-10-19 21:54：交付 V1 来源请求审阅入口与解析／扫描修复、13 项专项测试和复现说明。未新增依赖、读取凭证或发微信接口请求；来源／截图关口未通过。[交付](/Users/chenge/project/liumo/docs/weread-discovery-validation.md) 。

- 2026-10-19 21:42：作废项目附加重复审批条款，精简 AGENTS 并保留历史存档，同步 README 和 V1 清单；运行代码、用户配置、凭证、系统设置与 Goal 生命周期均未改。[说明](/Users/chenge/project/liumo/docs/execution-permissions.md) 。

- 2026-10-19 21:25：完成 Workbuddy 路线评审及 V1 范围同步，按用户指定新增 goal/ 施工清单；停止评论系统实验主线，未改运行代码、未发微信请求，来源与整图仍待验。[评审](/Users/chenge/project/liumo/docs/route-review-20261019.md) 、[施工清单](/Users/chenge/project/liumo/goal/20261019-2121-v1-auto-follow.md) 。

- 2026-10-19 08:06：离线容量复核交付：55 段构造 JS、3493944／4194304 字节在 20 万节点均失败，候选 8388608 上限各完成，耗时 0.677／0.788 秒、退出 0；源码／超时／old-space 边界保持，运行时上限未改。RSS 计量因 sysctl 权限不可用，明确未验证；真实脚本容量及评论仍未知。新增可复现构造程序，完整回归 355 项为 351 通过、4 跳过。建议下一轮受控保留一份本机私有 HTML，扩大仅内存范围需用户决策，尚未实现或创建新授权／目录。[对比证据](/Users/chenge/project/liumo/evidence/feasibility/parser-capacity.json) 、[待决方案](/Users/chenge/project/liumo/docs/inline-script-validation.md#下一轮证据保留方式待用户决策) 。


## 最近验证

- 2026-10-22 23:18：提交前获取远端后 main／dev 均无分叉；22 份实现／测试／依赖哈希与 491 项通过证据一致。238 份工程候选无受保护路径、强特征秘密扫描无命中，8 类忽略路径核对通过；文档与 diff 检查通过。
- 2026-10-22 23:09：最终质量入口 491 项全部通过、无跳过，45.077 秒：产品 108／浏览器 11／旧实验 372。新核心 venv 108 项及 pip check 通过；正式 RSS 2 篇、手动 2 篇只读 intact；17 个共享函数 AST 及构造输出兼容，语法／导入边界／文档和 diff 检查通过。[证据](/Users/chenge/project/liumo/evidence/feasibility/engineering-consolidation.json) 。
- 2026-10-22 22:53：G3 专项 18 项、完整回归 484 项通过，无跳过，44.668 秒；两篇选中快照 intact，整账本含范围外待办仍为 partial。正式账本未改。
- 2026-10-22 22:42：范围调整文档检查：保留 3 个 Goal、17 个检查点（G1 已完成 6 个）；本地链接、锚点、Markdown 结构、Roadmap 记录顺序与上限、G1 的 8 份实现／测试哈希及 `git diff --check` 核对通过。仅文档变更，未重跑产品测试。
- 2026-10-22 22:35：G1 交付核对：8 份实现／测试哈希与证据一致，真实隔离副本 CLI verify 和幂等 repair 均退出 0；6 份文档、135 个本地链接、5 个锚点及 Roadmap 记录规则通过，`git diff --check` 通过。六个检查点验收齐全，G2～G4 不随之关闭。[回执](/Users/chenge/project/liumo/goals/20261022-2046-p1-p2-remediation.md#g1-验收回执) 。
- 2026-10-22 22:29：G1 完整回归 471 项通过、无跳过，45.249 秒；随后仅补充子命令帮助文字，30 项完整性专项再次通过，历史专项 5 项通过。真实 RSS 2 篇、手动 2 篇只读核验 intact；RSS 副本损坏检出后零网络恢复、3 图复用、正文哈希还原、重复复用，正式文件与数据库不变。历史与新网络恢复证据边界单列。[证据](/Users/chenge/project/liumo/evidence/feasibility/archive-integrity.json) 。
- 2026-10-22 20:56：整改清单与 Roadmap 的标题／代码块、70 个本地链接及锚点、7 项问题映射、4 个 Goal 与 22 个检查点核对通过；最近记录倒序及各最多 20 条、`git diff --check` 通过。本轮仅文档检查，未运行产品测试，不新增功能通过结论。
- 2026-10-22 20:18：提交前完整回归 436 项全部通过、无跳过，46.338 秒；候选源码／文档强特征秘密扫描无命中，8 类本机敏感路径忽略核对通过；获取远端后 main／dev 均无分叉。不将通用回归视为历史导入功能已验收。
- 2026-10-22 08:10：用户短链正常 Chrome 真实读取与滚动到底通过，文章身份及原文时间核对、6385 字节 Markdown、2 图 SHA-256／PNG 尺寸／本地引用通过，重复命令退出 0 并复用。17 项逻辑、4 项本地浏览器专项通过；完整 436 项全部通过、无跳过，43.824 秒。历史 3 个独立文件哈希保持，主入口仅追加 save，正式基线和状态计数未变。[证据](/Users/chenge/project/liumo/evidence/feasibility/manual-url-archive.json) 。
- 2026-10-22 07:54：指定短链一次匿名 HTTPS GET 被 302 重定向门槛停止；一次不跟随 HEAD 记录验证页类别，curl 92 独立保留，未推断 GET 目标完全相同或必须登录。0 篇正文／0 张图片；4 份历史程序哈希保全，脱敏 JSON 和文档链接核对，无产品代码变更。[证据](/Users/chenge/project/liumo/evidence/feasibility/manual-article-link.json) 。
- 2026-10-22 00:08：从 Git 暂存区导出的独立提交快照完整回归 415 项全部通过、无跳过，43.454 秒；运行代码／测试／依赖与 `66373d8` 相同，未导出历史实现。首轮 4 项因缺少历史测试临时父目录失败，补建快照内空目录后复测通过，复现说明已同步；不改业务代码。[快照验证](/Users/chenge/project/liumo/evidence/feasibility/maobidao-mvp-release.json) 。
- 2026-10-21 23:54：完整回归 415 项全部通过、无跳过，46.725 秒；正式文章 Markdown／3 图哈希、本地引用、一次后台归档和随后三次无重复检查通过，安装配置与模板一致。保留既有 6 份历史导入文件身份，结项不改代码或系统。[正式验收证据](/Users/chenge/project/liumo/evidence/feasibility/maobidao-mvp-closeout.json) 。
- 2026-10-20 23:31：显式启用本地浏览器完整回归，415 项全部通过、无跳过，耗时 43.516 秒。沙盒首轮阻止浏览器／回环，未计为通过；经正式权限门禁后完成，不访问微信、不改运行代码。[基线验证](/Users/chenge/project/liumo/evidence/feasibility/git-baseline.json) 。
- 2026-10-20 21:04：系统实测：安装前无同名任务／配置，bootstrap／bootout／恢复均退出 0，后续日历运行和日志计数增长；21:03 后台读取 RSS 20 条、0 新增／0 未完成，退出 0、stderr 空。代码哈希仍与 415 项回归一致；夜间四点、正式新增、设备行为和通知可见性未代验。[证据](/Users/chenge/project/liumo/evidence/feasibility/maobidao-launchd.json) 。
- 2026-10-20 08:01：07:59 真实正式 check 无新增，状态仅 20 条 baseline；真实样本／6 图与隔离闭环哈希通过。8 份 Markdown、155 个本地链接、10 个章节锚点、Roadmap 顺序与 plist 通过，代码与 415 项完整回归版本一致；不因仅文档整理重复旧网络／浏览器实验。[证据](/Users/chenge/project/liumo/evidence/feasibility/maobidao-mvp.json) 。
- 2026-10-19 23:55：完整 415 项全部通过，无跳过；真实 RSS 隔离闭环新增 1、归档 1，重复执行新增 0／归档 0，6 张配图本地齐全；正式 check 为 20 条基线／0 新增、tick idle。原页访问未通过，截图及原文时间暂缓。[证据](/Users/chenge/project/liumo/evidence/feasibility/maobidao-mvp.json) 。

- 2026-10-19 22:22：真实正常网页操作：猫笔刀显示「电子书」及全文提及书籍 1210，stormzhang 显示全文提及书籍 2；这些不是文章数。未进入两号文章列表，无多篇／翻页通过证据。未改产品代码，不重复旧完整回归。[证据](/Users/chenge/project/liumo/evidence/feasibility/weread-normal-pages.json) 。
- 2026-10-19 22:09：完整 372 项为 368 通过、4 跳过；正式授权 HTTPS 200／TLS 0 及无账号 Chrome 本地渲染通过。两号首轮各 -2012，会话变化后猫笔刀 -2041，共 3 次列表／0 篇；公开猫笔刀 RSS 20 个不同原链接，时间／覆盖未验。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/v1-source-live.json) 。

- 2026-10-19 21:54：完整回归 368 项为 364 通过、4 跳过，13 项新增来源回归通过；weread-plan 离线输出两号候选及请求边界。一次标准提权申请在执行前被策略拒绝，不算连通性测试；未重复旧系统实验。[证据](/Users/chenge/project/liumo/evidence/feasibility/weread-discovery-preparation.json) 。

- 2026-10-19 21:42：权限能力核对：工作区读写通过；无凭证公开 HEAD 两站均 curl 6／HTTP 0，回环绑定 errno 1，隔离浏览器 TargetClosedError；CLI 0.163.0，用户配置已有 auto_review。未取得账号／微信接口通过证据，不把 TLS 数值 0 当握手成功；文档结构、链接及记录顺序检查通过。[证据](/Users/chenge/project/liumo/evidence/feasibility/permission-policy-update.json) 。
