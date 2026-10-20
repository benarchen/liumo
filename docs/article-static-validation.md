# C24 至 C26：固定文章内存静态取证

实现位于 [分析器](/Users/chenge/project/liumo/validation/html_static.py) 、[固定会话入口](/Users/chenge/project/liumo/validation/html_static_session.py) 和 [默认关闭的代理适配器](/Users/chenge/project/liumo/validation/html_static_addon.py) 。目录职责、自测和验收见 [施工清单](/Users/chenge/project/liumo/goals/20261017-1606-wechat-session-validation.md#c24固定文章内存静态取证施工范围) ，前置证据见 [C23 排查](/Users/chenge/project/liumo/docs/comment-loading-investigation.md) 。这是原 Goal 的一个检查点。

## 实现行为

只匹配猫笔刀固定技术样本的正常 GET 响应。短链接必须为既有固定路径；长链接必须同号、同文章、同索引，重复公开标识拒绝。不解码其他 query 值，不读取请求头、Cookie 或响应 Set-Cookie。

最多读取第一份匹配响应。非 HTTP 200、非 HTML／非 UTF-8 声明或未知 Content-Encoding 时停止，不改用第二份响应。identity、gzip、deflate 与已有 Brotli 组件分别验证，编码和解码上限各 4194304 字节；损坏、截断、尾随压缩数据及超限拒绝。原响应字节逐块透传，不修改微信页面。

HTML 仅在内存中解析，检查非空正文、固定号名／标题，以及脚本字面量中的 biz、mid／appmsgid、idx；缺失、冲突或重复身份节点拒绝，不能用请求 URL 充当响应身份。验证页、未知正文模板、非 UTF-8、未闭合结构和付费标记拒绝。它只支持已核对的静态字面量，不执行 JS 或猜测动态变量；真实页面模板兼容性仍需实测。

独立身份通过后输出固定词频和候选公共静态脚本地址。仅允许 HTTPS `res.wx.qq.com`／`res2.wx.qq.com`，路径前缀限 `/mmbizwap/`、`/a/wx_fed/`、`/t/wx_fed/`，限定字符及 `.js` 后缀，拒绝编码路径、点段、端口、userinfo 和动态地址，移除查询及片段并去重。外部脚本元素最多 128 个，未知来源只输出数量并标记 partial；不输出未知域名或地址原文，不自动取脚本。该列表只是满足语法白名单的候选地址，未证明当前可匿名取得或与评论有关。

`inline_marker_counts` 是脚本文本中固定词的出现次数，包含注释或字符串的可能；`getcomment` 也可能是其他词的子串。计数不是执行轨迹、端点发现或已加载留言数。无可用标记／来源时标记 partial；无论结果如何，`comment_channel_verified` 和 `comment_baseline_verified` 均为 false。

## 无网络复现

在项目根目录执行：

```bash
.venv/bin/python -m validation html-static-plan
.venv/bin/python -m validation html-static-fixture
.venv/bin/python -m unittest discover -s tests -p test_html_static.py -v
```

plan 只审阅固定范围；fixture 只读取 [脱敏构造页](/Users/chenge/project/liumo/examples/pages/article-static.html) 并输出 JSON，不创建真实实验目录、不启动浏览器／监听或修改系统。构造页里的图片和脚本地址均不会被访问。专项测试包含真实 mitmproxy HTTPFlow 类型和 Brotli 组件的无网络回放；不等于代理链路或当前微信已通过。

必需完整回归与结果索引：

```bash
.venv/bin/python -m unittest discover -s tests -v
```

[C24 准备证据](/Users/chenge/project/liumo/evidence/feasibility/article-static-preparation.json) 记录测试数量、源码哈希、CLI 输出和边界；真实微信证据不能由该索引替代。

## 新系统实验的具体范围

C24 本次已执行并关闭，不再运行以下 session／observe／finish 命令。控制 HTTP 200／计数各 1，匹配文章响应 1 次，在 Content-Type 检查处以 html_content_type_rejected 停止；没有读入正文或生成 static-summary.json。15.484 秒内完成代理恢复、有效撤销、进程停止及私钥清理；公共材料身份与私钥不存在已另行核对。正常文章仍可读、留言按钮显示 33，但正文独立身份及静态线索未取得，不能标通过。原始头部没有保留，无法追补具体拒绝原因。[真实结果](/Users/chenge/project/liumo/evidence/feasibility/article-static-live.json) 。

以下为已消耗的 C24 授权范围说明，不授权新实验：

- 目标仅为已确认的猫笔刀固定文章，一次明确圆形箭头刷新，一份被动 HTML，编码／解码各最多 4 MiB；正文可能含会话字段，只在本次内存中处理，不落原始内容。
- 总窗口 180 秒，预留 120 秒收尾；复用已验证控制器，临时用户级受约束 SSL 信任限定 `mp.weixin.qq.com`，临时设置当前活跃网络服务的 HTTPS 代理并衔接原本机上游。用户可能需要完成 macOS 认证。
- 新 CA／固定目标叶证书私钥仅在新的 `.auth/wechat-capture/article-static-session/`，结束后恢复原代理、撤销本次信任、停止本次子进程并清理本次私钥。恢复任一分项失败则停止后续工作，按本次专用入口收尾。
- 仅有一个无凭证公开控制请求，无主动正文／列表／评论或脚本请求，无 Cookie 读取、应用缓存、账号资料、聊天、消息发送、系统后台任务或其他系统设置操作。

新授权文件固定为 `/Users/chenge/project/liumo/.auth/wechat-capture/article-static-authorization.json` ，绑定 C22 已关闭且四项恢复通过的 state.json 哈希及时间；不能复用 C21／C22 授权。旧十次均需关闭，生命周期锁保持互斥。目标 UI 确认沿用 300 秒时限，固定就绪文件位于 `/Users/chenge/project/liumo/.tmp/wechat-session-validation/article-static-ui-ready.json` 。这些文件均不是用户需要手工编写的参数。

以下为已执行的 C24 命令，不再重跑：

```bash
.venv-capture/bin/python -m validation html-static-session
```

只有出现 `ready_user_refresh_maobidao_for_static_inspection` 才刷新一次。流处理完成或匹配失败时，适配器请求提前收尾；如果该请求不可用，独立控制器仍负责截止恢复。不得把自动提前恢复写成未经设备测试的保证。

独立恢复入口为：

```bash
.venv-capture/bin/python -m validation html-static-recover
```

恢复入口只处理 C24 拥有的设置及材料，不自动授权或启动新采集；已关闭并验证恢复的目录返回 already_closed_no_changes。observe／finish 也只接受本次模式，不能触碰旧实验或使目录可重跑。

## 实际验收

一份响应经独立身份和限制检查后，候选摘要排他写入本次 `static-summary.json`，权限为 0600。匹配失败记录在固定 capture／session 摘要，不保存原始失败正文或错误文本。没有匹配则明确未取得。

必须同时核对 UI 动作、采集时间、实际摘要、公共材料身份以及代理恢复／有效信任撤销／进程停止／私钥清理，才验收真实检查点。只有脚本候选或固定标记仍不能宣称评论接口、评论快照、两号完整归档或自动追更通过。没有线索则保留失败证据，重新评审，不原样重试。

## C25：固定响应头分类与格式解析

C24 的原始 Content-Type 不存在于回执中，无法确定它是缺失、不同媒体、字符集变体、附加参数或其他情况。没有将页面可读等同于接口头部必定符合预期。

离线核对 [RFC 9110 第 8.3.1 节](https://www.rfc-editor.org/rfc/rfc9110.html#name-media-type) （访问日期：2026-10-19）确认媒体类型可带参数，类型名称不区分大小写，参数值可带引号。旧单一正则会拒绝一些带附加参数的构造值；该可复现缺陷不能证明 C24 命中了同种格式。

准备版 C25 使用已有 Python 标准库 email.policy.HTTP 解析，只接受明确 text/html，charset 缺省或明确为 UTF-8／受限 UTF8 别名；原始字节随后仍严格 UTF-8 解码并独立核对文章身份。畸形、重复／冲突参数、多个 Content-Type、非 HTML、非 UTF-8 和未知压缩编码停止。最多 8192 个 ASCII 头部字符、16 个参数，拒绝控制字符，不打印原始值。C24 默认模式仍保留旧判定，已关闭结果不被新逻辑覆盖。

匹配响应只增加固定 response_metadata：HTTP 数字状态、html／xhtml／json／other／missing／malformed／ambiguous 媒体类别、固定 charset 类别、参数数目、Content-Type 条数，以及固定 Content-Encoding 类别。未知字符串均不输出；失败分类也会进入 capture.json，因此不再只剩一个拒绝原因。不会读取请求 Cookie、Set-Cookie 或任意其他头部，不读取未匹配响应。

C25 本次已执行并关闭：控制 HTTP 200／各 1，匹配文章响应 1 次；响应固定分类为 HTTP 200、gzip、Content-Type 条数 2、media=ambiguous，程序按既定规则拒绝，未读正文或生成静态摘要。15.664 秒完成四项恢复，公共材料身份与私钥不存在已核对；C24 私有回执不变。未保留两条原始值，不能判断它们相同或冲突，也不能归因于微信、原本机上游或具体实现环节。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/article-static-metadata-live.json) 。

C25 固定目录 `/Users/chenge/project/liumo/.auth/wechat-capture/article-static-metadata-session/` 和绑定授权已消耗，下面的 session／observe／finish 均不再运行；专用 recover 仅在确有该次未恢复事项时使用。当前已恢复，不需再运行命令。

除以上解析及诊断变化，C24 的固定文章／一次被动响应、4 MiB 双上限、一次明确刷新、180 秒／120 秒收尾预留、受约束临时用户级 SSL 信任／HTTPS 代理、无主动文章或 API／脚本请求、四项恢复及隐私边界均保持。C25 使用独立固定适配器选择模式，不重跑 C24，也不使用旧授权。

无网络审阅和构造复现：

```bash
.venv/bin/python -m validation html-static-metadata-plan
.venv/bin/python -m validation html-static-metadata-fixture
.venv/bin/python -m unittest discover -s tests -p 'test_html_static*.py' -v
```

以下为已执行的 C25 入口，不重跑：

```bash
.venv-capture/bin/python -m validation html-static-metadata-session
```

只在出现 ready_user_refresh_maobidao_for_static_metadata 后刷新一次；若需独立收尾，只用 html-static-metadata-recover。构造检查、组件回放和新增边界见 [C25 准备证据](/Users/chenge/project/liumo/evidence/feasibility/article-static-metadata-preparation.json) 。正常微信取证和当前评论通道仍未通过。

## C26：只处理可证明等价的双头

C24／C25 连续两轮在同一阶段停止后，已重新核对一手标准、已装组件源码和构造行为。[RFC 9110 第 8.3 节](https://www.rfc-editor.org/rfc/rfc9110.html#name-content-type) 指出 Content-Type 是单值字段，重复生成后的恢复可能造成不同解释；不能直接选最后一条。[mitmproxy 官方 API](https://docs.mitmproxy.org/stable/api/mitmproxy/http.html#Headers.get_all) 与本机锁定的 12.2.3 源码说明 get_all 保留独立字段，普通 get 会合并值。本机两条构造值已复现该行为；源码哈希和访问日期见准备索引。

C26 的保守恢复策略为：单条按 C25 解析；恰好两条时分别通过 HTML／UTF-8 门槛，再比较归一化媒体类型与全部参数。参数顺序、引号形式、媒体／charset 大小写和受限 UTF8 别名可以归一化；非 charset 参数值保留大小写，缺省 charset 与显式 charset 不擅自等同。只有完整签名一致才继续，签名仅留内存；无效／冲突／超过两条都停止，不选一条、不嗅探类型、不改写响应。这是留墨的恢复策略，不声称标准要求接受双头。

输出只增加逐条固定类别与 relation 枚举，不保存原始头部、任意参数名值或比较签名。UTF-8、独立号／文章／标题／正文身份、4 MiB 双上限和单次流处理均保持；头部等价不等于正文正确或评论可取。

旧十二次须关闭，C26 固定目录为 `/Users/chenge/project/liumo/.auth/wechat-capture/article-static-duplicates-session/` ，授权绑定已恢复 C25 的 state.json 哈希。C26 已由普通终端执行并关闭，本次授权已消耗，目录不得重跑。[现场记录](/Users/chenge/project/liumo/evidence/feasibility/article-static-duplicates-live.json) 。

C26 系统操作已取得本次独立授权，无需重复确认。一次固定猫笔刀刷新／一份被动响应、180 秒／120 秒收尾预留、受约束临时用户级 SSL 信任与当前服务 HTTPS 代理、原本机上游、无主动文章／评论／列表／脚本请求及四项恢复要求均沿用。

无网络复现：

```bash
.venv/bin/python -m validation html-static-duplicates-plan
.venv/bin/python -m validation html-static-duplicates-fixture
.venv/bin/python -m unittest discover -s tests -p 'test_html_static*.py' -v
```

以下为已执行的历史入口，不再运行：

```bash
.venv-capture/bin/python -m validation html-static-duplicates-session
```

专用恢复入口为 html-static-duplicates-recover；已验收恢复后只返回记录，不重新修改系统。[C26 准备证据](/Users/chenge/project/liumo/evidence/feasibility/article-static-duplicates-preparation.json) 。

### C26 实际结果

2026-10-19 00:35：HTTP 200／gzip，两条声明分别有效且完整归一化等价，编码 789852 字节、解码 3493845 字节，独立号／文章／标题／正文身份通过。16.313 秒完成代理恢复、有效撤销、进程停止与私钥清理；公共材料身份、两份私钥不存在、0600 摘要、源代码基线和 C25 旧回执另行核对。

分析发现 57 个 script，其中 2 个带外部来源，均被既有白名单拒绝，无可用公共脚本地址。固定词频为 cgiDataNew 94、appmsg_comment 2、WeixinJSBridge 132、getappmsgext 44、comment_id 7，其余 getcomment／getcommentreply／elected_comment 为 0。这些只是文本计数，可能来自注释、字段或字符串，不证明路径调用、运行时请求或评论不存在。

整体结果为 partial／html_script_source_rejected。未保存原始 HTML、脚本文本、Cookie 或评论；无法追补语法分析，也没有新 Markdown／配图／整页截图产物。下一步只准备 [C27 离线语法分析](/Users/chenge/project/liumo/docs/inline-script-validation.md) ，不复用 C26 授权或扩大外部脚本白名单。
