# 留墨 Roadmap

## 当前状态

- 2026-10-22 00:08：按用户授权将 MVP 结项材料与历史任务待办说明纳入一次文档提交，`main` 快进集成后创建附注标签 `mvp-rss-20261021`，推送两个分支和标签，最后回到 `dev`。标签日期沿用 2026-10-21 的验收日期；未完成历史导入代码留在本机，提交快照的运行代码／测试／依赖与首次基线相同。[快照验证](/Users/chenge/project/liumo/evidence/feasibility/maobidao-mvp-release.json) 。
- 2026-10-21 23:56：首个 Goal 按用户明确修订的猫笔刀单号 RSS MVP 范围结项，Goal 工具已返回 `complete`；正式新增已自动归档，后台保持运行。最终交付、范围修订与后续边界见 [结项报告](/Users/chenge/project/liumo/docs/maobidao-mvp-closeout.md) 、[施工清单](/Users/chenge/project/liumo/goal/20261019-2328-maobidao-mvp.md) 。
- 2026-10-21 23:54：复核 22:00:05 正式新增《带头大哥肿么了...》，22:00:07 归档完成；5998 字节 Markdown、3 图及哈希／本地引用通过。随后三次检查无重复、无未完成，最近 23:30 来源检查成功；正式归档通知调用成功，测试通知桌面可见性由用户确认。[正式证据](/Users/chenge/project/liumo/evidence/feasibility/maobidao-mvp-closeout.json) 。
- 2026-10-21 23:54：结项工作区完整回归 415 项全部通过、无跳过，耗时 46.725 秒；该工作区包含未提交历史改动，与本次排除历史代码的提交快照分别验收。构造异常、隔离闭环、正式自动归档及用户可见通知证据分别记录，不互相替代。
- 正式启用时间保持 2026-10-19 23:51（北京时间），20 条历史仅作 baseline，新增已 complete 1 篇。默认运行仍为 RSS 快照，原文时间未核实、评论 not_requested、截图 deferred，不声称原站完整归档。
- 首次 Git 基线为 `66373d8`／`baseline-20261020`，本地日常分支 `dev`，公开仓库 `benarchen/liumo`。本次仅提交结项文档、脱敏证据及必要待办说明，历史导入工作树代码改动保持原样，未标完成；不改系统设置或重启后台。

## 进行中

- 历史导入：已有未完成的工作树实现及 [历史归档清单](/Users/chenge/project/liumo/goals/20261020-2339-rss-history.md) ，不纳入本次结项；未证明猫笔刀 2026 年历史完整，也未把相关功能标为已交付。
- 延迟及覆盖：本次用户观察到约一天滞后，尚未分别记录上游首次可见时间与本机等待；来源保留窗口与群发范围有限，不保证当日收齐。持续试用和更及时来源评估保留后续。
- 设备可靠性：休眠／唤醒、物理断网恢复及注销／重登仍未实测，不影响本次用户修订范围结项，不能写成已验证。
- 备份恢复：本机 SQLite 重开与失败恢复已验证；项目外备份目标、恢复和长期保全仍待后续处理。
- 原文时间、原页截图、评论与 stormzhang：按用户最新范围暂缓，退出当前 MVP 门槛；原站访问失败记录保留，不继续实验。

## 当前验收快照

| 对象 | 状态 | 证据边界 |
| --- | --- | --- |
| 猫笔刀公开 RSS 多篇发现 | 通过分项 | 真实 20 条及跨两份快照新增 1 条；只覆盖源可见范围 |
| RSS 正文及配图快照 | 通过 | 真实 Markdown、6 张本地配图；不声称对照原站完整 |
| 入队、去重、失败与恢复 | 通过 | 真实 RSS 隔离闭环；故障注入、中断、有限重试和保留旧产物回归 |
| 上海四点、合并补查与互斥 | 分项通过 | 四点与锁逻辑、已知失败后自动补查通过；正式夜间新增归档及后续三次检查通过，物理断网及设备唤醒另验 |
| 正式 start_at 后新增文章 | 通过 | 2026-10-21 22:00 自动发现并归档 1 篇，Markdown／3 图校验通过，后续无重复 |
| 后台调度、通知、外部备份 | 分项通过 | 已加载／自然心跳／停用恢复／夜间 RSS 检查通过，用户确认通知可见；设备行为及数据备份另验 |
| 原站截图／发布时间／评论／第二号 | 用户暂缓 | 不影响当前 RSS 快照 complete，不改写历史失败 |

