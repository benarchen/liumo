# 留墨关键可行性验证

状态：原 Goal 仍 blocked、未完成。C16 组件证书选择及 34 次内存 TLS 已通过离线验证，未操作系统或微信。当前 222 项回归为 218 通过、4 跳过；下一真实实验的时间／私钥／代理范围待单独确认。[证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-compat-preparation.json) 。

## 当前结论

- 2026-10-18 15:28：C16 离线准备通过：已有 mitmproxy 12.2.3 实际加载受约束 CA 与独立目标叶证书，15 场景双根对照加选择检查共 34 次 MemoryBIO TLS 符合预期。构造上游通配符／解析 IP 时默认 SAN 推导被约束拒绝，固定目标证书后选择与握手通过；这不是当前微信失败根因证明。222 项回归为 218 通过、4 跳过，临时私钥已清理。未改系统、开监听或访问微信，C15 仍关闭。新实验提案为 180 秒／120 秒收尾预留与临时私钥文件，需按该具体范围单独确认；系统入口未实现，微信及原 Goal 未完成。[准备证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-compat-preparation.json) 。

- 2026-10-18 15:14：C15 普通终端安装后 17 项约束通过；后续独立恢复已取得证书不存在及带根链目标明确不信任 （-67843／信任结果 5），本次有效撤销验收通过，无需继续运行命令。撤销验收在信任开始 125.8 秒后完成，原 120 秒自动收尾未通过，不补记为成功。已修正自动／独立撤销各命令 30 秒认证预算，并将自动流程收尾预留增至 70 秒；216 项回归为 212 通过、4 跳过。预算修正仅经构造测试，未重装或重跑系统实验。微信兼容、无人值守追更及原 Goal 仍未完成。[现场证据](/Users/chenge/project/liumo/evidence/feasibility/installed-anchor-live.json) 。

- 2026-10-18 14:45：已核对普通终端 C14 离线结果。macOS 正对照退出 0、信任结果 4，CT 提示与成功决定并存；两个验证器各 51 项均取得结果，改进候选各 17 项符合预期，朴素方案各有 7 个范围遗漏。未安装信任、改代理或访问微信。程序／测试 38 份哈希与 200 项回归基线一致，未重复运行。显式根结果不等于安装后信任或微信兼容；新证书亦使本次不能单独证明旧 Agent 内部错误的根因。该离线检查点完成，原 Goal 仍 blocked、未完成。[终端证据](/Users/chenge/project/liumo/evidence/feasibility/native-control-terminal.json) 。

- 2026-10-18 12:38：C13 离线证书探针已交付。OpenSSL 3.6.3 下改进候选的 17 个场景符合预期，朴素 DNS 许可方案有 7 个范围遗漏；macOS 显式根正对照退出 1、含 CT／SCT 提示，未执行后续矩阵，不算约束通过。198 项回归为 194 通过、4 跳过。未安装信任、改代理、访问微信或保留私钥；没有新增微信功能通过项。整体 partial，原 Goal 仍 blocked、未完成。[离线报告](/Users/chenge/project/liumo/docs/certificate-scope-offline.md) 、[证据](/Users/chenge/project/liumo/evidence/feasibility/certificate-scope-offline.json) 。

- 2026-10-18 12:26：C12 单次文章对照已结束并正常恢复。控制 HTTP 200、代理控制计数各 1；Agent 于 12:22:02 一次刷新猫笔刀样本后，页面出现 NET::ERR_CERT_AUTHORITY_INVALID，目标 certificate_alert 从 0 增至 15，文章／普通目标 HTTP 仍为 0。代理恢复回读、临时信任撤销和进程停止通过，未采凭证、未发列表／评论探针。当前配置未被文章浏览器接受；主机限定信任的 Chromium 兼容性仅为源码支持的假设，尚非微信根因证明。不重跑本次实验，原 Goal 未完成。[现场证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-article-diagnostic-live.json) 。

