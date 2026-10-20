# 本机微信凭证验证：阶段报告

## C20：正文读取分项通过，评论快照失败

2026-10-18 18:47：C20 普通终端取得 HTTP 200、3493257 字节正文，完整传输及号／文章／标题的独立 HTML 身份门槛通过；这份响应约 3.33 MiB，确实超过旧 2 MiB 预算，但不能反推旧 56／302 根因或证明 Cookie 必需。评论请求 HTTP 200／业务码 -3，快照失败、保存 0 条，整体 partial；不是文章无留言。正文／评论各 1 次已消耗，旧结果保全，不再复用该候选重试。本次只保存功能摘要与失败评论快照，未保存 HTML 或生成 Markdown／本地配图／原页截图。离线 18 项评论 query 语义及 UA 与固定参考一致，当前 token 无百分号解码差异；完整 Cookie、响应 Cookie 更新及正常微信成功评论请求仍无对照，-3 原因未知。50 份代码哈希符合 268 项基线，未重复测试；原 Goal 仍 blocked、未完成。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/article-cookie-body-live.json) 。

## C16：单篇文章兼容与恢复实测通过

2026-10-18 16:08：C16 单次文章兼容与限时收尾通过。普通终端启动后，安装前对照／不信任及安装后 17 项范围检查成立；控制 HTTP 200、代理控制计数各 1。Agent 对猫笔刀固定文章正常刷新一次，页面可读且未见证书警告；文章请求／响应从 0 增至各 1，普通目标域从 0 增至各 20，TLS 失败计数均为 0。约 60.3 秒完成代理回读恢复、明确有效撤销、进程停止及两份私钥删除，180 秒窗口内收尾通过。未采凭证或发列表／评论探针，不证明旧错误的唯一根因、两号兼容或凭证功能；236 项基线哈希未变，未重复运行代码测试。C16 已关闭，不重跑；原 Goal 未完成。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-compat-live.json) 。

## C15：安装约束与后续撤销通过，限时收尾未通过

2026-10-18 15:14：C15 普通终端安装后 17 项约束通过；后续独立恢复已取得证书不存在及带根链目标明确不信任 （-67843／信任结果 5），本次有效撤销验收通过，无需继续运行命令。撤销验收在信任开始 125.8 秒后完成，原 120 秒自动收尾未通过，不补记为成功。已修正自动／独立撤销各命令 30 秒认证预算，并将自动流程收尾预留增至 70 秒；216 项回归为 212 通过、4 跳过。预算修正仅经构造测试，未重装或重跑系统实验。微信兼容、无人值守追更及原 Goal 仍未完成。[现场证据](/Users/chenge/project/liumo/evidence/feasibility/installed-anchor-live.json) 。

## C14 普通终端：macOS 显式根矩阵通过

2026-10-18 14:45：已核对普通终端 C14 离线结果。macOS 正对照退出 0、信任结果 4，CT 提示与成功决定并存；两个验证器各 51 项均取得结果，改进候选各 17 项符合预期，朴素方案各有 7 个范围遗漏。未安装信任、改代理或访问微信。程序／测试 38 份哈希与 200 项回归基线一致，未重复运行。显式根结果不等于安装后信任或微信兼容；新证书亦使本次不能单独证明旧 Agent 内部错误的根因。该离线检查点完成，原 Goal 仍 blocked、未完成。[终端证据](/Users/chenge/project/liumo/evidence/feasibility/native-control-terminal.json) 。

## C13 离线约束：OpenSSL 分项通过，macOS／微信未验证

2026-10-18 12:38：C13 离线证书探针已交付。OpenSSL 3.6.3 下改进候选的 17 个场景符合预期，朴素 DNS 许可方案有 7 个范围遗漏；macOS 显式根正对照退出 1、含 CT／SCT 提示，未执行后续矩阵，不算约束通过。198 项回归为 194 通过、4 跳过。未安装信任、改代理、访问微信或保留私钥；没有新增微信功能通过项。整体 partial，原 Goal 仍 blocked、未完成。[离线报告](/Users/chenge/project/liumo/docs/certificate-scope-offline.md) 、[证据](/Users/chenge/project/liumo/evidence/feasibility/certificate-scope-offline.json) 。

## C12 文章页对照：证书错误可见，正常恢复通过

