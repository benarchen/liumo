# C17：固定文章候选与恢复后功能核对

## 范围与当前状态

2026-10-18 18:47：C20 普通终端取得 HTTP 200、3493257 字节正文，完整传输及号／文章／标题的独立 HTML 身份门槛通过；这份响应约 3.33 MiB，确实超过旧 2 MiB 预算，但不能反推旧 56／302 根因或证明 Cookie 必需。评论请求 HTTP 200／业务码 -3，快照失败、保存 0 条，整体 partial；不是文章无留言。正文／评论各 1 次已消耗，旧结果保全，不再复用该候选重试。本次只保存功能摘要与失败评论快照，未保存 HTML 或生成 Markdown／本地配图／原页截图。离线 18 项评论 query 语义及 UA 与固定参考一致，当前 token 无百分号解码差异；完整 Cookie、响应 Cookie 更新及正常微信成功评论请求仍无对照，-3 原因未知。50 份代码哈希符合 268 项基线，未重复测试；原 Goal 仍 blocked、未完成。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/article-cookie-body-live.json) 。

用户已明确授权 C17，仅处理猫笔刀固定技术样本《上个月最值的一笔消费》。C16 已证明该篇当前微信文章可以经过受约束 CA／固定目标叶配置正常请求及恢复，不重跑 C16。C17 的候选取得、正文功能、评论与真实收尾分别验收，不把构造测试或文件保存当功能通过。

实现复用 [compat_session.py](/Users/chenge/project/liumo/validation/compat_session.py) 的独立固定模式，保持 C16 默认配置；新入口由 [functional_capture.py](/Users/chenge/project/liumo/validation/functional_capture.py) 选择。适配器为 [functional_addon.py](/Users/chenge/project/liumo/validation/functional_addon.py) ，恢复后核对为 [functional_check.py](/Users/chenge/project/liumo/validation/functional_check.py) 。只使用现有隔离环境，不新增依赖，不启用订阅或安装后台任务。

## 实际入口（一次目录已使用，采集不可重跑）

Agent 先通过 Computer Use 确认固定文章和无聊天的界面，写入最近 300 秒的私有 UI 就绪记录。没有该记录或系统前置条件失败时，不启动实验。随后只需在普通终端执行一次，保持运行：

```bash
cd /Users/chenge/project/liumo
.venv-capture/bin/python -m validation article-functional-session
```

macOS 认证由用户完成；用户不要刷新、不额外按 Enter。Agent 只在状态 `ready_refresh_maobidao_article_for_functional_capture`、控制请求与计数通过、时间充足且文章可确认时取样和正常刷新一次，随后请求恢复：

```bash
.venv-capture/bin/python -m validation article-functional-observe --phase before_refresh
# Agent 界面操作一次正常刷新，并核对实际页面状态。
.venv-capture/bin/python -m validation article-functional-observe --phase after_refresh
.venv-capture/bin/python -m validation article-functional-finish
```

一次目录为 `.auth/wechat-capture/article-functional-session/`，不可重跑；旧七次实验必须已恢复、停止，并持有相关生命周期锁。新建本次 CA／独立叶私钥，仍仅目标 DNS、排除子域及全部 IP；只临时用户级 SSL 信任和当前服务 HTTPS 代理，衔接原有本机上游。系统窗口 180 秒，收尾预留 120 秒；预算不足、取消、父进程退出或异常均进入恢复。代理原值回读、有效撤销、进程停止和两份私钥删除分别验收；未知结果不算成功。

若自动恢复未通过，只运行恢复入口，不重跑 session：

```bash
.venv-capture/bin/python -m validation article-functional-recover
```

恢复入口不重复采集或发送功能请求。正常 session 父进程在恢复通过后自动调用主项目环境做功能核对；若父进程中断、独立恢复后尚未尝试功能核对，可执行一次：

```bash
.venv/bin/python -m validation.functional_check
```

此入口持有单独进程锁，并用不可覆盖的 `functional-attempt.json` 标记一次尝试；重复运行只拒绝，不补发。字段缺失、未知恢复、材料变化或私钥仍在时不会发请求。断电、进程遭 SIGKILL、无法识别遗留进程等情况仍可能需要人工检查，不承诺这些异常的自动恢复。