- 2026-10-18 11:56：C11 只读复核完成，wxdown 文章凭证插件与 exporter 列表封装不足以证明当前 Mac 主页路径；代理／信任条件差异已记录，根因未定。停止原样重跑主页实验，不扩大采集；没有新增真实功能通过项。[通道复核](/Users/chenge/project/liumo/docs/wechat-profile-route-review.md) 。

- 自研路线已实施：直接 HTTPS、正文／图片落盘、首次评论游标和回复补取、Credential 列表候选及严格私有输入。早期缺凭证零请求与构造端到端证据见 [历史索引](/Users/chenge/project/liumo/evidence/feasibility/self-http-route.json) ；后续一次真实候选采集、正常系统恢复已通过，组件隔离于 .venv-capture。未复制或执行参考业务源码，独立 curl 与会话门槛的当前行为见 [说明](/Users/chenge/project/liumo/docs/http-route.md) 。
- 本轮真实功能未通过：普通终端列表缺字段；对齐固定参考后的两号列表均 HTTP 200／-3；两篇正文均 302 且不能确认同文跳转；主页静态身份／会话字段门槛未通过，未继续列表。这里只证明这些请求条件下的失败，不证明接口永久关闭或凭证自然过期。停止复用现有候选；没有评论或原页截图新增通过项。
- 先前 exporter 源码研究补齐主下载器、评论后端、回复补取、凭证 helper 和 PDF 渲染，纠正仅简化 API 的证据范围。上游 Markdown 分支不直接满足本地配图，PDF 重组页面不能替代原页截图；留墨本回合已独立实现正文配图，不执行上游代码。见 [机制研究](/Users/chenge/project/liumo/docs/exporter-mechanism.md) 。
- 2026-10-17 补查当前一手资料后撤回「优先继续微信读书探针」的建议：exporter 作者已宣布核心上游关闭并停维护，wx-kit 当前明确订阅只能取得最新一篇，WeRSS 分页源码仍缺本账号真实证据。三组工具的能力与凭证边界见 [GitHub 方案调研](/Users/chenge/project/liumo/docs/github-solutions.md) ，研究阶段与本回合自研验证分开记录。
- 产品边界已经同步；最小验证程序可运行，增量、时区、锁和正文转换已有分级证据。
- 两篇真实浏览器样本均已取得；猫笔刀正文与配图有分项证据，隐藏空头像误报已修正，真实复测未完成。stormzhang 存在隐藏面板混入与截图遮挡。正常阅读窗口的用户截图直接显示两篇留言和作者回复，验证浏览器均未取得，保持部分成功。
- 自动发现来源、真实发布时间、含评论单张截图和设备休眠唤醒均未通过。用户终端已成功生成构造页截图并经检查，证明该执行环境的正常渲染路径可用；Agent 环境历史启动失败的根因仍未确定，未重试权限拒绝或绕过浏览器 URL 策略。
- 用户已确认 Python HTTP 与既有浏览器组件的自研路线；真实发现来源和原页访问条件仍未选定，不把构造测试写成来源验收通过。

## 证据等级与索引

| 等级 | 含义 | 本次证据 |
| --- | --- | --- |
| 官方文档 | 接口的公开约束及字段，不代表本账号有权限 | 微信发布列表／凭据文档 |
| 固定提交源码 | 某实现的请求与解析逻辑，不保证服务端当前可用 | WeRSS `9b40351fd1913e7f74cf88f65740cd67a28baf81` |
| 真实请求／页面 | 当前执行路径实际收到的结果 | 早期限制页、后续两篇真实正文与截图、评论业务码 -3 |
| 用户截图直接审阅 | 用户正常窗口确实展示的内容，不证明自动获取 | 留言标记 15／33、可见作者回复及广告 |
| 构造浏览器实测 | 实际 Chrome 渲染构造页，不等于真实微信通过 | 本地页回复展开、截图尺寸、隐藏区域副本过滤；隔离修复后整套 44 项通过 |
| 真实本机进程 | 程序和锁在本机实际执行，不等于系统调度通过 | 重叠进程拒绝、重复运行合并 |
| 构造样本／模拟 | 给定输入下的逻辑行为，不等于真实来源覆盖 | 增量、时钟、断网标志、离线正文转换 |
| 未验证 | 尚无满足要求的证据 | 真实发现、含评论截图、实际断网恢复、休眠唤醒 |