2026-10-18 12:26：C12 单次文章对照已结束并正常恢复。控制 HTTP 200、代理控制计数各 1；Agent 于 12:22:02 一次刷新猫笔刀样本后，页面出现 NET::ERR_CERT_AUTHORITY_INVALID，目标 certificate_alert 从 0 增至 15，文章／普通目标 HTTP 仍为 0。代理恢复回读、临时信任撤销和进程停止通过，未采凭证、未发列表／评论探针。当前配置未被文章浏览器接受；主机限定信任的 Chromium 兼容性仅为源码支持的假设，尚非微信根因证明。不重跑本次实验，原 Goal 未完成。[现场证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-article-diagnostic-live.json) 。

现场前后计数、UI 时间、证书兼容性假设及证据边界见 [通道复核报告](/Users/chenge/project/liumo/docs/wechat-profile-route-review.md) 。当前不需要用户继续刷新或重跑；页面错误未通过警告绕过，系统恢复通过不等于页面已重新打开。准备阶段 193 项测试、早期真实功能失败及其他各阶段索引保持独立。

## C11 结果：参考实现覆盖文章，当前主页路径仍未知

2026-10-18 11:56：只读复核已完成。wxdown 的固定插件捕获文章 `/s` 的响应凭证；exporter 的列表模块使用调用方提供的凭证，并未提供当前 Mac 主页初始化实现。上游教程要求 HTTP／HTTPS 双代理和系统级信任，留墨仅改 HTTPS、使用用户级主机限定信任，条件不同但未证明失败根因。没有找到本机 4.1.15／270100 主页路径的直接证据；未开新实验、未放宽权限，代码未改。来源、证据等级及下一步分支见 [复核报告](/Users/chenge/project/liumo/docs/wechat-profile-route-review.md) 。

前轮阶段快照：2026-10-17 22:00（北京时间）；当前进展见 C11 与 C10。本报告承接 [后续施工清单](/Users/chenge/project/liumo/goals/20261017-1606-wechat-session-validation.md) 的 C0 至 C6。一次采集与正常系统恢复已通过，候选凭证的功能有效性未通过。本轮 Agent 已完成独立 curl 真实请求：两篇正文均在 302 跳转处停止，对齐参考字段后的两号列表均为 HTTP 200／业务码 -3，两号主页均未建立可核实的会话上下文。147 项自测中 143 通过、4 跳过。原 Goal 服务仍为 `blocked`，未新建或标完成。[最新证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-autonomous-validation.json) 。

## C10 结果：UI 刷新可见，实际主页通道仍未观测到

2026-10-18 11:49：C10 单次实验已到期并正常恢复。控制 HTTP 200、代理控制请求／响应各 1；Agent 在北京时间 11:46:29 向已确认的猫笔刀主页成功发送一次 ⌘R，观察到卡片图片占位后重新加载、互动数字变化。普通目标域 HTTP 计数始终为 0；唯一 1 次 certificate_alert 类客户端 TLS 失败在刷新前已出现，刷新前后及后续取样均未增加，不能归因本次刷新。代理恢复回读、临时信任撤销及进程停止通过；未采凭证、未发列表／评论探针。C10 诊断交付完成，实际主页网络通道与功能会话仍未建立；本次无需用户继续操作或重跑。[C10 现场证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-ui-diagnostic-live.json) 。

| 对象 | 现场结果 | 验收范围 |
| --- | --- | --- |
| 控制 | HTTP 200，代理控制请求／响应各 1 | 本次代理控制路径通过，账号功能未通过 |
| 目标操作 | 一次成功 ⌘R；图片出现占位后恢复，互动数字变化 | 主页重载可见；不证明走目标域或已完整加载所有文章 |
| HTTP | 普通目标域请求／响应始终为 0 | 当前观察范围没有识别实际主页加载通道 |
| TLS | 刷新前已有 1 次 certificate_alert，前后及后续计数相等 | 仅固定类别；不能归因刷新、账号或证书固定 |
| 恢复 | 代理恢复回读、信任撤销检查、进程停止均通过 | 本次正常收尾通过；异常终止／休眠仍未验证 |
| 凭证与探针 | 禁凭证，无 requests 目录、无列表／评论探针 | 不把控制 HTTP 或 UI 重载当可用会话 |

首次按键在 11:45:56 因用户改变应用被工具阻止，未计为成功刷新。重新读取目标后，在 11:46:17 取前样本，11:46:29 成功发送一次快捷键，11:46:37 取后样本，11:47:13 取后续样本，均在 11:45:14 至 11:47:14 的计划窗口内。唯一 TLS 告警已存在于 11:46:17 的样本，后续无增量；不能把它当成刷新失败原因。UI 原图在本会话 Computer Use 输出可审阅，未保存本机截图文件；本机归档保存时间、固定计数、操作摘要及最终收尾摘要与校验值。