## 凭证与请求边界

- 被动采集只匹配固定猫笔刀公开 biz／mid／idx、GET、HTTP 200 的文章响应，且必须在控制通过与就绪状态之后。其他文章／域或非成功响应不读取 Cookie 头部。首个同文候选缺字段或写盘失败也不重试、不扩大匹配范围。
- 只保存既有提取器的白名单 query／Cookie、固定来源身份和脱敏后的公共文章 URL。候选为本次目录下的 `candidate.json`、0600，采用排他新建；旧 `.auth/wechat/` 不读取、不覆盖。原始 URL、完整头部及被动流量正文不持久化；匹配与字段过滤只在内存中进行，不读取账号数据库、缓存或无关窗口。
- 恢复通过后，凭证只向 `mp.weixin.qq.com` 发送，沿用原有本机上游并保持 TLS 校验。curl URL／Cookie 只通过 stdin，不进入进程参数或普通日志；不使用默认配置、环境代理、重定向、自动重试或 TLS 降级。
- 最多一次同文正文 GET；成功核对 HTML 内独立的号、文章及标题后，才最多一次评论 GET。每次子进程最长 20 秒、合计最长 40 秒；不下载配图、不发列表／主页／额外回复请求。HTTP 302、受限页、字段／身份未知时停止，不匿名回退。
- 候选时间必须落在本次计划的主动采集窗口内，且不能来自未来。独立恢复等待不等于服务端凭证过期，不以程序自设的 10 分钟阈值判失效；仍只允许本次尚未消耗的一次功能尝试，服务器拒绝后不补发。
- 正文身份提取使用没有身份查询参数的固定短链接作为解析上下文，避免原有解析器的 URL 字段优先级掩盖返回 HTML 的身份差异。仅保存固定摘要、计数和必要的评论白名单快照，不保存原始网络流量。
- 评论复用现有快照解析，最多一页；存在更多评论／回复或范围不明时标为部分成功或失败，不把预算截断当完整。本篇已由用户及 C16 界面确认有留言，API 返回空列表时标为未知并记录差异，不认定原页无评论；不可访问与加载失败仍分别记录。正文身份通过也不代表配图离线可读、真实原页整图或自动发现通过。

归档位于忽略的 `archives/feasibility/*-article-functional-session/` 和 `*-article-functional-check/`；候选保留在本机私有目录，普通输出和公开证据只含固定状态、数量、数字错误码与路径。字段取得、凭证可用性、评论及原页截图是不同验收项。

## 自测与证据等级

```bash
.venv/bin/python -m unittest discover -s tests -v
```

C17 初次交付时完整 252 项中 248 通过、4 跳过。新增 16 项覆盖固定身份／一次候选、缺字段和写盘失败不重试、Cookie 过滤和普通摘要脱敏、独立模式与旧入口、私有文件／符号链接保全、恢复门槛、单独锁和不可重跑、HTML 身份差异、评论无／禁用／失败／回复超预算、请求写前记录、stdin 与 TLS／主机／上游／时间约束。真实 mitmproxy 组件在禁止网络 socket 的构造回放中运行默认关闭、就绪门槛和一次假候选写入；没有访问微信或使用真实凭证。当前 257 项结果见 C18 节。

初次 Agent 只读预检受环境权限限制，之后用户已在普通终端完成真实启动、独立恢复与一次功能核对。该次正文请求以 curl 56 结束，评论未请求；候选仍未经功能验证。不要再次运行原功能入口、采集或恢复；完整结果与后续观测边界见下节。