[来源与校验索引](/Users/chenge/project/liumo/evidence/feasibility/sources.json) 、[文章访问证据](/Users/chenge/project/liumo/evidence/feasibility/article-access.json) 、[测试结果](/Users/chenge/project/liumo/evidence/feasibility/tests.json) 、[运行环境限制](/Users/chenge/project/liumo/evidence/feasibility/environment.json) 。真实文章产物保存在本机忽略目录，脱敏索引不得包含 Cookie、token 或二维码。

## A：三条候选来源路线

以下资料访问日期均为北京时间 2026-10-17；索引含各文件的具体获取时间和 SHA-256。参考源码固定在 2026-10-10 提交 `9b40351fd1913e7f74cf88f65740cd67a28baf81`，不沿用旧 `main` 结论代替当前证据。

| 路线 | 两个目标号与覆盖 | 登录、凭证及请求去向 | 权限、费用、维护与当前结论 |
| --- | --- | --- | --- |
| 1．官方发布 API | 文档支持 `offset`／`count`、每项多图文；本轮没有两个目标号的授权和实测。不能据此读取任意第三方账号 | 需要账号 AppID／AppSecret 换取凭据，或对应第三方授权；去往 `api.weixin.qq.com`。本 Goal 未索取或存储这些密钥 | 适用范围受账号类型和认证限制；具体额度费用未核实，未购买。若无两个目标号授权，不适合作为当前发现来源 |
| 2．公众号后台正常登录后的列表 | 固定源码采用 `fakeid`、`begin`、`count`；理论具备多篇分页。两个目标号是否能搜索、列表覆盖多远均未实测 | 需可正常登录公众号后台的账号，用户是否具备尚未确认；会话只应本机隔离，向 `mp.weixin.qq.com` 发请求，不复用其他软件会话 | 属后台 Web 路径，不能当作稳定公开 API；源码有频率限制分支。参考工具存在关闭 TLS 校验和输出 token 的代码，不能直接采用整套工具；不通过换账号／端点绕过限制。费用未核实 |
| 3．微信读书本地会话列表 | 固定源码的 `/web/mp/articles` 按顶层组数推进 `offset`，解析全部 `subReviews`；两个目标号是否在微信读书可访问、分页是否有效及窗口长度均待实测 | 用户已确认正常微信读书扫码，会话仅 `.auth/weread/`；最小探针只请求指定 `MP_WXS_*` 列表，向 `weread.qq.com`，不枚举书架，不第三方转发 | 内部 Web 路径，无官方稳定性和长期覆盖承诺。wx-kit 当前明确仅最新一篇，与本候选的分页源码存在待解释差异；撤回优先实测建议，先审阅当前证据，不在本轮运行探针 |

