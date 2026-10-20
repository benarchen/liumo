# 当前 Mac 微信主页通道：证据复核

## C20：正文读取分项通过，评论快照失败

2026-10-18 18:47：C20 普通终端取得 HTTP 200、3493257 字节正文，完整传输及号／文章／标题的独立 HTML 身份门槛通过；这份响应约 3.33 MiB，确实超过旧 2 MiB 预算，但不能反推旧 56／302 根因或证明 Cookie 必需。评论请求 HTTP 200／业务码 -3，快照失败、保存 0 条，整体 partial；不是文章无留言。正文／评论各 1 次已消耗，旧结果保全，不再复用该候选重试。本次只保存功能摘要与失败评论快照，未保存 HTML 或生成 Markdown／本地配图／原页截图。离线 18 项评论 query 语义及 UA 与固定参考一致，当前 token 无百分号解码差异；完整 Cookie、响应 Cookie 更新及正常微信成功评论请求仍无对照，-3 原因未知。50 份代码哈希符合 268 项基线，未重复测试；原 Goal 仍 blocked、未完成。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/article-cookie-body-live.json) 。

## C16：单篇文章兼容与恢复实测通过

2026-10-18 16:08：C16 单次文章兼容与限时收尾通过。普通终端启动后，安装前对照／不信任及安装后 17 项范围检查成立；控制 HTTP 200、代理控制计数各 1。Agent 对猫笔刀固定文章正常刷新一次，页面可读且未见证书警告；文章请求／响应从 0 增至各 1，普通目标域从 0 增至各 20，TLS 失败计数均为 0。约 60.3 秒完成代理回读恢复、明确有效撤销、进程停止及两份私钥删除，180 秒窗口内收尾通过。未采凭证或发列表／评论探针，不证明旧错误的唯一根因、两号兼容或凭证功能；236 项基线哈希未变，未重复运行代码测试。C16 已关闭，不重跑；原 Goal 未完成。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-compat-live.json) 。

## C15：安装约束与后续撤销已分别取得证据

2026-10-18 15:14：C15 普通终端安装后 17 项约束通过；后续独立恢复已取得证书不存在及带根链目标明确不信任 （-67843／信任结果 5），本次有效撤销验收通过，无需继续运行命令。撤销验收在信任开始 125.8 秒后完成，原 120 秒自动收尾未通过，不补记为成功。已修正自动／独立撤销各命令 30 秒认证预算，并将自动流程收尾预留增至 70 秒；216 项回归为 212 通过、4 跳过。预算修正仅经构造测试，未重装或重跑系统实验。微信兼容、无人值守追更及原 Goal 仍未完成。[现场证据](/Users/chenge/project/liumo/evidence/feasibility/installed-anchor-live.json) 。

核对时间：2026-10-18（北京时间）。本轮为 C11，只读公开资料和本机应用版本；未启动采集、修改证书／代理、读取微信账号数据或发起微信接口请求。原 Goal 未完成。

## C14 原生校验诊断

2026-10-18 14:45：已核对普通终端 C14 离线结果。macOS 正对照退出 0、信任结果 4，CT 提示与成功决定并存；两个验证器各 51 项均取得结果，改进候选各 17 项符合预期，朴素方案各有 7 个范围遗漏。未安装信任、改代理或访问微信。程序／测试 38 份哈希与 200 项回归基线一致，未重复运行。显式根结果不等于安装后信任或微信兼容；新证书亦使本次不能单独证明旧 Agent 内部错误的根因。该离线检查点完成，原 Goal 仍 blocked、未完成。[终端证据](/Users/chenge/project/liumo/evidence/feasibility/native-control-terminal.json) 。

## C13 离线进展

2026-10-18 12:38：C13 离线证书探针已交付。OpenSSL 3.6.3 下改进候选的 17 个场景符合预期，朴素 DNS 许可方案有 7 个范围遗漏；macOS 显式根正对照退出 1、含 CT／SCT 提示，未执行后续矩阵，不算约束通过。198 项回归为 194 通过、4 跳过。未安装信任、改代理、访问微信或保留私钥；没有新增微信功能通过项。整体 partial，原 Goal 仍 blocked、未完成。[离线报告](/Users/chenge/project/liumo/docs/certificate-scope-offline.md) 、[证据](/Users/chenge/project/liumo/evidence/feasibility/certificate-scope-offline.json) 。

## C12 补充实测：文章浏览器拒绝本次证书

用户另行授权后，已完成一次独立 120 秒文章页对照。C11 的只读边界与证据保留；以下为新增真实证据，不将其追补到旧实验。