## 下一步执行顺序

1. 首个 Goal 已完成，保留后台与正式基线继续自动运行，不重新初始化。
2. 历史导入按独立清单继续核对来源覆盖、未完成实现与必要测试，不能承接本次结项声明为历史任务完成。
3. 后续优先量化上游收录与本机检查延迟，再决定检查窗口或来源变更；设备中断实验、备份目标按对应授权执行。
4. 原页、原文时间、评论及第二号保持暂缓，不重新开展旧微信实验。

## 最近完成

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

- 2026-10-19 08:00：C28 已关闭：HTTP 200／gzip，789880 字节编码／3493944 字节解码 HTML，独立文章身份通过；53 段经典 JS／2 段 module／2 条外部来源，外部均为 known_host_path_rejected。AST 触发本地累计 200000 节点上限，调用计数未保留，整体 partial，不能推断评论通道。14.705 秒内四项恢复通过，公共材料身份／私钥不存在／0600 摘要／旧十三次回执另验；授权已消耗，不重跑。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/html-inline-live.json) 。

- 2026-10-19 07:57：C28 本次授权已排他记录并绑定已恢复 C26；旧十三次关闭哈希及 71 份源码／配置对应的 355 项基线核对通过。用户确认文章前置／聊天隐藏，Agent 截图核对及 300 秒 UI 就绪已完成；系统只读预检仍返回 preflight_system_authorization_unavailable，尚未创建真实目录、改系统、刷新或读取 HTML，待普通终端启动本次入口，无需再次授权。原 Goal 未完成。[现场记录](/Users/chenge/project/liumo/evidence/feasibility/html-inline-live.json) 。

- 2026-10-19 07:53：C28 HTML 内联分析准备交付：独立身份后才启动 Acorn，输出语法形状／类型覆盖与外部来源固定类别，不下载外部脚本、不保存原文；新增本次代理／Node 进程组收尾门槛。14 项专项通过，完整 355 项为 351 通过、4 跳过；实际本机 Python／Node 构造进程组退出已验证，不替代微信系统恢复。旧十三次关闭及 C26 回执保全，新授权／UI／真实目录均未创建，等待本次具体系统授权；原 Goal 未完成。[范围与命令](/Users/chenge/project/liumo/docs/inline-script-validation.md#c28一次-html-内存连接实验) 、[准备证据](/Users/chenge/project/liumo/evidence/feasibility/html-inline-preparation.json) 。

- 2026-10-19 07:39：C27 离线 JS 分析准备通过：普通终端安装 Acorn 8.19.0 后，缓存包 SHA-512／lockfile 及 10 个安装文件逐一核对；语法分析辅助程序和受限 Python 包装交付。12 项构造专项通过，完整 341 项为 337 通过、4 跳过；仅输出固定计数，不执行输入。真实 HTML 连接／评论通道未验，无新微信或系统实验，C26 旧回执保全，原 Goal 未完成。[实现与复现](/Users/chenge/project/liumo/docs/inline-script-validation.md) 、[证据](/Users/chenge/project/liumo/evidence/feasibility/inline-script-preparation.json) 。

- 2026-10-19 00:35：C26 已关闭：HTTP 200／gzip、两条 Content-Type 完整归一化等价，789852 字节编码／3493845 字节解码 HTML，独立文章身份通过。57 个 script、2 个外部来源均被拒绝，无可用公共脚本地址；固定词频不足以证明调用关系，静态取证整体 partial，评论及完整归档未通过。16.313 秒内四项恢复通过，公共材料身份、私钥不存在及 C25 回执另验；63 份代码与 329 项基线一致，未重复测试。原 Goal 服务仍 blocked、未完成。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/article-static-duplicates-live.json) 。