本轮没有更改代码，程序／测试哈希仍与 188 项回归索引一致。下一项只读核对当前 Mac 正常主页的加载方式及公开实现依据，不重跑相同实验，不扩大域名／信任或降低 TLS。来源、多篇覆盖、评论、原页单图及续期继续未通过；原 Goal 保持 blocked、未完成，未新建。

## C9 当前进展：控制及恢复通过，目标连接停在客户端 TLS 阶段

用户补充 stormzhang 主页和两个菜单截图；文章卡片可见，但图中没有复制链接／外部浏览器入口。页面刷新入口可见，可用于后续有控制条件的重新加载；截图仍不暴露实际地址或网络机制。“下载内容”的行为未知，不点击或擅自当作含评论导出。

已经准备 120 秒、无凭证的 diagnostic 模式：先发一次无账号字段的公开 HTTPS 控制请求，显式经过本次代理、用本次 CA 校验；控制请求／响应与页面流量分别计数。只有控制传输及代理观测均成立，才提示正常刷新猫笔刀主页，否则立即恢复。该模式完全禁用凭证匹配和保存，不发列表或评论请求，独立目录和恢复路由保留旧两次实验。具体范围见 [操作说明](/Users/chenge/project/liumo/docs/wechat-session-operations.md) 。

必要完整回归保留为 179 项，175 通过、4 跳过；36 份程序／测试哈希未变，本轮只读取现场结果并更新文档，未重复运行程序测试。Agent 初次系统预检停止后，用户已在普通终端启动本次诊断。

2026-10-18 07:54：C9 单次诊断已到期并正常恢复。固定无凭证控制为 HTTP 200，代理侧控制请求／响应各 1 次；非控制目标域 HTTP 请求／响应未记录，目标 SNI 的 TLS 客户端失败共 91 次。主机限定信任、代理往返、最终代理恢复回读、信任撤销及进程停止通过；未采凭证或发列表／评论探针。计数不能确认应用／账号归属，未收到本轮刷新及页面表现反馈，不能认定证书固定或具体根因。不再刷新或重跑本次实验，来源及含评论原页单图仍未通过。[C9 现场证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-transport-diagnostic-live.json) 。

本机 mitmproxy 12.2.3 的 proxy/layers/tls.py 第 225 至 239 行将 tls_failed_client 定义为客户端握手失败，第 637 至 674 行处理协议不匹配、证书拒绝、连接关闭等多类情况。本轮仅保存分类计数，未保存错误原因，因此不能从 91 次事件推出证书固定、凭证过期或接口关闭；控制成功也不证明微信信任路径可用。请求体／列表参数尚不是本次失败连接可核对的阶段。原 Goal 保持 blocked、未完成，不新建。

## C8 结论：主页可见，采集路径仍未定位

2026-10-17 22:49：用户提供正常主页截图及“看到了”的反馈。图中可直接确认猫笔刀的主页与至少两张文章卡片，另有 stormzhang 标签页；该标签内的列表内容、地址和截图时间均不可见。接受正常主页可显示的反馈，不再等待用户重复证明操作。截图只留忽略归档，公开索引不复制朋友数或其他个人内容。[观察与代码证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-profile-observation-gap.json) 。

只读源码核对发现，C7 的 target_host_responses_seen 计数发生在路径匹配之前，而现场未记录任何目标域响应。因此，“匹配器只支持旧路径”不足以单独解释本轮结果，直接放宽路径不是已证实的修复。原诊断只记录响应阶段、TLS 失败只记总数，无法区分目标域请求是否进入代理、是否到响应阶段，或 TLS 失败是否属于目标主机；不能据此认定客户端证书固定、缓存、其他端点、凭证失效或接口关闭。

现已仅在项目内补齐目标请求／响应、profile／article／other 路径计数及 TLS 失败 target／other／unknown 分类。不保存其他主机名、任意路径、查询、错误原文或 ClientHello；默认关闭和停止／到期后不新增观测。依据为已锁定的 mitmproxy 12.2.3 本机源码 TlsData.conn 和 Connection.sni，源码路径、行号和 SHA-256 在新索引中。构造事件和实际组件 Connection／TlsData 对象回放通过；完整 168 项中 164 通过、4 跳过。