| 项目 | 结果 |
| --- | --- |
| 目标与 UI | Agent 实际截图确认猫笔刀《上个月最值的一笔消费》，留言角标 33，无聊天可见；不是含评论完整截图验收 |
| 控制 | HTTP 200；代理侧控制请求／响应各 1，curl 使用本次显式 CA，不证明微信浏览器信任 |
| 刷新前 | 北京时间 12:21:49，普通目标 HTTP、文章 HTTP、目标 TLS 失败均为 0 |
| 唯一刷新 | 12:22:02.688 至 12:22:02.725，Agent 成功发送一次 ⌘R，标签显示加载指示 |
| 刷新后 | 12:22:10 取样：目标客户端 certificate_alert 增至 15，普通目标 HTTP／文章 HTTP 仍为 0；12:22:32 后续取样及结束时未再增加 |
| 页面 | 隐私错误页明确显示 mp.weixin.qq.com 的 NET::ERR_CERT_AUTHORITY_INVALID；未点击高级、绕过警告、重复刷新或放宽信任 |
| 收尾 | 到期结束；代理原值恢复回读、临时信任撤销检查、进程停止均通过，保存凭证为空、requests 目录不存在 |

现场证据、时间、校验值与独立归档摘要见 [C12 索引](/Users/chenge/project/liumo/evidence/feasibility/wechat-article-diagnostic-live.json) 。原始 UI 图片仅存在本会话工具输出，未声称另有本地错误截图；本机归档保留取样和文字观察。系统恢复通过不代表错误页面已经重新加载为原文，本轮结束后未再次刷新。

**已实测结论：当前临时信任配置未被该文章浏览器接受，文章 HTTP 观测失败。** 这不是文章没有评论、登录过期或微信服务端业务拒绝的证据。不能用它解释此前主页无 HTTP 的全部原因，也不能直接宣称证书固定或扩大信任即可解决。

## C12 后的只读机制核对