施工授权、检查点与交付要求见 [原 Goal 续程清单](/Users/chenge/project/liumo/goals/20261017-1606-wechat-session-validation.md#c17固定文章凭证功能验证) 。

## 本轮交付记录

2026-10-18 16:25：C17 已获单次授权，独立入口、首个固定文章候选和恢复后最多两次 HTTP 核对已实现。252 项回归为 248 通过、4 跳过；新增 16 项覆盖实际组件无网络回放、凭证保全、独立 HTML 身份、恢复与次数门槛，不冒充真实采集。Agent 实际只读预检返回 preflight_system_authorization_unavailable，未创建一次目录、签发证书、启动监听或采凭证；下一步仅需普通终端启动和必要 macOS 认证，其余由 Agent 完成。C16 及旧七次不重跑，原 Goal 未完成。[交付证据](/Users/chenge/project/liumo/evidence/feasibility/article-functional-runner.json) 。

## 本次自动运行验收

2026-10-18 17:35：C17 已取得猫笔刀固定文章首个私有候选，尚未验证凭证可用性。Agent 一次正常刷新后页面可读；文章请求／响应各 1、普通目标域各 16、TLS 失败计数 0。安装后 17 项范围与控制通过；自动收尾用时 113.7 秒，代理恢复、进程停止和两份私钥删除通过，但两条证书撤销命令各超时，证书仍存在且带根链目标仍被接受，整体恢复失败。功能请求均未发送，优先普通终端仅运行 article-functional-recover，不重跑采集。252 项基线的 49 份程序哈希未变，未重复测试；原 Goal 未完成。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/article-functional-live.json) 。

只接受上述自动回执中的明确证据：目标在撤销后仍受信任，不能把“命令已执行”或“私钥已删”当有效撤销。两条命令为 remove-trusted-cert 和按本次指纹的 delete-certificate，均有独立 30 秒预算并返回固定超时代码；这证明本次自动操作超时，不能确定更深的系统认证或执行根因。独立恢复不重装证书，不开启代理，不采集候选或发送 HTTP。只有独立回执确认有效撤销后，才允许执行尚未消耗的一次 functional_check。

UI 证据为本会话 Computer Use 输出，未保存本机 PNG。刷新前点赞 6998／收藏 1093，刷新后 7010／1095，留言入口仍为 33；不能据此认定评论内容已经取得。代理只记录类别计数，其余 15 次请求不认定为评论。

## 独立恢复结果与修正

2026-10-18 17:44：C17 独立恢复已取得有效证据：代理原值、证书不存在及带根链目标明确不信任 （-67843／信任结果 5）、进程停止与私钥删除均通过。移除过程保留一条非零退出记录，以最终回读验收；有效撤销在原开始后约 617.1 秒完成，原 180 秒自动恢复失败记录不补成通过。一份本次候选仍为未验证，正文／评论请求各 0；下一步仅普通终端执行一次 validation.functional_check，不重跑采集或恢复。修正无服务端依据的 10 分钟年龄拦截为本次主动采集窗口身份校验，仍保持一次尝试及两次请求上限；253 项回归为 249 通过、4 跳过，原 Goal 未完成。[恢复证据](/Users/chenge/project/liumo/evidence/feasibility/article-functional-live.json) 。

独立结果并未覆盖原自动失败档案。后续只核对本次窗口内采集的未消耗候选：不通过旧的任意 10 分钟年龄值推断服务器会话失效，超出本次主动窗口／来自未来／不同文章仍拒绝，实际失效或拒绝由服务器响应记录，不增加请求和重试。该修正新增延迟恢复与窗口外拒绝回归；未读取或打印候选值、未发网络请求、未改变系统设置。

## C18：真实失败与传输观测

2026-10-18 17:57：C17 普通终端功能核对已结束：正文请求 1 次，curl 退出 56，正文未验证，评论请求 0；原一次标记已消耗，不能重跑。系统独立恢复仍通过，原自动撤销失败保留。旧程序未保留传输阶段数据，不能推断凭证失效或具体根因。已补齐固定数值观测与独立一次入口，257 项回归为 253 通过、4 跳过。Agent 两次无凭证公开控制均 HTTP 200；不等于原普通终端文章功能通过。C18 同候选的一次观测待新授权，不重采或改系统，原 Goal 仍 blocked、未完成。[功能证据](/Users/chenge/project/liumo/evidence/feasibility/article-functional-live.json) 、[诊断证据](/Users/chenge/project/liumo/evidence/feasibility/article-transport-observation.json) 。