这是 C7 结束后的诊断改动，未启动代理、信任证书、发起微信请求或取得新会话。新的计数尚无实测，不能追补 C7 的 19 个 TLS 失败事件；C7 原始索引与当时的 164 项程序版本保留，不改写历史。下一项先明确正常页面可观察的公开地址与请求阶段证据；若现有权限内无法取得，交付具体缺口，不让用户重复相同采集、扩大捕获范围或降低 TLS。Goal 仍未完成。

## C7 结果：本次已结束，未取得新会话

2026-10-17 22:42 最终现场结果：本次正常到期，代理已恢复并回读、临时信任已撤销并检查、采集进程已停止，恢复验收通过。全窗口没有两号主页／列表匹配，必要字段保存与即时列表探针均为 0；功能验收未通过。共 19 个 TLS 客户端失败事件，没有对应账号或原因证据，不能推断 Mac 微信不兼容、凭证失效或接口关闭。用户仅确认已运行命令，尚未确认就绪后的主页／列表操作和页面表现；先补此反馈，不要求重跑实验。[最终现场索引](/Users/chenge/project/liumo/evidence/feasibility/wechat-profile-session-live.json) 。下方 22:33、22:21 段落为本次过程快照。

2026-10-17 22:33 现场更新：用户已在普通终端启动。主机限定信任及代理原值往返均通过，状态为 ready_open_two_profiles_in_mac_wechat；采集正在运行，尚无两号匹配请求或即时核对，最终恢复待验收。已请求在 Mac 微信正常进入两号主页／列表，不重跑启动命令、延长窗口或改动正在执行的代码。33 份程序／测试哈希与已测版本一致。[现场索引](/Users/chenge/project/liumo/evidence/feasibility/wechat-profile-session-live.json) 。

2026-10-17 22:21：用户已单独授权一次最多 10 分钟的两号主页／列表会话实验。自研最小字段采集、每号一次即时核对、独立实验／恢复路由与当前基线检查已交付；164 项回归为 160 通过、4 跳过。实际带终端启动在只读查询返回 preflight_system_authorization_unavailable，未创建新实验或改系统；旧实验的恢复与停止记录仍通过。已请求普通终端运行一条新启动命令，未要求重复扫码、旧诊断、文章开文或手抄凭证。[C7 证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-profile-session.json) 。下文 C0 至 C6 为前轮阶段事实，147 项索引保持原样。

新匹配器仅处理固定两号的 profile_ext home／getmsg，先确认公开作用域，再筛选查询／头部／Cookie；每种动作只保存首次结果，0600 私有文件，不覆盖旧候选。代理响应正文始终流式转发、不读取或落盘。独立请求在捕获列表后 30 秒内使用白名单字段重建，只向同一 HTTPS 列表端点各号一次；省略查询数量、业务拒绝、结构和身份分别记录，不把过滤重建称原始请求完整重放。不会在拒绝后重复、分页或切换端点。协议范围沿用前轮固定证据，没有增加第三方依赖或执行参考业务源码。

成熟组件的新 profile 选项、头部事件、流式设置和独立恢复提示已在隔离进程用实际组件对象测试；系统恢复顺序、终端子进程／恢复路由、时间门槛和未知文件保全有构造与本机文件证据。未启动真实代理、信任测试 CA 或取得新会话；本次现场恢复、两号功能、完整来源和含评论原页单图均保持未通过。操作入口见 [说明](/Users/chenge/project/liumo/docs/wechat-session-operations.md) 。

## 本轮结论

exporter 的“正常请求 → 提取必要字段 → 独立 HTTP 读取”思路已有一次真实采集证据，但目前只完成候选保存，尚无真实列表或带评论读取成功证据。微信每天在线、HTTP 200 和凭证文件存在均不足以证明该路线可无人值守运行。

采用有限时本机 HTTPS 代理作为实验候选，自研适配器只保存指定文章的必要头部字段。本次衔接原代理的 upstream 模式已实际采集两号候选，之后恢复准确原值，撤销并检查本次 CA 信任，进程停止。该现场结果证明一次取得路径可行，尚不证明持续自动取得、接口有效性或归档成功。具体命令、范围和恢复入口见 [操作说明](/Users/chenge/project/liumo/docs/wechat-session-operations.md) 。没有读取微信数据库、其他应用钥匙串凭证、进程内存或微信读书会话；系统证书操作仅针对本次新生成的 CA。

## C0：实际基线

