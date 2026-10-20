# 自研 HTTP 路线：运行与证据边界

用户已确认按 exporter 的机制思路推进，业务代码全部由留墨自行编写。没有复制、导入或执行 exporter／wxdown-service 业务源码；HTTP 请求中的接口名、字段和兼容请求头是协议参考。HTTP 路径继续使用 Python、标准库、既有 BeautifulSoup／markdownify 与 Playwright。本机凭证实验另在 `.venv-capture/` 隔离安装成熟 TLS 组件，见 [阶段报告](/Users/chenge/project/liumo/docs/wechat-session-validation.md) ，不改变 HTTP 主程序依赖。

## 当前入口

在项目根目录运行：

```bash
.venv/bin/python -m validation http-fixture
.venv/bin/python -m unittest discover -s tests -v
```

`http-fixture` 只处理 [构造 HTML](/Users/chenge/project/liumo/examples/pages/http-article.html) 与 [构造接口响应](/Users/chenge/project/liumo/examples/comment-pages.json) ，不访问网络。它保存 Markdown、一张本地配图、两页构造留言及两次补取的回复；回复按 ID 合并，保留原内嵌回复。产物写入新的 `archives/feasibility/*-http-fixture/`。该命令预期退出码为 2：HTTP 层成功不代表原页截图、发布时间和浏览器可见性通过，整体仍为 partial。

具备正常访问条件后，真实技术样本的入口为：

```bash
.venv/bin/python -m validation http-archive --sample maobidao
.venv/bin/python -m validation http-archive --sample stormzhang
.venv/bin/python -m validation mp-discover --account 猫笔刀 --max-pages 3
```

这些是当前程序入口，不代表已经实测通过。本轮没有重复此前返回限制页的两个匿名样本，没有新发起扫码；原页截图仍使用 README 已有的独立浏览器入口，未改成接口重建页面截图。所有样本仍不是正式订阅或历史补抓。

## 模块与行为

| 模块 | 已实现行为 | 限制 |
| --- | --- | --- |
| `validation/http.py` | 标准库直接 HTTPS，默认校验证书，仅指定腾讯文章／图片域名，无环境代理、重定向和自动重试；API 请求串行且间隔至少 2 秒 | 兼容 UA 和字段值来自固定研究证据，真实请求已取得响应但目标功能未通过；传输可达不代表认证有效 |
| `validation/http_archive.py` | 静态提取标题、公众号、正文和公开身份候选，复用自研 Markdown／图片落盘；不执行脚本；受限、未知模板和付费预览明确失败 | 仅支持有 `#js_content` 的当前验证结构；不承诺所有模板或 CSS 计算可见性；不能据此标整篇完成 |
| `validation/comments.py` | 按留言游标分页，回复按稳定 ID 合并并核对数量，有限补取；游标停滞、跨页失败、访问状态不明、业务拒绝及范围变化可见，已取得内容保留 | 超过一页的回复续取是待真实协议核对的实现；当前范围为 elected_comments，其他评论区域出现时标部分成功；不代表原页可见范围 |
| `validation/mp_source.py` | Credential 列表候选，解析群发中的多篇及 offset 分页，过滤链接凭证，失败保留已取得页 | 身份、时间、覆盖仍未验；时间始终 `time_verified: false`，不能直接推进增量位置 |
| `validation/credentials.py` | 读取两个目标号指定的项目私有输入；受限写锁与原子落盘只轮换本模块管理的同身份文件；拒绝符号链接、非当前用户、宽松权限及控制字符 | 不验证服务端期限，也不读取微信或其他应用账号；真实写入须符合当次采集授权 |

## 列表结构诊断

```bash
.venv/bin/python -m validation mp-diagnose --account all --transport curl
```

`all` 固定为两个目标号，各一次第一页，间隔 2 秒，不分页或下载正文。缺凭证时该号零请求；业务拒绝、解析失败或传输失败均停止该号，不重试。只记录固定字段的存在性、类型、有限数字、列表长度与最多 3 条结构样本，不输出任意上游键名、文章／读者内容、错误文本、Cookie 或 token。解析成功也只表示结构观察，不证明账号身份、时间语义、完整覆盖或认证可持续。

原 `mp-discover` 的结构失败现在同时保留脱敏 shape；畸形嵌套字段不再导致诊断文件缺失，前页结果继续保留。真实缺失字段已观察，具体原因仍未知，没有放宽解析规则或把缺失字段补成成功。

2026-10-17 17:45 的普通终端诊断已取得两号结构：ret=0、can_msg_continue=0，但 general_msg_list 和 next_offset 均缺失。新增 `source_list_missing` 分类及对应最小构造样本，不将缺字段补成空列表，不推进完整检查位置。原结构诊断证据保持原样；这不证明账号认证有效、无新文章或接口永久关闭。两轮未取得列表后停止相同请求，具体原因尚未确定。