- 2026-10-19 00:20：C24／C25 连续头部失败后，已复核 RFC 9110、官方 API 与锁定 mitmproxy 源码／构造双头，确认计数为独立字段。C26 仅对完整归一化声明一致的双头继续，其余停止；329 项为 325 通过、4 跳过，63 份 AST、旧回执及新授权拒绝核对。新授权／UI／目录未创建，无新系统或微信请求；真实 HTML／评论通道及原 Goal 未完成，服务 blocked。[准备与方案](/Users/chenge/project/liumo/evidence/feasibility/article-static-duplicates-preparation.json) 。

- 2026-10-19 00:20：C25 已关闭：控制 HTTP 200／各 1、匹配文章响应 1 次；实测 HTTP 200／gzip／两条 Content-Type，按 ambiguous 拒绝，未读 HTML 或生成静态摘要。15.664 秒内四项恢复通过，公共材料身份、私钥不存在及 C24 旧回执另验；两条值未留存，不知是否一致或冲突，不重跑。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/article-static-metadata-live.json) 。

- 2026-10-19 00:10：C25 本次授权已记录并绑定已恢复 C24，旧十一次关闭回执及 61 份代码的 321 项基线核对通过。固定文章 UI 已截图确认、聊天隐藏，300 秒就绪记录已创建；Agent 系统预检仍权限不可用。尚未创建实验目录、改系统、刷新或读取 HTML，待普通终端启动，无需重复授权；C24 私有回执不变，原 Goal 仍 blocked、未完成。[现场记录](/Users/chenge/project/liumo/evidence/feasibility/article-static-metadata-live.json) 。

## 最近验证

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

- 2026-10-19 21:28：V1 路线文档检查通过：6 份 Markdown 的结构、绝对本地链接、施工清单目标／边界／自测／验收／交付项、Roadmap 倒序与各最多 20 条记录及来源索引 JSON；仅文档改动，不重复旧 355 项回归，不新增真实微信验证。[检查与来源证据](/Users/chenge/project/liumo/evidence/feasibility/route-review-20261019.json) 。

- 2026-10-19 08:06：离线容量复核交付：55 段构造 JS、3493944／4194304 字节在 20 万节点均失败，候选 8388608 上限各完成，耗时 0.677／0.788 秒、退出 0；源码／超时／old-space 边界保持，运行时上限未改。RSS 计量因 sysctl 权限不可用，明确未验证；真实脚本容量及评论仍未知。新增可复现构造程序，完整回归 355 项为 351 通过、4 跳过。建议下一轮受控保留一份本机私有 HTML，扩大仅内存范围需用户决策，尚未实现或创建新授权／目录。[对比证据](/Users/chenge/project/liumo/evidence/feasibility/parser-capacity.json) 、[待决方案](/Users/chenge/project/liumo/docs/inline-script-validation.md#下一轮证据保留方式待用户决策) 。

- 2026-10-19 08:00：C28 已关闭：HTTP 200／gzip，789880 字节编码／3493944 字节解码 HTML，独立文章身份通过；53 段经典 JS／2 段 module／2 条外部来源，外部均为 known_host_path_rejected。AST 触发本地累计 200000 节点上限，调用计数未保留，整体 partial，不能推断评论通道。14.705 秒内四项恢复通过，公共材料身份／私钥不存在／0600 摘要／旧十三次回执另验；授权已消耗，不重跑。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/html-inline-live.json) 。