| 对象 | 观察与证据等级 | 结论 |
| --- | --- | --- |
| 工作区 | 当前目录不是 Git 仓库；此前 HTTP 路线证据中的源码哈希在改动前全部一致 | 未初始化 Git，保留原文件与产物 |
| 设备 | 本机 `sw_vers` 返回 macOS 27.0.1（26A434）；项目 Python 3.14.5 | 本机元数据实测 |
| 微信 | 仅读取 `/Applications/WeChat.app/Contents/Info.plist`，版本 4.1.15、构建 270100、bundle ID `com.tencent.xinWeChat` | 未检查聊天、账号会话或登录有效性 |
| 组件 | mitmproxy 12.2.3 已独立安装于 `.venv-capture/`，43 个 wheel 经 SHA-256 校验，pip check 通过 | 原 `.venv/` 不变；本次另有真实代理采集与停止证据 |
| 代理现状 | 用户普通终端预检已保存完整私有基线：当前服务、已启用的同一本机 HTTP／HTTPS 原代理、无认证、PAC／自动发现关闭，端口绑定通过 | 该依赖已解除；Agent 自身的系统调用限制仍在，实际实验从普通终端启动 |
| 正常访问 | 用户已在 Mac 微信打开两篇样本并提供新截图 | 手动正常访问与候选采集已观察；程序自动开文及含评论整页截图仍未通过 |

已有本机页面观察提供了公开匹配候选，避免让用户抄参数：

| 样本 | `__biz` | `mid`／`idx` | 身份限制 |
| --- | --- | --- | --- |
| 猫笔刀 | `MzE5ODk2NjUwOA==` | `2247498641`／`1` | 来自该样本归档的公开字段与可见署名；新请求仍需核对 |
| stormzhang | `MzA4NTQwNDcyMA==` | `2650682490`／`1` | 来自用户指定样本的观察文件，文件中 account_name 为空；尚非新接口的身份验证 |

字段来源路径与校验值见 [本轮证据索引](/Users/chenge/project/liumo/evidence/feasibility/wechat-session-validation.json) 。这些公开 ID 不是凭证，也不是已实测的可用接口参数。

## C1：已经实现的准备程序

| 模块 | 当前行为 | 仍缺的验证 |
| --- | --- | --- |
| `validation/capture.py` | 限定 HTTPS、精确主机、GET、HTTP 200、`/s`、两个样本的 biz／mid／idx；先匹配公开字段，再解析凭证；窗口最多 600 秒 | 本次两号均匹配并保存；持续取得与使用仍未通过 |
| `validation/credentials.py` | 当前用户私有目录与文件检查、非阻塞写锁、原子落盘；仅轮换本模块已管理且身份相同的文件；拒绝旧时间和未知既有文件 | 两号候选已真实取得；功能有效性、服务端有效期和自然失效后的恢复未通过 |
| `validation/mitm_addon.py` | 默认关闭；显式开启前核对回环监听、域名、TLS 和无抓包输出配置；只读匹配请求的必要 Cookie 头，不读取正文；配置变更不安全时停止采集 | 本次实际 TLS 事件、字段保存与正常停止已观察；异常生命周期仍以构造证据为主 |
| `validation/capture_plan.py` | 输出底层模板与执行前提、虚假回放及比较判断；真实一次性入口独立 | 底层模板不能代替含恢复控制的终端入口 |
| `validation/capture_preflight.py` | 查询活跃服务与原值，私有保存、明确冲突；退出码 0 也识别授权错误 | 用户普通终端基线已核对，尚不是系统恢复证据 |
| `validation/capture_session.py` | 单次目录、工作子进程、双时钟／父管道、原值复核／往返、证书正反主机验证、失败恢复和恢复后有限来源探针；只衔接符合当前条件的本机原代理 | 本次正常系统写入／恢复通过；强制杀死、断电、休眠及其他异常的系统恢复未实测，不能保证即时恢复 |

当前仅接收 `uin`、`key`、`pass_ticket`、`appmsg_token` 与允许的 Cookie 字段，不求助页面脚本求值或扫描其他会话。已保存不代表已认证成功；缺字段一律不生成可用凭证结论。计数型诊断仅区分目标域响应、文章形态和 TLS 失败事件，不保存 URL 或原始错误，不能据此猜测证书固定的具体原因。裸采集逻辑不负责系统恢复，须使用新的终端控制入口。到期或收尾时停止保存，并把新连接改成不解密的上游隧道，再恢复并停止进程；异常恢复状态明确保留。

## 自测与证据等级