显式 curl 使用系统已有组件，不安装依赖。配置经 stdin，禁用个人配置、代理、重定向／重试及 TLS keylog 环境，仍要求 HTTPS 与目标域白名单；10 MiB 大小及 20 秒时限由 curl 限制，程序再检查状态与大小。依据为 [curl 官方手册的 config、disable、max-filesize 与 max-time 选项](https://curl.se/docs/manpage.html) ，访问日期 2026-10-17。Python 路径使用本机 Python 3.14 默认客户端验证策略，但不启用 SSLKEYLOGFILE；两种传输都不关闭证书校验。

## 带凭证样本与原页验证

当前入口为 `sample-check --transport curl --browser`，也可用 `http-archive --sample maobidao --credentialed --transport curl` 单独核对一篇。原匿名入口保留，但本轮不重复使用。

- `load_sample_credentials` 在请求前核对目标号、biz、mid／idx 与现有捕获范围，不修改私有文件；缺 Cookie 或作用域不符时零请求。
- HTTP 正文使用已有 Cookie，参考固定 exporter 的 `downloadMetadataTask` → `download(..., true)` 的有凭证读取思路；自行实现直连，不采用其代理、重试、缓存覆盖或付费分支。未知／受限正文停止，不猜 comment_id。
- 正文作用域与署名通过后才请求评论；图片不携带 Cookie。每篇图片最多 10 次、评论与回复 API 合计最多 12 次，超限明确部分成功。原始 HTML 不落盘，credentialed 模式也不保存其散列；进入 Markdown 的微信链接剔除会话查询字段。
- HTTP 正文、配图、评论 API 和原页截图各自记录时间与结果。`sample_check.py` 不调发现来源，不自动判定完整归档；HTTP 拒绝／身份门槛不符或评论失败时不进入浏览器重试。
- 浏览器复用已有 `archive` 的滚动、展开、截图和加载范围核对，使用临时内存上下文与主机限定 Cookie，不复用其他应用会话、不写 profile、不修改截图 DOM。原 Cookie 属性没有采集，重建属性及局限写入元数据；页面公开标识无法核对时停止取证。它仍是待实测候选，不能据此宣称原页评论已可访问。

参考源码仍为 [固定 Downloader.ts](https://github.com/wechat-article/wechat-article-exporter/blob/152f23832c7f3664b86148e84bd3f75e513e4dd2/utils/download/Downloader.ts#L240) 与 [BaseDownloader.ts](https://github.com/wechat-article/wechat-article-exporter/blob/152f23832c7f3664b86148e84bd3f75e513e4dd2/utils/download/BaseDownloader.ts#L143) ，复核日期 2026-10-17。只借鉴请求与分层思路，代码全部自行编写。

## 本轮自主实测与前置会话

当前 C20 的猫笔刀固定样本已取得 HTTP 200、3493257 字节正文并通过独立 HTML 身份门槛；正文 URL 使用公开文章标识，Cookie 仅 pass_ticket／wap_sid2，不追加评论 API 鉴权 query。随后评论为 HTTP 200／业务码 -3，整体部分成功；该次只保存功能摘要与失败评论快照，没有持久化 HTML 或生成 Markdown／配图／截图。旧候选不再重试，下一项需正常微信成功评论请求的网络基线。详情见 [C20 真实结果](/Users/chenge/project/liumo/evidence/feasibility/article-cookie-body-live.json) 。下文 2026-10-17 的结果仅为前轮证据。

2026-10-17 的最新结果是两篇带凭证正文均 HTTP 302，严格同文校验未通过，未跟随，也未继续配图、评论或浏览器。列表头部已按固定参考一次性对齐 WAE UA、Origin、identity 编码及 Accept，移除参考备用请求未携带的阅读 Cookie；两号各一次均 HTTP 200／业务码 -3。没有已取得的真实列表、评论或完整截图，不据此断言接口关闭或凭证过期。具体目录、代码与测试散列见 [最新证据索引](/Users/chenge/project/liumo/evidence/feasibility/wechat-autonomous-validation.json) 。

`validation/curl_bridge.py` 是当前 Agent 调用已获准独立 curl 的任务适配：配置、响应和响应头经 0600 私有 FIFO，原始值只在内存，不存普通文件；数字回执须为当前用户 0600 文件。它不启动 curl、代理、监听端口或浏览器，不是常驻产品服务。桥模式需控制器消费状态中的 FIFO 并写入实际命令回执，不能作为普通终端的一键命令。早期本地回执权限及 EAGAIN 竞争失败已分离、修复和自测；未知请求结果不当作服务端拒绝。独立公开请求及真实受限结果证明这条已授权传输路径可达，不证明微信功能有效。

默认禁止跟随跳转。桥模式仅允许固定样本的一次同 HTTPS 主机、同短链路径或已知 biz／mid／idx 的规范链接跳转；混合身份、验证码、跨站或第二跳停止。本轮实际没有跳转通过该门槛，不保存 Location 的查询值。

另一个固定实现展示了正常主页先取得 poc_token／poc_sid 的前置步骤，来源和平台局限见 [阶段报告](/Users/chenge/project/liumo/docs/wechat-session-validation.md) 。自研 `profile_context.py` 只在主页公开 biz 与目标匹配且两个字段均存在时，才在本次内存中补入并各号请求一次列表。未执行上游代码、未扫描缓存、未保存新凭证。真实两号主页均 HTTP 200，但当前解析未识别到身份及这两个字段，列表各 0 次；不推断未保存的原始响应内容。

普通终端的可复现入口如下，使用标准 Python HTTPS，不自动切换传输；当前候选已失败，不要求用户再次执行：

```bash
.venv/bin/python -m validation profile-context
```

此命令两号各一次主页，最多再各一次列表，页间间隔 2 秒；敏感值只在内存／HTTPS。产物为 `archives/feasibility/*-profile-context-pair/contexts.json`，固定类型和布尔门槛，不含原始响应。整体为 not_verified／退出码 2；即使取得列表结构，也不能代替多篇覆盖、真实时间或续期验收。当前停止复用旧候选请求，下一项依赖新的正常主页／列表会话条件。

新的会话条件已按 C7 单独获准，`profile-capture-session` 会筛选正常主页／列表请求的最小字段，在独立私有目录保存，并在 30 秒新鲜度内每号只请求一次列表。它使用本次捕获的正常请求 UA 和必要字段，不读旧文章候选；过滤重建、身份、时间与完整追更分别验收。164 项必要自测中 160 通过、4 跳过，用户普通终端已运行到期，本次正常系统恢复通过，目标匹配与即时探针为 0；正常主页反馈已收到；响应计数在路径过滤前也为 0，路径／阶段及原因仍未定位。已补请求／响应和 TLS 主机类别的固定计数，仅本地回归通过，不重复实验。程序、隐私边界和本次独立恢复入口见 [操作说明](/Users/chenge/project/liumo/docs/wechat-session-operations.md) ，分级证据见 [C7 索引](/Users/chenge/project/liumo/evidence/feasibility/wechat-profile-session.json) 。

## 凭证输入边界

真实接口需要微信文章阅读凭证；微信读书 Cookie 与其不同，不会自动转换或混用。程序只识别以下指定文件：

- 猫笔刀：`/Users/chenge/project/liumo/.auth/wechat/maobidao.json`。
- stormzhang：`/Users/chenge/project/liumo/.auth/wechat/stormzhang.json`。

输入结构见 [脱敏示例](/Users/chenge/project/liumo/examples/wechat-credential.example.json) ，示例不能当有效凭证使用。HTTP 读取命令不创建或复制凭证；另行显式启用且获准的采集器才可新建或轮换其管理的文件，不覆盖手工或未知来源文件。目录只允许当前用户访问，文件不得对组或其他用户开放。尚未取得或过期时应停止真实接口请求，不把凭证放进对话、普通日志或外部代理。`captured_at` 只记录采集时间，不据此猜测服务端有效期。

此前 `.auth/weread/` 的扫码反馈仍有效，不要求重复扫码；`.auth/article/` 也不被自动扫描、导出或转换成这些文件。后续 [有限采集实验](/Users/chenge/project/liumo/docs/wechat-session-validation.md) 已在当次明确授权下保存两号真实请求的候选凭证，恢复本次代理改动、撤销证书信任并停止进程；没有提取既有应用会话。两号列表各一次均为 source_shape_changed，使用有效性与续期仍未通过，不要求用户重复登录或打开文章。

## 请求差异与状态门槛

列表候选为 `/mp/profile_ext` 的 `getmsg`，使用 biz、offset、count 和阅读凭证，不调用旧后台 `appmsgpublish`。留言为 `/mp/appmsg_comment` 的 `getcomment`，使用 comment_id、appmsgid、idx、buffer；回复为同端点的 `getcommentreply`，使用 content_id、max_reply_id。新回复分页还携带返回的 buffer，只有构造响应证据，不能声称服务端已支持这条续取方式。

凭证只发送至明确的 `mp.weixin.qq.com` 接口；配图下载不携带 Cookie 或 Authorization。错误只保存固定原因与数字业务码，不保存上游错误描述和带凭证 URL；不将业务码 `-3` 擅自解释为某种权限原因。

`http-metadata.json` 保存正文、图片、来源候选和各分项状态；`comments.json` 只在本机忽略归档中保存选定范围的留言及回复数据。即使 comments 为 loaded 或 none，缺少原页截图、原文时间核对和静态可见性验证时，整体仍为 partial。重跑生成独立目录，不覆盖已有档案；来源输出不能自动把未核实时间改为 true，也未接入系统调度。

## 验证记录入口

最初构造证据见 [自研路线验证摘要](/Users/chenge/project/liumo/evidence/feasibility/self-http-route.json) ，后续实际请求见 [当前索引](/Users/chenge/project/liumo/evidence/feasibility/wechat-autonomous-validation.json) ，进度见 [Roadmap](/Users/chenge/project/liumo/ROADMAP.md) 。构造响应、真实本机进程、回环 HTTP 传输与真实微信证据分开记录；环境不允许监听端口或启动浏览器时明确跳过，跳过不算通过。