普通终端在北京时间 2026-10-18 17:45:47 开始正文请求，17:45:48 回执为 curl 56；评论未请求。原程序非零退出时先抛错，未保留 HTTP 状态及 stderr，因此不知道是否收到 HTTP 响应、CONNECT 是否完成、TLS 到了哪一步。没有证据证明凭证过期、微信拒绝或代理故障。[curl 官方错误码](https://curl.se/libcurl/c/libcurl-errors.html) 将 56 定义为接收网络数据失败；访问日期 2026-10-18。

本机实际使用 /usr/bin/curl 8.7.1，SecureTransport／LibreSSL 3.3.6。按本机 --manual 与 [官方 write-out 说明](https://curl.se/docs/manpage.html#write-out) 核对 HTTP、CONNECT、证书校验结果、TCP／TLS 时间和下载字节；校验结果 0 不能单独证明握手完成。错误原文只在内存映射固定类别，不落日志；非零退出即使有 HTTP 200 或部分正文也不验收成功。旧结果不能补成新字段。

以下是同日 Agent 执行环境的实际公开控制，各仅一次，固定 URL 为 https://mp.weixin.qq.com/robots.txt?liumo_feasibility_control=1 ，未携带凭证，正文丢弃，TLS 校验开启，无重试／重定向，最长 18 秒。它们发生在普通终端失败之后，不能定位前一次失败；也没有测试同篇文章或其凭证。

| 路径 | curl 退出 | HTTP | CONNECT | 证书校验 | TCP 秒 | TLS 秒 | 下载字节 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 原有本机上游 | 0 | 200 | 200 | 0 | 0.000261 | 0.078699 | 251 |
| 显式直连 | 0 | 200 | 0 | 0 | 0.003315 | 0.079645 | 251 |

### 复现与一次边界

只读查看方案（本轮已经执行，不读候选、不联网）：

```bash
cd /Users/chenge/project/liumo
.venv/bin/python -m validation.functional_check --observation-plan
```

新授权后的执行入口为 --observation-once，缺少本机私有授权记录时停止，不自动生成授权。它使用同一个 C17 候选、同文正文最多一次，身份通过后评论最多一次，每次 20 秒；不重采、不改系统，不发列表或配图请求，不切换上游或匿名回退。新的一次标记／结果与原 C17 分开，失败也消耗尝试。具体授权字段、路径、验收和失败处理见 [C18 清单](/Users/chenge/project/liumo/goals/20261017-1606-wechat-session-validation.md#c18传输观测补齐与无凭证只读对照) 。用户已在普通终端执行，正文 1 次／评论 0 次；回执为 HTTP 200、收到 2 MiB 后 curl 56，旧入口不再执行。

完整回归 257 项：253 通过、4 跳过。新增四项覆盖传输失败时固定观测与部分响应拒绝、错误分类和数值边界脱敏、未授权前不读凭证／不建标记、新授权作用域与独立一次标记；均为构造验证。真实凭证观测、评论与原页截图仍未通过。[证据与当前代码哈希](/Users/chenge/project/liumo/evidence/feasibility/article-transport-observation.json) 。

### C18 原启动方式（已消耗，不再执行）

当前 Agent 环境连接原本机上游被权限拒绝（errno 1）；这不是 HTTP、TLS 或服务端凭证结论。未调用真实功能入口，独立一次标记不存在。此为执行时的启动记录；现已取得普通终端结果，命令不可再次执行：

```bash
cd /Users/chenge/project/liumo
.venv/bin/python -m validation.functional_check --observation-once
```

成功／失败都保存独立的 functional-observation-result.json 与新归档摘要；不要重跑原无参数入口。完成后由 Agent 审阅数值观测、正文独立身份与评论结果；失败不自动重试或重采。代码未改变，沿用已核对哈希的 257 项测试基线，没有重复测试。

## C18 真实结果与尺寸边界

2026-10-18 18:07：C18 普通终端已结束：同文正文请求 1、评论 0；CONNECT／HTTP 均 200，证书校验数值 0、TLS 连接约 0.085 秒，下载恰为 2 MiB 上限后 curl 56。正文身份与完整性未验收，不能认定凭证有效或过期；尺寸边界为线索，尚非根因。原 C17 与 C18 回执保全，不重跑。已交付无凭证离线尺寸探针与固定观测回归，260 项为 256 通过、4 跳过；Agent 的 Unix socket 预检 errno 1，五个本机 curl 构造场景尚未实测，下一步仅普通终端运行离线探针，无外网／凭证请求或系统变更。原 Goal 仍 blocked、未完成。[现场证据](/Users/chenge/project/liumo/evidence/feasibility/article-transport-observation-live.json) 。

| 项目 | 实际结果 |
| --- | --- |
| 普通终端请求时间 | 2026-10-18 18:01:00 至 18:01:01，北京时间 |
| 代理 CONNECT／HTTP | 200／200 |
| TCP／TLS 连接秒数 | 0.000165／0.084692 |
| 证书校验数值 | 0 |
| 下载字节／程序上限 | 2097152／2097152 |
| curl 退出／固定错误类别 | 56／other |
| 正文身份／评论请求 | 未验收／0 |

本次已经收到 HTTP 响应及数据，不能再解释为完全未建立连接。数据大小恰好触及上限，值得优先核对本地尺寸边界；但没有保存原错误、完整响应及传输编码，不能断定 56 是超限造成，也不能确认这是正常文章或受限页面。C17 未保留阶段数据，本次结果不能回填到上一次。

访问日期 2026-10-18：固定版本 [curl-8_7_1 的下载写入器](https://github.com/curl/curl/blob/curl-8_7_1/lib/sendf.c#L254) 在超限分支写出允许的字节后返回 63；[分块解码器](https://github.com/curl/curl/blob/curl-8_7_1/lib/http_chunks.c#L395) 传递下游错误；[该版本 max-filesize 文档](https://github.com/curl/curl/blob/curl-8_7_1/docs/cmdline-opts/max-filesize.md) 也列出 63。它们提供待比对的预期，并未证明本机 Apple 构建与上游完全一致，因此不能用源码把真实 56 直接改判为 63。

程序现增加尺寸触顶的固定观测和明确尺寸错误类别，但没有追补旧回执、提高 2 MiB 上限或重发请求。完整回归 260 项，256 通过、4 跳过；新三项覆盖触顶不等于成功、构造刺激的实际字节与分块终止、权限失败不调用原生 HTTP 或换传输。

### 本机 curl 离线核对（已取得普通终端结果）

Agent 创建 Unix socket 被权限拒绝（errno 1）的旧结果保留；之后用户普通终端已执行以下命令，五个场景均符合预期，无需重跑：

```bash
cd /Users/chenge/project/liumo
.venv/bin/python -m validation.curl_size_probe
```

只用本机私有 Unix socket 的构造 HTTP，不访问微信、互联网或原代理，不读取任何凭证、不改系统设置；五个场景独立记录退出码与字节，完成后自动清理临时 socket。摘要归档到新建的 archives/feasibility/*-curl-size-offline/size-summary.json；CLI 显示 observed 只代表取得观测，是否符合上游预期由独立字段记录，不等于 HTTPS 或账号验证通过。

离线结果确定后再选择修正尺寸预算或其他传输差异；任何追加带凭证请求均须新限定授权，不能重置 C18 标记。本轮系统恢复记录保持通过，未新增系统改动。

## C19：离线结论与单变量正文核对

2026-10-18 18:12：用户普通终端的五个离线尺寸场景均符合预期：超限 63、恰好 2 MiB 成功、提前中断 18；未复现真实 C18 的 56，不能认定尺寸为根因，也未测试 TLS／账号。C19 单变量入口已准备：仅正文上限由 2 MiB 改为 10 MiB，评论仍 2 MiB，同候选正文／条件满足后的评论各最多 1 次、每次 20 秒，原上游／TLS／请求字段不变。264 项回归为 260 通过、4 跳过；真实执行待新授权，未生成 C19 授权或发请求，旧 C17／C18 保全。原 Goal 仍 blocked、未完成。[准备证据](/Users/chenge/project/liumo/evidence/feasibility/article-bounded-body-preparation.json) 。

本机 curl 8.7.1 在北京时间 2026-10-18 18:08:14 的构造观测如下，均无外网／凭证请求。已核对离线程序哈希与 260 项基线一致，实际归档与固定数值已保存至 [C18 现场索引](/Users/chenge/project/liumo/evidence/feasibility/article-transport-observation-live.json) 。

| 固定场景 | HTTP | curl 退出 | 下载字节 | 核对 |
| --- | --- | --- | --- | --- |
| 小响应 | 200 | 0 | 2 | 符合预期 |
| 已知长度超过 2 MiB | 200 | 63 | 0 | 符合预期 |
| 分块超过 2 MiB | 200 | 63 | 2097152 | 符合预期 |
| 分块恰好 2 MiB | 200 | 0 | 2097152 | 符合预期 |
| 分块提前断开 | 200 | 18 | 20 | 符合预期 |

该结果只支持普通构造 HTTP 的上述行为，没有重现微信 HTTPS／原代理条件下的 56。尺寸触顶线索仍保留，不能写成凭证失效、纯尺寸根因或 TLS／代理故障的结论。当前窄检索没有找到能直接解释本次组合的一手已知问题，不据此扩展调研或切换技术栈。

下一步采用单变量对照，目标是取得可独立校验的完整正文：仅正文预算由 2 MiB 调到 10 MiB，量级沿用已有 WechatHTTP.read 的默认正文预算；评论仍 2 MiB。仍只有同候选正文至多 1 次，HTML 号／文章／标题独立一致后评论至多 1 次，每次 20 秒。上游、TLS、请求头、参数、无重试／重定向及其他边界不变。结果成功也只验收正文身份和评论快照分项，不验收配图、原页单图或追更。

只读复现方案（已运行，不读凭证或联网）：

```bash
cd /Users/chenge/project/liumo
.venv/bin/python -m validation.functional_check --bounded-body-plan
```

实际入口 --bounded-body-once 必须在新授权之后使用。私有授权记录固定为 experiment=c19_bounded_body、source=explicit_user_grant、授权时刻、正文／评论各 1 次、同候选、正文 10485760／评论 2097152 字节，并绑定 C18 结果 SHA-256。新标记／结果为 functional-bounded-body-attempt.json／functional-bounded-body-result.json；原 C17、C18 不重置。缺记录或哈希／预算不符时不读候选或发请求，失败不重试或重采。[施工与验收边界](/Users/chenge/project/liumo/goals/20261017-1606-wechat-session-validation.md#c19正文尺寸单变量核对) 。

完整回归 264 项为 260 通过、4 跳过；新增四项验证超过 2 MiB 的完整构造 HTML 可独立校验、评论预算不变、默认／无效／超限／非零退出拒绝、未授权时不触及凭证、授权绑定回执及新旧标记保全。真实 C19 仍未执行；无需先刷新微信、扫码、采集或修改系统。

### C19 单次启动记录（已消耗，不重跑）

本次授权已记录并绑定 C18 回执，Agent 连接原本机上游的 TCP 预检仍被权限拒绝（errno 1）。没有调用真实入口、读取候选值或消耗尝试；不换传输或绕过限制。用户之后已在普通终端执行并返回 302；以下为历史启动命令，不再执行：

```bash
cd /Users/chenge/project/liumo
.venv/bin/python -m validation.functional_check --bounded-body-once
```

结束后审阅独立结果 functional-bounded-body-result.json 及 archives/feasibility/*-article-functional-bounded-body/functional-summary.json。成功也须按正文身份、评论、配图与原页截图分项判断；失败停止，不再执行原 C17／C18 入口或重置标记。

## C20：正文鉴权构造差异与修正

2026-10-18 18:21：C19 普通终端传输成功但 HTTP 302，正文请求 1、评论 0、2252 字节，未触及 10 MiB 上限，未跟随；Location 未保存，去向及原因未知，不能认定凭证失效或尺寸修正有效。离线逐字段复核固定 exporter 源码后，已纠正正文构造差异：公开文章 URL 加 pass_ticket／wap_sid2 Cookie，不再追加四项 API 鉴权 query，评论 API 不变。该差异仍不是旧 302 的根因证明。268 项回归为 264 通过、4 跳过；C20 固定入口与验收已交付，真实请求待新授权，旧三次回执保全。原 Goal 仍 blocked、未完成。[准备证据](/Users/chenge/project/liumo/evidence/feasibility/article-cookie-body-preparation.json) 。

C19 于北京时间 2026-10-18 18:15:02 至 18:15:03 完成：curl 退出 0，CONNECT 200、HTTP 302，证书校验数值 0，TLS 约 0.083 秒，下载 2252 字节。没有跟随重定向或发评论，正文身份未验收。它与 C18 不同，不是又一次传输 56；服务器状态也发生变化，不能据此证明提高尺寸预算修复了原问题。Location 未保存，不能解释为登录跳转、验证页或同文正常跳转。

### 固定源码复核

复核日期 2026-10-18；沿用 2026-10-17 下载的固定提交 152f23832c7f3664b86148e84bd3f75e513e4dd2，三个缓存 SHA-256 与旧索引一致，没有执行上游代码或查询新版本。参考 [BaseDownloader.ts:143-155](https://github.com/wechat-article/wechat-article-exporter/blob/152f23832c7f3664b86148e84bd3f75e513e4dd2/utils/download/BaseDownloader.ts#L143) 、[CredentialsDialog.vue:395-400](https://github.com/wechat-article/wechat-article-exporter/blob/152f23832c7f3664b86148e84bd3f75e513e4dd2/components/global/CredentialsDialog.vue#L395) 与 [Downloader.ts:167](https://github.com/wechat-article/wechat-article-exporter/blob/152f23832c7f3664b86148e84bd3f75e513e4dd2/utils/download/Downloader.ts#L167) 。只借鉴协议，自行实现请求构造。

| 字段／行为 | C17 至 C19 实际实现 | 固定参考的带凭证正文路径／当前修正 |
| --- | --- | --- |
| 正文 URL | 文章标识加 uin、key、pass_ticket、appmsg_token | 保留经本次身份校验的公开文章 URL，不追加四项 API 参数 |
| 正文 Cookie | 采集白名单 Cookie | 仅 pass_ticket 与 wap_sid2 |
| pass_ticket 来源 | query 解码后的凭证字段 | 参考 URLSearchParams.get 的解码字段，使用同一凭证字段 |
| wap_sid2 来源 | 保存于白名单 Cookie | 从白名单 Cookie 提取，不解码或改写 opaque 值 |
| 评论请求 | 既有 API query 与 Cookie | 保持原有字段与次数限制 |
| UA／Referer 与上游传输 | 留墨既有显式 UA／Referer、本机上游 | 本轮保持不变；未证明与原微信或上游代理完全等价 |

此前正文验证程序确实偏离了固定参考的这条带凭证分支，现已纠正；该差异尚未通过服务端对照，不能写成 302 根因。公开文章 URL 由既有白名单从原请求规范化取得，完整原 query／headers 未保留，因此不能声称逐字重放了微信原请求。普通文章的上游默认路径还可能不附凭证，本次不匿名回退，不冒称已走过该分支。

本机固定候选具备必需字段，已在内存中构造成功，仅输出固定布尔值；没有输出 Cookie 或令牌、改写凭证文件或访问网络。字段缺失、Cookie 分隔符／控制字符等无效输入会在请求前停止。

### 下一步：新授权后的有限核对

只读方案已执行，不读凭证、不联网：

```bash
cd /Users/chenge/project/liumo
.venv/bin/python -m validation.functional_check --cookie-body-plan
```

真实入口 --cookie-body-once 需要新明确授权和私有 functional-cookie-body-authorization.json，绑定 C19 回执 SHA-256、固定候选、正文／评论各 1 次、正文 10 MiB／评论 2 MiB。仍每次最多 20 秒，身份通过后才请求评论；不重采、不改系统、不跟随 302、不重试或匿名回退。标记与结果分别为 functional-cookie-body-attempt.json／functional-cookie-body-result.json，旧三次均不可重跑。[C20 施工边界](/Users/chenge/project/liumo/goals/20261017-1606-wechat-session-validation.md#c20纠正正文鉴权构造) 。

完整回归 268 项为 264 通过、4 跳过。新增四项核对实际正文／评论构造字段分离、缺失或恶意 Cookie 零请求、未授权不读候选，以及 C19 回执绑定和旧三次标记保全。真实 C20 未授权、未执行；正文、评论、原页截图和自动发现仍未通过。

### C20 单次启动记录（已消耗，不重跑）

本次授权已记录并绑定 C19 回执。Agent 对原本机上游的 TCP 预检 errno 1，未调用真实入口或读取候选值，尝试未消耗；没有改用其他传输。用户之后已执行，结果为正文通过、评论 -3；以下只保留历史启动命令，不再执行：

```bash
cd /Users/chenge/project/liumo
.venv/bin/python -m validation.functional_check --cookie-body-once
```

结果保存在独立 functional-cookie-body-result.json 及 archives/feasibility/*-article-functional-cookie-body/functional-summary.json；旧三次不重跑。按正文独立身份、评论快照与未验的图片／截图分别判断，失败停止，不重试或再采集。

## C20 实际结果与当前卡点

2026-10-18 18:47：C20 普通终端取得 HTTP 200、3493257 字节正文，完整传输及号／文章／标题的独立 HTML 身份门槛通过；这份响应约 3.33 MiB，确实超过旧 2 MiB 预算，但不能反推旧 56／302 根因或证明 Cookie 必需。评论请求 HTTP 200／业务码 -3，快照失败、保存 0 条，整体 partial；不是文章无留言。正文／评论各 1 次已消耗，旧结果保全，不再复用该候选重试。本次只保存功能摘要与失败评论快照，未保存 HTML 或生成 Markdown／本地配图／原页截图。离线 18 项评论 query 语义及 UA 与固定参考一致，当前 token 无百分号解码差异；完整 Cookie、响应 Cookie 更新及正常微信成功评论请求仍无对照，-3 原因未知。50 份代码哈希符合 268 项基线，未重复测试；原 Goal 仍 blocked、未完成。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/article-cookie-body-live.json) 。

| 验证项 | 实际结果与边界 |
| --- | --- |
| 正文传输 | curl 0／CONNECT 200／HTTP 200，3493257 字节，未触顶 10 MiB |
| 正文身份 | 已测程序独立核对 HTML 中号、文章及标题通过，不使用请求 URL 掩盖身份 |
| 评论传输 | curl 0／CONNECT 200／HTTP 200，111 字节 |
| 评论业务与快照 | -3／failed，保存 0 条，不算无留言或完整快照 |
| 实际请求 | 正文 1／评论 1，无后续重试、跟随或新采集 |
| 本次产物 | functional-summary.json 与失败的 comments.json；没有持久化正文 HTML、Markdown、配图或截图 |
| 整体 | partial，原 Goal 未完成 |

回执时间为北京时间 2026-10-18 18:42:42。本次正文响应约 3.33 MiB，说明旧 2 MiB 上限不足以容纳这份响应；但不同时间、请求构造和服务器状态都曾变化，不能据此证明旧 curl 56／302 的单一原因。正文在 Cookie 条件下可读，也不证明 Cookie 必需或评论鉴权有效；本轮没有匿名对照。

### 评论协议离线核对

使用构造凭证与 comment_id，不请求服务器，逐字段核对固定 exporter 下载器：18 个 query 字段的解码语义、微信 UA 字面值及 Referer 对齐；当前真实候选的 appmsg_token 与 Cookie 值相同，百分号解码不改变其值，不能再用“漏解码”解释本次 -3。固定源码版本与哈希沿用 C20 的证据索引，未执行上游代码。

尚有明确证据边界：留墨显式 Accept 为 application/json；上游源码未显式设置该头，但代理实际发出的默认头未验证。留墨保存四种白名单 Cookie，原微信与参考代理完整 Cookie 未保留；本次正文响应的 Set-Cookie 更新也未观测。它们都是待比对条件，不是已确定的拒绝原因。完整审计见 [真实索引](/Users/chenge/project/liumo/evidence/feasibility/article-cookie-body-live.json) 。

当前应停止复用旧候选盲试。下一项需要同一文章在正常微信里**成功加载评论**时的实际请求与响应数字基线，以便对照字段来源、编码、必要头部及会话更新；仅截图看到留言不等于已有这份网络证据，但不要求用户重复证明有留言。

后续先形成独立限定方案及实现、自测，再按具体范围申请真实采集或系统变更授权。当前没有新实验、没有追加请求，也没有需要用户重复运行的命令。正文 Markdown／配图／截图及自动发现仍按原验收推进，不能用正文成功替代评论或自动追更。