当前回归为 164 项：160 通过、4 跳过，见 C7 索引；前轮 147 项见 [自主验证证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-autonomous-validation.json) 。缺列表保护、带凭证样本门槛、私有 FIFO 非阻塞读写、回执与超时、严格单次同文跳转、参考列表头部对齐和主页会话门槛的既有证据保留。4 项跳过为 3 项浏览器未开启、1 项回环监听权限拒绝。123 项 [诊断阶段](/Users/chenge/project/liumo/evidence/feasibility/wechat-profile-diagnostic.json) 、112 项 [终端程序交付](/Users/chenge/project/liumo/evidence/feasibility/wechat-session-runner.json) 、97 项 [授权后阶段](/Users/chenge/project/liumo/evidence/feasibility/wechat-session-authorized-preflight.json) 和 88 项 [准备阶段](/Users/chenge/project/liumo/evidence/feasibility/wechat-session-validation.json) 独立保留；不能代替新代码浏览器或设备实测。

组件初始化测试实际生成临时测试 CA 和双 SAN 探针证书、检查私有权限与恢复计划、加载真实 DumpMaster 上游配置、验证停止后隧道及退出元数据。临时目录随测试清理；没有信任该测试 CA，没有监听或请求网络，也不等于 macOS 真实正反主机验证通过。

`capture-fixture` 的虚假落盘、过滤和清理证据保留；Agent 预检受限的旧产物也保留。启动前自测不能作为后续系统状态。17:21 现场记录已确认本次代理恢复、证书信任撤销和采集进程停止；之后的独立 curl 及新增回归没有再次修改系统配置或采集凭证。

## 本次现场观察

- 17:20：状态为 `ready_open_two_samples_in_mac_wechat`，`trust_scope_verified` 与 `proxy_roundtrip_verified` 均为 true，`finished` 为 false。
- 已保存 stormzhang 候选凭证 1 次，猫笔刀尚未保存。保存不等于服务端认证，也不等于可持续自动取得。
- 诊断计数为目标域响应 24、文章形态响应 1、TLS 客户端失败事件 193；这些计数不能定位具体应用，也不能据此认定证书固定或猫笔刀失败原因。
- 用户新截图显示两个目标文章标签和正文／留言片段，确认正常阅读窗口可见；不是采集成功或完整单图证据。已请求在当前实验窗口重新正常打开猫笔刀的指定链接一次，以排除已有标签页未产生新请求的可能性，缓存原因尚未证实。
- 17:21：两号候选各保存 1 次，`reason` 为 `two_credentials_saved_authentication_unverified`。代理为 `restored_and_read_back`，信任为 `revoked_and_checked`，`recovery.verified` 与 `proxy_process_stopped` 均为 true；最终采集状态 closed、running false。正常实验持续约 4 分 20 秒，未延长或重启。
- 最终诊断计数：目标域响应 40、文章形态响应 2、TLS 客户端失败事件 198；未保存无关 URL／错误原文，不用计数推定具体失败原因。
- 恢复后两号各进行 1 次列表请求，均以 `source_shape_changed` 停止，没有取得可解析条目。现有代码先检查业务码，再解析列表，因此该错误说明通过了现有业务码检查，但不足以证明身份或凭证可用于目标功能。没有原始响应或细分字段证据，不能猜测为权限或分页结构变化。
- 17:22：Agent 对 stormzhang 的一次结构诊断请求在传输层失败，只记录 `transport_failed`，没有响应结构；不将它当成服务端第二轮拒绝，不换入口绕过环境限制，也不要求用户再开文或重新实验。
- 本次系统实验已结束，不重启、不延长、不覆盖私有目录。后续结果见下节；评论、原页截图和自动续期没有新增通过项。

## C3：已落实的诊断与协议对照

已新增 `mp-diagnose --account all --transport curl`，两号各一次第一页，固定类型／数量输出；原来源扫描失败时也保留脱敏结构。现有系统 curl 为 8.7.1，不新增依赖；敏感参数只经子进程 stdin，不写临时配置、不进入 argv。Python TLS 路径保留本机 3.14 的默认验证策略并禁止环境 keylog。