2026-10-18 再查 Chromium 一手源码：`net/cert/internal/trust_store_mac.cc` 的 `IsTrustDictionaryTrustedForPolicy` 遇到 `kSecTrustSettingsPolicyString` 时返回未指定信任；该字段可用于主机名等策略约束。[固定提交 8efc7fd74724da62278f01e46e60432fd868f1ab，第 78 至 85 行附近](https://chromium.googlesource.com/chromium/src/+/8efc7fd74724da62278f01e46e60432fd868f1ab/net/cert/internal/trust_store_mac.cc#78) 。当天读取的 [main 文件](https://chromium.googlesource.com/chromium/src/+/main/net/cert/internal/trust_store_mac.cc) 仍有相同分支，页面显示 blob `5bb8181f318983f7108bcfca5b911a1fed1ce582`；固定提交文件 blob 为 `bf099d3cd4fbd826bec414ea7d1bc0eb3e4e775b`。main 提交页与固定当前提交文件的交叉读取未全部成功，不将分支内容冒充最新提交逐字核验。

本机只读命令 `/usr/bin/security help add-trusted-cert` 确认 `-s` 为策略字符串；留墨 `Native.trust()` 正使用 `-p ssl -s mp.weixin.qq.com`。因此，“浏览器信任实现不支持该主机限定项”是有源码依据的兼容性假设。**未核实当前微信的内核版本和证书验证调用路径，不能标记为根因已确认。** 上游教程的系统级信任方案也未实测，不自动采用。[wxdown 教程](https://docs.mptext.top/advanced/wxdown-service) 。

当前不重跑代理实验。下一步先离线评估能否保留域名限制并兼容浏览器的证书方案；必须分别证明证书约束、实际客户端接受和恢复能力，不能只凭系统 verify-cert 通过。若需要移除主机限定、扩大系统信任或重启微信，先形成具体差异和恢复方案，取得对应授权。后台登录来源仍是登录前提不同的备选，不自动替换用户已确认需求。列表、评论、原页单图及自动续期均未通过，原 Goal 保持未完成。

## 结论

现有公开参考不足以建立本机微信 4.1.15（270100）公众号主页的请求路径。wxdown-service 证明的是文章访问时取得阅读凭证的实现，exporter 提供的是已有凭证的列表请求封装；两者都不能直接证明当前 Mac 主页使用 `/mp/profile_ext`。停止原样重跑 C10，也不猜测新端点。

发现了具体条件差异：上游教程同时设置 HTTP／HTTPS 代理，并要求系统级证书信任；留墨此前实验只改当前服务的 HTTPS 代理，临时信任限定在用户级和目标主机。这些是授权和数据保护边界，不能为贴近教程而自动放宽。差异尚不是失败根因证据。

## 证据与适用范围

以下链接均于 2026-10-18 访问；“源码／文档”不等于留墨实测成功。来源及本地固定源码校验值见 [索引](/Users/chenge/project/liumo/evidence/feasibility/wechat-profile-route-review.json) 。

| 证据 | 实际支持 | 不支持的推论 |
| --- | --- | --- |
| 本机应用 Info.plist | 微信 4.1.15，构建 270100 | 不证明网络协议或凭证有效性 |
| [wxdown 官方教程](https://docs.mptext.top/advanced/wxdown-service) | Mac 配置步骤要求 HTTP 和 HTTPS 代理、系统钥匙串信任；操作对象是文章阅读页 | 不证明当前构建的公众号主页能被同样观察 |
| [wxdown 固定凭证插件](https://github.com/wechat-article/wxdown-service/blob/28feff2095359acb158f856c40b357e77b686d2c/resources/credential.py) | 匹配 `/s` 且查询以 `__biz=` 开头，读取文章响应的 Set-Cookie；没有主页列表捕获逻辑 | 不证明凭证可跨用途调用列表、自动续期或原页含评论截图 |
| [exporter 固定列表封装](https://github.com/wechat-article/wechat-article-exporter/blob/152f23832c7f3664b86148e84bd3f75e513e4dd2/server/api/web/mp/profile_ext_getmsg.get.ts) | 使用调用方提供的 uin／key／pass_ticket 调用 getmsg，含 offset／count | 不负责当前 Mac 正常主页初始化；本次新网页读取失败，复用既有固定源码缓存，未称远端重新核对通过 |
| [exporter 后台列表封装](https://github.com/wechat-article/wechat-article-exporter/blob/152f23832c7f3664b86148e84bd3f75e513e4dd2/server/api/web/mp/appmsgpublish.get.ts) | 另一条后台 Cookie／token、fakeid、begin／count 路线 | 不等于复用 Mac 微信在线会话；登录、权限和当前可用性须另验 |
| [exporter 维护者说明](https://github.com/wechat-article/wechat-article-exporter/issues/200) | 维护者报告核心上游关闭、Credential 路线未整合，并停止维护 | 不能据此认定所有微信接口永久不可用 |
| [腾讯 Mars 文档](https://github.com/Tencent/mars) | 腾讯公开网络组件包含 STN 长短连接等能力 | 不能证明当前公众号主页使用 Mars／MMTLS、某个域名或绕开系统代理 |
| [C10 现场索引](/Users/chenge/project/liumo/evidence/feasibility/wechat-ui-diagnostic-live.json) | 一次主页 UI 重载可见，控制通过，普通目标域 HTTP 无增量；唯一证书告警在刷新前 | 不能把该告警归因本次刷新，不能认定缓存、证书固定、账号限制或实际传输协议 |

wxdown 参考版本为 v0.27.1／`28feff2095359acb158f856c40b357e77b686d2c`；exporter 为 2.3.21／`152f23832c7f3664b86148e84bd3f75e513e4dd2`。当前提交页可以读取，但 GitHub API 的三次公开提交查询均返回 HTTP 403，未取得可独立校验的最新 HEAD。固定版本不能表述为当前最新版本。

两轮窄检索未找到当前 Mac 构建主页路径的直接证据，停止泛搜。客户端注入、读取本机缓存／内存、私有网关等不纳入实施；没有运行或安装参考项目。固定源码缓存与此前索引散列一致，只证明缓存未变，不冒充重新下载或真实功能通过。

## C11 时的分支记录（文章对照已在 C12 结束）

1. 当前不再刷新主页、不重启旧实验。现有文章凭证在列表调用中的失败结果继续有效，不能再把取得凭证当来源验收完成。
2. 若继续验证本机阅读凭证，应先做“文章页”与“主页”的受控对照，严格保持原有信任／代理范围：先确认上游实际支持的文章页能否产生目标域 HTTP，再判断主页假设。即使文章通过，也不能直接通过列表、评论或自动续期。它仍是新的系统实验，须先准备独立目录、120 秒控制器、恢复与验收，再取得该次明确授权；本轮没有启动，也不要求用户先开页面。
3. 不建议直接把 HTTP 代理和系统级信任一起放宽：一次改变多个条件无法定位原因，且扩大系统影响。当前没有支持该扩大的实证。
4. 若不继续本机代理实验，现有参考中可独立核对的替代是公众号后台登录列表路线。它改变登录前提，需要先确认用户是否具备并愿意使用该后台，不能擅自登录或将其选为正式方案。微信读书已有扫码反馈继续有效，但仍缺两个号的正常标识和多页覆盖证据，不要求重复扫码或手抄令牌。

现阶段没有足够证据交付“每天无人值守追更＋含评论单图”的可靠技术路线。来源与归档仍须分别验收；不缩减产品要求，不将新调研标记为功能通过。

## 本轮交付检查

新增本报告与脱敏来源索引，更新产品设计、Roadmap 和两份 Goal 记录及阶段说明。运行代码未改，不重复运行既有 188 项测试；历史结果仍为 184 通过、4 跳过。文档／链接和证据一致性检查结果保存在本轮索引，不能作为真实微信功能通过。