- 2026-10-19 07:57：C28 本次授权已排他记录并绑定已恢复 C26；旧十三次关闭哈希及 71 份源码／配置对应的 355 项基线核对通过。用户确认文章前置／聊天隐藏，Agent 截图核对及 300 秒 UI 就绪已完成；系统只读预检仍返回 preflight_system_authorization_unavailable，尚未创建真实目录、改系统、刷新或读取 HTML，待普通终端启动本次入口，无需再次授权。原 Goal 未完成。[现场记录](/Users/chenge/project/liumo/evidence/feasibility/html-inline-live.json) 。

- 2026-10-19 07:53：C28 HTML 内联分析准备交付：独立身份后才启动 Acorn，输出语法形状／类型覆盖与外部来源固定类别，不下载外部脚本、不保存原文；新增本次代理／Node 进程组收尾门槛。14 项专项通过，完整 355 项为 351 通过、4 跳过；实际本机 Python／Node 构造进程组退出已验证，不替代微信系统恢复。旧十三次关闭及 C26 回执保全，新授权／UI／真实目录均未创建，等待本次具体系统授权；原 Goal 未完成。[范围与命令](/Users/chenge/project/liumo/docs/inline-script-validation.md#c28一次-html-内存连接实验) 、[准备证据](/Users/chenge/project/liumo/evidence/feasibility/html-inline-preparation.json) 。

- 2026-10-19 07:39：C27 离线 JS 分析准备通过：普通终端安装 Acorn 8.19.0 后，缓存包 SHA-512／lockfile 及 10 个安装文件逐一核对；语法分析辅助程序和受限 Python 包装交付。12 项构造专项通过，完整 341 项为 337 通过、4 跳过；仅输出固定计数，不执行输入。真实 HTML 连接／评论通道未验，无新微信或系统实验，C26 旧回执保全，原 Goal 未完成。[实现与复现](/Users/chenge/project/liumo/docs/inline-script-validation.md) 、[证据](/Users/chenge/project/liumo/evidence/feasibility/inline-script-preparation.json) 。

- 2026-10-19 00:44：用户明确授权 Agent 直接安装后，已执行 C27 项目内隔离命令，仍退出 1／ENOTFOUND registry.npmjs.org；累计两次失败，Acorn／lockfile 均不存在。分析程序和自测尚未实现，当前依赖安装需要具备网络能力的执行环境；不重复尝试、不启动新微信实验，原 Goal 仍未完成。[证据](/Users/chenge/project/liumo/evidence/feasibility/inline-script-preparation.json) 、[操作说明](/Users/chenge/project/liumo/docs/inline-script-validation.md) 。

- 2026-10-19 00:42：项目内依赖安装实际退出 1／ENOTFOUND，确认 Acorn 和 lockfile 均不存在；未执行脚本分析自测，不计为通过。空 npm 配置、禁用生命周期脚本／重试与官方 TLS 范围保持；没有替代传输或新系统实验。[安装证据](/Users/chenge/project/liumo/evidence/feasibility/inline-script-preparation.json) 。

- 2026-10-19 00:35：C26 真实核对：HTTP 200／gzip、两条 Content-Type 完整归一化等价，789852 字节编码／3493845 字节解码 HTML，独立文章身份通过。57 个 script、2 个外部来源均被拒绝，无可用公共脚本地址；固定词频不足以证明调用关系，静态取证整体 partial，评论及完整归档未通过。16.313 秒内四项恢复通过，公共材料身份、私钥不存在及 C25 回执另验；63 份代码与 329 项基线一致，未重复测试。原 Goal 服务仍 blocked、未完成。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/article-static-duplicates-live.json) 。

- 2026-10-19 00:20：完整回归 329 项，325 通过、4 跳过；实际 mitmproxy 构造双头区分等价／冲突并保持 gzip 字节，63 份 AST 与 C24／C25 私有回执核对。标准和 API／安装源码仅为机制证据，新真实验证未通过。[准备索引](/Users/chenge/project/liumo/evidence/feasibility/article-static-duplicates-preparation.json) 。