按 [固定 exporter 提交](https://github.com/wechat-article/wechat-article-exporter/tree/152f23832c7f3664b86148e84bd3f75e513e4dd2) 的已有缓存逐字段复核，访问与复核日期 2026-10-17，缓存散列沿用原研究索引：

| 对象 | 对照结果 | 判断 |
| --- | --- | --- |
| 列表地址与动作 | 同为 `/mp/profile_ext`、GET、action=getmsg | 没有发现端点／动作差异 |
| 查询字段 | __biz、offset、count、uin、key、pass_ticket、f=json、is_ok=1、scene=124 一致 | 不能据此保证当前服务端可用 |
| 请求头 | 已一次性对齐显式 WAE UA、Origin、Accept-Encoding=identity 和 Accept；不把阅读 Cookie 充作上游可选的后台 CookieStore | 实际两号均返回 -3；不证明差异是根因，不再机械换 UA |
| appmsg_token 解码 | 上游对 Cookie token 做百分号解码，当前采集器未做该解码；本次两号仅在内存核对，均无百分号转义，存值与 Cookie 原值／解码值相同 | 本次候选无此实际差异，不修改凭证；评论仍未验证 |
| 原文与 comment_id | 既有两篇 page-observation 只有 biz／mid／idx，没有 comment_id | 不能凭空请求评论或把旧正文结果当新访问条件成立 |

17:27 的 curl 子进程诊断为退出码 6（DNS 解析失败）；17:28 的直接管道调用也没有取得 HTTP 响应（状态 000）。公开主机的无凭证 curl 单独调用曾返回 200，但不能证明凭证请求路径可用。没有关闭 TLS、改 DNS／系统代理或继续同方向重试，也未收到微信业务拒绝的新证据。

用户 17:45 的双号诊断已收到：两号 ret=0／can_msg_continue=0，但 general_msg_list、next_offset 缺失。当前代码将其细分为 source_list_missing，不能补成空列表或推进扫描位置；旧产物保留原错误码。该命令无需重复运行。

21:42 至 21:55 的自主实测已完成，均只使用项目已有凭证，没有新采集或系统改动：

| 检查 | 实际结果 | 判定 |
| --- | --- | --- |
| 带凭证正文 | 两号均 HTTP 302，Location 仅分类为相同 HTTPS 主机的文章路径；严格同文条件未通过，未跟随 | 未取得本轮正文；未继续图片、评论或浏览器请求，不称正常跳转或无评论 |
| 对齐参考后的列表 | 两号各一次，HTTP 200／业务码 -3，无列表 | 业务拒绝；不能确定过期、永久关闭或具体权限原因 |
| 主页会话前置条件 | 两号各一次 HTTP 200；当前静态解析未识别到目标 biz、poc_token 或 poc_sid | 身份门槛未通过，后续列表各 0 次；不据此推断响应具体类型或会话失效 |

传输通过私有 FIFO 衔接已获准的独立 curl，原始响应／头部仅留内存；敏感 URL 不进命令行或普通文件。初期失败另有本地回执权限和非阻塞读写竞争，已修复并以实际 FIFO 测试、公开 HTTPS 200 及上述真实请求区分，不当作微信账号失败证据。第二次早期控制器中断没有完整 HTTP 回执，服务端是否收到请求未知。完整路径、时间、源码版本与哈希见最新证据索引。

主页前置步骤仅参考一个 Windows 实现的 [固定 provider.py](https://github.com/tingaidehua/wechat-article-downloader-skill/blob/d97c255419e9a6de1c32bb5a9cf0f747630499bd/skills/wechat-article-downloader/scripts/wechat_article_downloader/provider.py) 和 [协议说明](https://github.com/tingaidehua/wechat-article-downloader-skill/blob/d97c255419e9a6de1c32bb5a9cf0f747630499bd/docs/protocol-principles.md) ，访问日期 2026-10-17。它先正常请求主页取得 poc_token／poc_sid，再读列表；不证明 Mac 适用。这里只补协议证据缺口，不新增候选选型、不安装或执行上游代码、不扫描其 Windows 缓存路径。第三方对 -3 的错误映射不是官方失效定义。

4 项跳过继续单列：3 项浏览器测试未显式开启，1 项回环 HTTP 传输因监听权限拒绝。此前用户终端的 44 项完整浏览器测试保留为独立历史证据；不冒充本轮 Agent 环境已解除限制。

## 候选组件的一手依据

以下资料访问日期为 2026-10-17。这里只固定实验候选，不将文档／源码升级为真实通过。

- [mitmproxy 证书机制](https://docs.mitmproxy.org/stable/concepts/certificates/) ：CA 信任和独立 confdir；证书固定的应用可能拒绝，遇到此情况停止，不修改应用或关闭 TLS。
- [模式说明](https://docs.mitmproxy.org/stable/concepts/modes/) ：普通模式与本地进程捕获是不同机制；后者涉及新的系统权限，本轮不切换过去。
- [域名排除边界](https://docs.mitmproxy.org/stable/howto/ignore-domains/) ：显式 HTTP 代理请求不受同样的忽略机制保护。因此提案只调整 HTTPS 代理，不启用 HTTP 代理。
- [选项](https://docs.mitmproxy.org/stable/concepts/options/) 、[事件接口](https://docs.mitmproxy.org/stable/api/events.html) ：用于核对回环监听、allow_hosts、TLS 验证、日志／流保存与头部事件，实际版本安装后还需复核选项。
- 候选固定为 [mitmproxy 12.2.3 源码](https://github.com/mitmproxy/mitmproxy/tree/6c09d56e4c29a92f5ad01b03199977584b8ea14f) ，[pyproject.toml](https://github.com/mitmproxy/mitmproxy/blob/6c09d56e4c29a92f5ad01b03199977584b8ea14f/pyproject.toml) 声明 Python ≥ 3.12，并列出 3.14；当前本机隔离安装与版本检查已通过。[上游 PR 列表](https://github.com/mitmproxy/mitmproxy/pulls) 可见截至 2026-10-16 的活动；维护者响应、依赖安全和实际 TLS 兼容性尚未完成全面评估。
- 安装依据为同一固定提交的 [uv.lock](https://github.com/mitmproxy/mitmproxy/blob/6c09d56e4c29a92f5ad01b03199977584b8ea14f/uv.lock) ，只导出运行依赖、按当前平台选择 wheel；主包另与 [PyPI 文件信息](https://pypi.org/project/mitmproxy/12.2.3/) 核对。当前 Python 进程不能解析 PyPI，使用获准的公开下载途径取得文件、核对散列后离线安装，不关闭 TLS。安装包含组件的私有平台包，但未启用本地进程捕获、系统扩展或任何后台服务。
- 基础安全核对：维护者 [LDAP 公告](https://github.com/mitmproxy/mitmproxy/security/advisories/GHSA-527g-3w9m-29hv) 记载次日确认报告、约四个月后发布修复，修复版本为 12.2.2；[h2 公告](https://github.com/mitmproxy/mitmproxy/security/advisories/GHSA-63cx-g855-hvv4) 的组件修复版本为 12.1.2；[mitmweb 公告](https://github.com/mitmproxy/mitmproxy/security/advisories/GHSA-wg33-5h85-7q5p) 明确该问题不影响 mitmdump。当前 12.2.3 超过这些修复版本，不开启 LDAP 或 mitmweb；这只是所列公告的核对，不代表所有依赖已无漏洞，也不承诺响应时效。

若进入实验，成熟组件仅承担 TLS 代理与事件接入：标准库或已有组件不具备安全维护证书签发及 HTTPS 中间代理的现成能力。自行重写这些底层能力会扩大本阶段范围。它不会进入当前产品常驻运行链，是否需要保留必须由真实证据决定。

## 尚未通过与后续条件

| 检查点 | 当前判定 | 下一项可执行条件 |
| --- | --- | --- |
| C0 | 源码／环境基线已核对；正常入口未新实测 | 保留已有用户对照，不要求重复截图 |
| C1 | 现场主机约束、代理往返及本次正常收尾通过 | 异常退出、强制杀死、断电／休眠仍需分开验收 |
| C2 | 两号候选各保存 1 次；本轮未建立可用会话 | 需要正常入口产生且能立即核对用途的主页／列表上下文；不让用户手抄凭证 |
| C3 | 列表与主页条件未通过；C20 固定正文读取／独立身份通过，评论 HTTP 200／-3；完整归档未通过 | 停止复用旧候选重试，先建立正常微信成功评论请求的网络基线；旧失败证据保留 |
| C4 | 真实含评论单张原页截图未通过 | 正常原页访问成立后独立核对，不将 API 重建页面或拼图替代要求 |
| C5 | 未验证持续自动取得／自然续期 | 两轮自动取得与使用、自然过期恢复分别记录，微信在线不能替代证据 |
| C6 | 阶段文档已交付；原目标未完成 | 补齐真实证据、系统恢复和原 Goal 的其余验收项后再审计 |

当前不进入完整 MVP。推荐仍保留自研 HTTP 发现／正文／评论、原页浏览器截图的分工，但 Credential 来源不能定案。新的限定方式已按 C7 单独获准、执行并正常恢复，但未取得目标会话字段。下一项先确认就绪后的正常导航与页面表现，再核对匹配边界及 TLS 路径；两次固定实验均保持关闭，不删除旧目录重跑。暂不要求重复扫码、旧文章开文、旧诊断或手抄 token。即便新的列表读取成功，分页覆盖、真实时间、评论原页单图与自动续期仍须独立验收；不能承诺重新登录或采集一定解决。