路线 2 同样需要重新评估：[exporter 作者公告](https://github.com/wechat-article/wechat-article-exporter/issues/200) 报告其核心上游关闭并于 2026-07-30 停止维护，不能仅凭旧分页实现判断可用；这不是留墨对全部后台接口的实测结论。

官方依据：[获取已发布消息列表](https://developers.weixin.qq.com/doc/subscription/api/public/api_freepublish_batchget.html) 、[获取接口凭据](https://developers.weixin.qq.com/doc/subscription/api/base/api_getaccesstoken.html) 。列表中的 `update_time` 定义为更新时间，不能未经原文核对用作首次发布时间。

源码依据：[微信读书列表与解析](https://github.com/rachelos/we-mp-rss/blob/9b40351fd1913e7f74cf88f65740cd67a28baf81/core/wx/model/weread_mp.py#L75) 、[认证请求头](https://github.com/rachelos/we-mp-rss/blob/9b40351fd1913e7f74cf88f65740cd67a28baf81/core/wx/model/weread.py#L136) 、[后台列表](https://github.com/rachelos/we-mp-rss/blob/9b40351fd1913e7f74cf88f65740cd67a28baf81/core/wx/model/web.py#L4) 、[token 输出](https://github.com/rachelos/we-mp-rss/blob/9b40351fd1913e7f74cf88f65740cd67a28baf81/driver/token.py#L47) 。近期报告实际为 [改版适配 PR #478](https://github.com/rachelos/we-mp-rss/pull/478) ，作者报告正文节点变化，提出的纯文本回退可能缺失配图。本项目未复现、未采用其回退，也未判定平台已普遍改版或问题已解决。[报告证据说明](/Users/chenge/project/liumo/evidence/feasibility/reference-change-report.json) 。

参考源码仍有只取最新一篇的 `cover` 回退，并以观察时间填充时间字段；本项目探针不采用该回退，不把它当作完整追更。参考源码还包含多账号切换，本项目不采用。

进一步核对同一固定提交：`weread_mp.py` 第 464 行附近调用 `ensure_mp_on_shelf`，`weread.py` 第 351 行起会枚举书架并可能自动加入书架。本探针不采用这些读写操作，不因参考工具可运行就推断当前只读探针同样满足前置条件；是否需要先关注／加入书架仍未实测，遇到限制记录停止，不自动更改用户书架。[固定源码调用位置](https://github.com/rachelos/we-mp-rss/blob/9b40351fd1913e7f74cf88f65740cd67a28baf81/core/wx/model/weread_mp.py#L464) 、[书架检查位置](https://github.com/rachelos/we-mp-rss/blob/9b40351fd1913e7f74cf88f65740cd67a28baf81/core/wx/model/weread.py#L351) 。探针已补充允许记录的数字业务码和白名单错误原因，不保存任意错误描述、原始响应或凭证；拒绝后不请求下一页，相关测试为 mock 证据。

探针与固定源码的逐字段对照：

| 字段 | 固定源码 | 本项目探针与差异 |
| --- | --- | --- |
| 请求 | HTTPS GET，`weread.qq.com/web/mp/articles` | 相同，TLS 默认校验；不跟随重定向，异常即停止 |
| 参数 | `bookId`、`offset`；按顶层 review 组数前进 | 相同；公开标识由用户在目标公众号正常页面取得，不枚举书架 |
| Accept | `application/json, text/plain, */*` | 相同 |
| Accept-Language | `zh-CN,zh;q=0.9,en;q=0.8` | 相同 |
| User-Agent | 参考程序配置的 UA | 使用专用浏览器实际 UA，不伪造浏览器指纹 |
| Origin／Referer | `https://weread.qq.com`／其首页 | 相同 |
| Cookie | 参考程序读取配置字符串 | 由本机专用浏览器会话按域名携带，不复制字符串、不输出凭证 |
| x-wr-ticket | 仅配置非空时携带，源码注释称新版非必需 | 不猜测、不索取该值；实际拒绝时停止核对正常页面，不能先认定 Cookie 失效 |
| 解析 | `reviews[].subReviews[].review.mpInfo`、`originalId`、`reviewId` 和时间字段 | 相同核心字段；未知结构或缺少身份就失败，不把未知响应当空列表；时间标记未核实 |
| 限制与回退 | 参考程序含多账号切换、最新一篇回退 | 均不采用；最多 3 页且页间 2 秒，失败和范围不足可见 |

本对照属于源码证据，不能证明服务端接受该请求或两个公众号实际在可访问列表中。

既有 WeWe RSS 调研只作为排除记录，不再深入第四条路线：其仓库显示 2026-05-11 已归档，README 明示第三方转发。留墨不依赖该项目。[仓库及说明](https://github.com/cooderl/wewe-rss) 。

## B：包含评论的单篇验证

真实样本仅为用户指定的两条链接，不启用正式订阅。用户普通终端已取得猫笔刀《上个月最值的一笔消费》的产物：`archives/feasibility/20261017T014629454536Z-article/`。账号可见名称与目标一致，正文 38 个非空文本行全部能在 Markdown 中找到；两张配图已本地化、SHA-256 一致并已从本地打开对照截图。当前页面截图 1100 × 4292 包含正文末尾、两张正文配图和视频封面；评论与正常页底附属区域未确认，不能通过整页完整性。[真实样本审阅](/Users/chenge/project/liumo/evidence/feasibility/maobidao-review.json) 。

该样本 `#js_content` 实际存在。参考 PR 作者报告的正文节点变化不能自动推广到此样本，更不能据此采用可能缺失配图的纯文本回退。

stormzhang 样本已取得 `archives/feasibility/20261017T021319885699Z-article/`，标题为《Linux 之父都开始用 AI 写代码了》。20 个非空可见正文行均在 Markdown 中，但 HTML 转换混入不可见赞赏表单与数字键盘，并重复标题，正文纯净性未通过。唯一图片节点为隐藏、无源的「赞赏二维码」，不满足空头像的精确排除条件，未静默忽略。截图为 1100 × 1318，实际检查发现操作栏遮挡部分正文；尺寸等于文档高度不能证明内容未被遮挡。可见署名为 stormzhang，但既有 `#js_name` 自动观察为空，说明此类页面的元信息选择器也需单独核对。[该样本证据](/Users/chenge/project/liumo/evidence/feasibility/stormzhang-review.json) 。

该篇评论同样四次返回 HTTP 200／业务码 -3，未取得评论或回复。两篇样本均为部分成功，已停止重复同方向请求。截图遮挡的 CSS 原因未采集，尚不能证明单张整图不可实现；下一步需在正常页面核对实际布局及评论开放情况，再验证最小修复。若仍无法可靠单图，可供用户取舍的候选为「保留原图并增加局部补图」或「经明确同意后调整操作栏布局生成标注处理的单图」；两者均未实施、未验证，也不代表当前已获准改变产品要求。

用户先确认两篇原文有留言，随后提供正常阅读窗口的两张截图，Agent 已直接检查：stormzhang 显示「留言 15」，猫笔刀显示「留言 33」，均有留言及作者回复，stormzhang 还有广告附属区。截图原图已保存在忽略的本机归档，摘要见两篇 review 证据；不复制读者信息或留言内容。数量仅为可见页头标记，不代表所有留言／回复均已加载，图片截图时间未知；程序未核实具体应用与会话。因此可以确认正常阅读窗口可展示这些内容、专用验证浏览器未取得，不能直接推导出具体访问差异或自动归档能力。

业务码 -3 的具体原因仍未知，不能据此认定必须登录、只能手机访问或通过增加等待即可解决。下一步核对正常入口与专用验证浏览器的访问条件及受支持的获取方式；不提取既有应用凭证，不伪造登录态或绕过访问控制，不将 UI 局部截图拼接冒充单张完整归档。微信读书发现来源验证独立，成功也不能代替评论验收。

第二次补采 `archives/feasibility/20261017T021042329739Z-article/` 已取得具体诊断：网页自身的 4 个 `/mp/appmsg_comment` 响应均为 HTTP 200／业务码 -3，未见评论正文；这证明请求遭业务拒绝，不能证明没有评论、必须登录或具体权限原因。同方向已失败两轮，停止重复请求；正常窗口可见情况已由用户截图补齐，不更换身份或接口尝试绕过。

第 3 个图片节点已确认为 `js_tail_panel_account_avatar`：无源、不可见、自然及渲染尺寸均为零，是空账号头像占位，并非第三张正文插图。代码仅在 DOM 观察及 HTML 同时匹配该特定节点与全部条件时排除，并记录原因；未知、可见、有源或缺少观察的节点仍失败。构造回归已通过，修正后的真实浏览器行为未重新执行；旧 Markdown 中的误报标记和原始元数据保留，不改写原产物。

时间边界也有真实样本证据：页面显示 `2026年10月16日 07:20`，公开时间戳候选 `1792160400` 换算为 `Asia/Shanghai` 是 `2026-10-16T22:20:00+08:00`，换算为洛杉矶是 `07:20`。第二次观察确认浏览器时区为 `America/Los_Angeles`，可见文本与该时区换算一致，因此不能当作北京时间。该交叉核对尚不能验证来源列表的时间字段语义。

最小程序已提供：正文限定 `#js_content`，配图本地化、校验和相对引用；页面不裁掉评论及附属区域；有界滚动、指定评论区中的安全展开、再次到底检查、全页单图、PNG 尺寸核对和结果元数据。评论分别记录 `none`、`inaccessible`、`failed`、`unknown`、`incomplete`、`loaded`。仅存在正文或评论区缺失时不得标完整。

实际微信评论 DOM 的选择器尚未验证，因此真实归档即使未来生成截图，也会先保留 `publication_time_not_verified`、`live_comment_selectors_not_validated` 和 `visual_review_required`，等待核实后才能进入正式完整归档逻辑。当前评论选择器是验证假设，不是已成功读取微信评论的证据。

针对 stormzhang 暴露的转换问题，已增加基于计算样式的正文副本过滤：排除 `display:none` 分支与 `visibility:hidden` 文字／图片，同时保留重新设置为可见的子元素；原页面和截图不变。过滤后配图仍使用原 DOM 索引，映射不一致会失败，重复开头标题去重且其他章节保留。首次用户终端整套 43 项因负向用例继承终端输入而超时，原失败日志保留。已将该测试的子进程 stdin 明确设为空，并在真实 PTY 下通过负向用例；用户随后完整重跑，44 项全部通过、无跳过，包含 3 项实际 Chrome 构造页测试。这些证据不能代替真实文章的转换／评论验收，也不代表 Agent 的浏览器启动权限恢复。

正常窗口的只读 UI 检查仅暴露微信主窗口及菜单，未定位到文章窗口，未获取整页导出证据；未截取聊天主窗口、未读取凭证，已停止该界面尝试。这不能证明原生阅读窗口没有导出功能。[本轮检查记录](/Users/chenge/project/liumo/evidence/feasibility/continued-validation.json) 。

构造样本已验证 Markdown 与配图转换，无网络参与；本机 `sips` 成功解码样本 PNG 为 1 × 1。[构造转换记录](/Users/chenge/project/liumo/evidence/feasibility/offline-conversion.json) 。用户随后在普通终端执行构造页归档，生成单图 1100 × 2103；Agent 已实际检查正文末尾、评论、展开回复、附属区域和页底均可见，Markdown 相对配图存在且校验一致。[构造浏览器证据](/Users/chenge/project/liumo/evidence/feasibility/fixture-browser.json) 。这不是两篇真实文章或浏览器故障分支的验收，也未完成真实文章的断网阅读检查。

已增加交互式真实取证入口：`archive --session --headed --interactive`。正常文章访问在同一窗口进行，由用户在遇到验证码时人工处理；就绪后按 Enter 才读取页面，取消、失去终端输入或离开文章站点时不截图、不自动重试。就绪分支已有两篇真实文章产物；取消保护仍只有构造输入与 mock 浏览器证据。公开元信息与评论区域的观察数据保存在忽略目录，凭证与任意脚本不进入证据。

超长单图的程序保护阈值为 100000 CSS 像素高或 1 亿像素面积。这是验证程序的资源保护，不是已测出的 Chrome 极限。超限只标部分成功，不拆图、不截断；真实超长样本与替代方案仍待取证，未经用户决定不修改要求。[Playwright 全页截图 API](https://playwright.dev/python/docs/screenshots) 只说明可用 API，不证明微信动态页面完整性。

## C：增量与调度

已通过构造样本验证：启用前／恰好等于／之后、多篇与同日发布、不同链接、已见文章后仍有新文章、跨页失败、尾页缺失、未知发布时间、重复运行、部分成功后恢复。发现队列与完整检查位置独立，失败页不推进完整检查位置，已完成档案不回退覆盖。

2026-10-17 00:25 补充回归：同一可信来源 ID、相同发布时间的短链／长链切换不应被误报为身份变化。修复前 pending／partial／complete 三种状态均会导致扫描不完整；最小修复后不重复建任务、不修改原链接及归档状态、待恢复任务仍保留。无可信来源 ID 的短链／长链仍不自动认定同文，发布时间冲突仍报告。[修复前后构造证据](/Users/chenge/project/liumo/evidence/feasibility/url-alias-regression.json) 。

真实本机子进程验证：同一锁重叠触发被拒绝；连续两次轻量任务只记一次运行。北京时间四点、跨日约 22.5 小时空档、时区与夏令时、离线恢复合并使用构造时钟／标志验证；实际联网恢复、设备休眠唤醒及系统后台触发未测试。

已生成 [审阅配置](/Users/chenge/project/liumo/examples/local.liumo.feasibility.plist) 并通过 `plutil -lint`。每分钟触发本地轻量门控，由 Python 使用 `Asia/Shanghai` 决定是否该运行；该文件不访问微信，不检测实际网络，不安装／加载。配置启用和检测连接、真正补抓仍属后续工作。Apple 文档只作调度语义依据，不能代替本机睡眠测试。[Apple 调度文档](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/ScheduledJobs.html) 。

本机通知提供单一 `notify(event, count, sender)` 出口，当前只有本机 sender；测试使用注入 sender 和文案预览，没有发送真实 macOS 通知，没有实现微信通知。

## 依赖选择与维护核对

标准库负责时区、状态文件、锁、配置和测试。Playwright 用于真实页面 JavaScript、滚动、展开及全页截图，标准库无法替代浏览器渲染；markdownify 用于正文 HTML 的 Markdown 转换，避免自行重写复杂标签转换。Beautiful Soup 为其依赖，并复用于正文处理；其他固定依赖为传递依赖。

本机隔离安装 Playwright 1.64.0（PyPI 发布于 2026-10-13）、markdownify 1.2.3（2026-06-30），8 个 wheel 与 PyPI SHA-256 一致。主仓库 metadata 显示未归档，Playwright 最近 push 为 2026-10-16，markdownify 为 2026-06-30。已查看 issue 页面；不足以承诺统一响应时效。Playwright Python issue 页面提示问题集中到主仓库，本轮未对核心浏览器 issue 做全面审计。它们仅进入验证环境，不据此宣称生产链已定案。[Playwright 文档](https://playwright.dev/python/docs/library) 、[Python issues](https://github.com/microsoft/playwright-python/issues) 、[markdownify 仓库](https://github.com/matthewwithanm/python-markdownify) 、[markdownify issues](https://github.com/matthewwithanm/python-markdownify/issues) 。

安装过程中部分命令出现 DNS 解析失败；直接 curl 成功下载官方 PyPI wheel，再校验并离线安装，没有关闭 TLS、改变系统网络或安装全局依赖。[依赖记录](/Users/chenge/project/liumo/evidence/feasibility/dependencies.json) 。

## 下一步与用户配合

2026-10-18 11:49：C10 单次实验已到期并正常恢复。控制 HTTP 200、代理控制请求／响应各 1；Agent 在北京时间 11:46:29 向已确认的猫笔刀主页成功发送一次 ⌘R，观察到卡片图片占位后重新加载、互动数字变化。普通目标域 HTTP 计数始终为 0；唯一 1 次 certificate_alert 类客户端 TLS 失败在刷新前已出现，刷新前后及后续取样均未增加，不能归因本次刷新。代理恢复回读、临时信任撤销及进程停止通过；未采凭证、未发列表／评论探针。C10 诊断交付完成，实际主页网络通道与功能会话仍未建立；本次无需用户继续操作或重跑。[C10 现场证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-ui-diagnostic-live.json) 。

2026-10-18 11:09：重启 CLI 后本会话已连接微信；整体截图被自动审批拒绝，理由为可能包含未授权聊天，标题元数据仍无法确认目标主页，待用户将右侧猫笔刀主页单独前置。Agent 系统基线查询仍受权限限制。已交付独立 ui_diagnostic 入口和恢复路由，固定 120 秒、无凭证、旧三次恢复门槛及目录保全；188 项中 184 通过、4 跳过。第四次系统实验尚未启动，未刷新。[C10 独立入口证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-ui-diagnostic-session.json) 。

2026-10-18 08:17：用户已授权 Agent 操作右侧猫笔刀主页并记录复测。首次 Computer Use 连接返回 Sky Computer Use native pipe startup failed，未接管成功、未启动第四次系统实验。已完成目标主机 TLS 错误固定分类及刷新前／后只读取样，185 项测试中 181 通过、4 跳过；现场刷新、原因分类及对应关系仍未验证。C9 最先操作左侧、回复后再刷新右侧的反馈已接受，确切时刻未知，不再要求重复解释或运行旧命令。[C10 准备证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-ui-diagnostic-preparation.json) 。

1. 用户普通终端的构造页面命令及最新完整浏览器测试均已执行，44 项全部通过，包含评论失败保护、回复展开和可见正文副本过滤；无需再跑相同测试。真实微信与实际设备断网／唤醒仍是独立未验证项。
2. 用户截图已直接确认正常阅读窗口显示留言及作者回复；无需再要求重复这一检查。下一步核对正常入口与验证浏览器的访问条件、受支持的获取方式，再核对保真路线或明确取舍；评论获取验收仍未通过，不继续重复同方向取证。
3. 微信读书扫码、正常开文及双号诊断均已完成，无需重复。一次捕获已得到两号候选，但未建立可用功能会话；不能重复旧命令作为推进。具体失败与条件见 [阶段报告](/Users/chenge/project/liumo/docs/wechat-session-validation.md) 。
4. 正常主页／列表请求的合法上下文与即时功能核对已作为 C7 单独获准，新的限定采集程序及必要自测已交付。用户普通终端已执行到期，本次代理恢复、信任撤销及进程停止通过；全窗口没有目标匹配或即时探针。主页反馈已收到，目标响应计数在路径过滤前也为 0；不能单凭放宽路径或 TLS 事件猜测原因。C8 已补固定阶段计数，菜单截图仍没有可见复制链接入口。C9 已交付有正向控制门槛的 120 秒无凭证诊断，本次真实控制 HTTP 200 且代理控制计数各 1，目标域其他连接记录到 91 次客户端 TLS 失败、无 HTTP 请求／响应。实验到期恢复并停止，未采凭证或运行列表探针；具体原因及客户端归属未知，不再刷新或重跑。旧授权已结束，旧目录不删除重跑。后续仍需两号多篇／分页、真实时间、评论原页单图和自然续期证据，不承诺重新采集必然解决。

自研程序、源码探针与构造测试可以复现；真实自动发现、含评论截图证据尚缺，不能宣布 Goal 完成。Goal 服务本轮核对仍为 blocked，未新建替代 Goal；用户登录完成反馈已接受，旧依赖审计中等待微信读书登录的部分为历史。本回合按用户明确授权实施并交付代码，不把模拟、作者报告或源码当作解除真实验收依赖。

下一 MVP Goal 的建议范围：仅在来源、发布时间和含评论截图通过后，把已验证的发现、独立待归档队列、归档保全、恢复、通知与调度门控接成闭环；系统调度安装仍需该次明确授权。本 Goal 不创建或执行第二个 Goal。
