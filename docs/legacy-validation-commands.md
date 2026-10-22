# 历史验证工具使用记录

以下保存单号 RSS MVP 上线前的 README 使用记录，仅供复核旧程序；不是当前运行顺序、当前产品范围或新增授权依据。当前入口见 [README](/Users/chenge/project/liumo/README.md) 。

# 留墨 liumo

个人公众号新文章自动归档项目。V1 范围为猫笔刀、stormzhang 的自动追更、Markdown、本地配图与原页非评论区域单张整图；不读取评论区。

当前可运行内容是首个可行性 Goal 的独立验证程序，尚未接成正式追更程序。下文命令描述现有原型，其中旧归档入口仍采用含评论验收，尚未按 V1 改造；原页及评论诊断说明只供历史复核，不能当作当前实施顺序。详细状态和后续入口见 [Roadmap](/Users/chenge/project/liumo/ROADMAP.md) ；[路线评审](/Users/chenge/project/liumo/docs/route-review-20261019.md) 解释新方案与旧程序的关系。

项目已取消旧实验附加的逐轮授权和固定单次目录审批，按全局规则及用户明确授权范围执行；历史命令中的授权文件／固定目录检查仍是现有程序行为，尚未迁移，也不用于 V1。当前环境能力与调整边界见 [执行权限说明](/Users/chenge/project/liumo/docs/execution-permissions.md) 。

## 2026-10-22 入口迁移

当前正式共享实现位于 `liumo/`，旧验证模块保留兼容导入，单向引用正式实现。旧原页诊断入口已从 `python -m liumo page-sample` 迁到 `python -m validation page-sample`，仍是显式诊断，不进入 RSS 自动运行。核心／浏览器依赖和产品／浏览器／旧实验测试分组见 [开发说明](/Users/chenge/project/liumo/docs/development.md) 。下文保留当时使用记录，不能当作当前产品安装要求。

## 隔离环境

本机已在 `.venv/` 安装固定版本依赖，使用现有 Google Chrome。重新创建环境时：

```bash
cd /Users/chenge/project/liumo
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m validation --help
```

实际验证环境为 macOS、Python 3.14.5、Playwright 1.64.0、markdownify 1.2.3。C27 专项及完整回归还需要本机 Node.js 和项目内 Acorn 8.19.0，当前已安装并核对，依赖入口见 [离线分析说明](/Users/chenge/project/liumo/docs/inline-script-validation.md) 。依赖版本和 SHA-256 见 [依赖证据](/Users/chenge/project/liumo/evidence/feasibility/dependencies.json) 。程序无需下载新的浏览器，不使用其他应用的浏览器会话，不默认接入大模型。

## 证书信任离线对照

已单独授权的证书安装前后离线对照使用 `.venv-capture/bin/python -m validation anchor-scope-session`，只处理构造公共证书和临时用户级 SSL 信任，不操作代理或微信。必要恢复入口为 `.venv-capture/bin/python -m validation anchor-scope-recover`，命令范围、固定目录和输出分项见 [操作说明](/Users/chenge/project/liumo/docs/installed-anchor-experiment.md) 。默认测试与 `--help` 不安装证书。

微信兼容准备可运行 `.venv/bin/python -m validation wechat-compat-plan` 审阅预算，以及 `.venv-capture/bin/python -m validation wechat-compat-fixture` 离线验证受约束 CA、固定目标证书与已有组件选择。后者只在私有临时目录生成密钥并清理，输出公共证书和实际内存 TLS 结果，不安装信任、不启动网络或访问微信；分项输出与范围见 [验证说明](/Users/chenge/project/liumo/docs/wechat-compatibility-validation.md) 。

## 本地逻辑与构造样本

固定文章 HTML 静态取证可在无网络模式下审阅和运行构造样本：

```bash
.venv/bin/python -m validation html-static-plan
.venv/bin/python -m validation html-static-fixture
.venv/bin/python -m validation html-static-metadata-plan
.venv/bin/python -m validation html-static-metadata-fixture
.venv/bin/python -m validation html-static-duplicates-plan
.venv/bin/python -m validation html-static-duplicates-fixture
```

程序只输出独立文章身份结果、固定标记计数和脱敏后的白名单静态脚本候选，不执行 JS、不读取 Cookie 或自动访问脚本。固定范围、测试、真实入口与恢复命令见 [页面静态取证说明](/Users/chenge/project/liumo/docs/article-static-validation.md) 。

C24／C25／C26 的真实单次目录均已关闭；session／observe／finish 入口不再运行，已验收的 recover 只返回记录。`validation/js/` 已安装固定 Acorn 8.19.0 并保存 lockfile；`.venv/bin/python -m validation.inline_scripts --fixture` 可运行无网络 JS 静态构造分析。输入、输出、资源限制和复现步骤见 [内联脚本分析说明](/Users/chenge/project/liumo/docs/inline-script-validation.md) 。

C28 无网络入口为 `.venv/bin/python -m validation html-static-inline-plan` 和 `.venv/bin/python -m validation html-static-inline-fixture`，后者因包含未下载的外部脚本，预期返回 partial／退出 2。C28 真实目录现已关闭，不再执行 session／observe／finish，已验收 recover 只返回记录。操作边界见 [C28 说明](/Users/chenge/project/liumo/docs/inline-script-validation.md#c28一次-html-内存连接实验) 。

`.venv/bin/python -m validation.parser_capacity` 仅生成构造 JS 并比较临时分析器副本的节点容量，输出退出码及耗时，不访问微信或修改运行时。峰值 RSS 不在该程序的测量范围。

正常微信评论请求的限定对照入口为 `.venv/bin/python -m validation comment-baseline-plan`，只输出固定范围，不读取凭证或联网。会话、收尾、专用恢复及离线比较入口见 [评论基线说明](/Users/chenge/project/liumo/docs/comment-baseline-validation.md) ；真实入口强制检查当次授权，固定单次目录不可重跑。 C21 固定目录现已关闭，session／observe／finish 不再执行；恢复入口仍保留，已恢复时只返回关闭记录。

明确刷新对照使用 `.venv/bin/python -m validation comment-refresh-plan` 审阅；C22 的独立会话、固定匹配计数、取样与恢复入口见 [C22 操作说明](/Users/chenge/project/liumo/docs/comment-baseline-validation.md#c22明确刷新与固定匹配计数) 。该模式只接受固定样本和预算，真实入口先检查单次绑定授权。 C22 固定目录已关闭，session／observe／finish 不再执行；成功基线不存在时不执行 compare。

C16 单次兼容入口为 `.venv-capture/bin/python -m validation wechat-compat-session`，独立恢复为 `.venv-capture/bin/python -m validation wechat-compat-recover`；只能在对应单次授权和 Agent 近期确认目标 UI 后运行。完整运行、取样与恢复说明见 [微信兼容验证](/Users/chenge/project/liumo/docs/wechat-compatibility-validation.md) 。默认无凭证采集，固定一次目录不可重跑。C16 目录已完成并关闭，上述 session／observe／finish 命令保留说明，不再执行；已验收的恢复入口重复运行只返回记录。

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m validation replay --input examples/incremental.json --state .tmp/feasibility/replay-state.json --start-at 2026-10-16T22:00:00+08:00
.venv/bin/python -m validation schedule --state .tmp/feasibility/schedule-state.json --now 2026-10-16T22:00:00+08:00
.venv/bin/python -m validation schedule --state .tmp/feasibility/schedule-state.json --now 2026-10-17T10:00:00+08:00 --offline
.venv/bin/python -m validation schedule --state .tmp/feasibility/schedule-state.json --now 2026-10-17T10:01:00+08:00
.venv/bin/python -m validation notify --event partial --count 2 --dry-run
```

`--now` 是构造时钟；`--offline` 是显式断网标志，不检测实际微信可达性。省略 `--now` 时使用真实时钟；轻量任务不访问微信。通知 `--dry-run` 只显示文案；省略时才请求 macOS 本机通知，不接入微信。

增量输入中，`time_verified: true` 代表输入提供者已核实原文发布时间；构造样本只在构造域内成立。真实来源程序始终先输出 `time_verified: false`，不得为了通过测试直接改为 true。短链与长链的同文关系需可信来源 ID 或实际跳转证据，不自动猜测。

## 浏览器与样本归档

下面的浏览器命令需要本机允许启动 Chrome；测试只访问本地构造文件，不访问微信：

```bash
LIUMO_BROWSER_TESTS=1 .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m validation fixture --file examples/pages/article.html
```

真实文章需正常访问。交互式命令在同一专用 Chrome 窗口等待您正常打开文章；若出现页面验证，由您操作。能正常阅读后回到同一终端按 Enter，程序再开始取证；无法访问时输入 q，不继续自动请求：

```bash
.venv/bin/python -m validation archive --sample maobidao --session --headed --interactive
.venv/bin/python -m validation archive --sample stormzhang --session --headed --interactive
```

登录对象是两篇用户指定的微信文章页面，独立会话只存于 `/Users/chenge/project/liumo/.auth/article/` 。站点正常请求发往腾讯及页面资源域名；图片下载仅接受已登记的腾讯图片域名，不把凭证发给 RSS 服务，不导出 Cookie。发现访问限制时停止自动请求，由用户在正常页面完成人工操作，不绕过验证码。

每次生成新的 `/Users/chenge/project/liumo/archives/feasibility/` 子目录，不覆盖旧档案。程序记录加载范围、评论状态、截图尺寸、配图校验值和未完成原因；实际页面仍需核实发布时间、评论选择器及人工视觉对照，不能仅凭退出码认为整页已验收。`partial`、`blocked`、`failed`、未完成扫描或尚未验证的来源结果返回退出码 2。

真实正文可读时，还在该次忽略目录中保存 `body-source.txt` 和 `page-observation.json`，用于核对正文转换、公开署名与发布时间候选、评论区域的可见结构。不保存原始页面脚本、请求头或凭证；这些观察值不自动升级为已核实的发布时间或评论完整性。

Markdown 从正文的独立副本转换，依据浏览器计算后的 `display`／`visibility` 排除隐藏文字与表单，保留显式重新可见的子元素；记录过滤数量及原始图片索引。该处理不改动实际页面或截图布局。开头与文章标题相同的正文标题只输出一次，后续章节标题保留。

## 微信读书来源探针

可先运行不读取会话、不启动浏览器的请求审阅：

```bash
.venv/bin/python -m validation weread-plan
```

程序从已有公开样本身份计算两个 `bookId` 候选，并输出请求字段、会话去向和每号最多 3 页的范围。候选映射不是当前服务端身份验证。列表解析保留 `reviewId`／`originalId`，不会直接拼出文章短链；`url=null`、`url_verified=false`，需后续从同文内容响应核实。观测到空页或 `clearAll` 结束信号只记为 `source_terminal_observed`，身份、原链接与发布时间未核实前，`coverage_complete` 仍为 false。

重复文章／重复页、异常结构、业务拒绝和跨页失败都会留下未完成原因，前面有效页保留。列表 2 MiB 是响应已读入后的接受上限，不是流式下载或进程内存硬上限；本轮未做真实列表传输。针对这些路径的离线回归可运行 `.venv/bin/python -m unittest discover -s tests -p 'test_weread_discovery.py' -v`，不访问微信。

```bash
.venv/bin/python -m validation login --site weread
.venv/bin/python -m validation login --site weread --auto-wait
```

登录对象是 `https://weread.qq.com/`，用户在专用窗口扫码；会话只保存在 `/Users/chenge/project/liumo/.auth/weread/` 。探针只向微信读书域名发起指定公众号列表请求，不枚举书架、不读取其他书籍／账号资料、不使用第三方转发、不切换账号绕过限制。

`--auto-wait` 只用于微信读书：打开项目专用正常登录页，最多观察 300 秒的必要会话 Cookie 更新，随后自动关闭，不需要终端 Enter。只在内存比较，不输出 Cookie 值或散列；更新不证明用户已扫码或认证通过，真实列表另验。超时／窗口关闭返回部分完成，不自行重登或重放请求。

当前发现入口只接受已有两份公开样本推导的号与标识组合。环境允许且项目专用登录有效后，可使用 `weread-plan` 给出的对应标识；无需用户再手抄 Cookie 或找标识。通过正式授权通道已可运行浏览器及 HTTPS；本轮两号首轮均 HTTP 200／-2012，会话更新后猫笔刀返回 -2041，已停止相关请求。下面保留入口说明，不能按旧结果反复重跑：

```bash
.venv/bin/python -m validation discover --account 猫笔刀 --book-id MP_WXS_3198966508 --max-pages 3
.venv/bin/python -m validation discover --account stormzhang --book-id MP_WXS_3085404720 --max-pages 3
```

## 自研 HTTP 与评论快照

```bash
.venv/bin/python -m validation http-fixture
.venv/bin/python -m validation http-archive --sample maobidao
.venv/bin/python -m validation mp-discover --account 猫笔刀 --max-pages 3
```

`http-fixture` 不访问网络，保存构造正文、本地图与评论／回复数据；原页截图和真实时间未核实时整体为 partial，退出码为 2。其余两项为真实样本入口；来源命令缺少指定私有输入时以 blocked 停止、请求数为 0，不复用微信读书 Cookie，不自动采集微信凭证。

代码全部自行实现，借鉴 exporter 的协议与分层。HTTP 路径不使用公共代理、不执行文章脚本、不修改原页截图；具体输入位置、字段、产物与协议差异见 [自研 HTTP 路线](/Users/chenge/project/liumo/docs/http-route.md) 。

每次最多 3 页，页间间隔 2 秒。它不回退为只取最新一篇，不请求文章正文，不根据观察到的时间字段宣称已核实发布时间。JSON 输出不保存原始响应、请求头或凭证。探针参数来自固定提交的参考实现，适用性需真实样本验证。

只检查两号第一页的返回结构，可在项目目录运行：

```bash
.venv/bin/python -m validation mp-diagnose --account all --transport curl
```

该命令读取已有项目凭证，两号各最多请求 1 次，间隔 2 秒；只保存固定字段的类型、数量和数字错误码，不保存文章正文、原始响应、凭证或上游错误文本。结果在本机 `archives/feasibility/*-mp-diagnostic-pair/`，退出码 2 表示诊断不构成来源验收。不会重新采集、登录或修改系统配置。

HTTP 默认仍使用 Python；`mp-discover` 和 `mp-diagnose` 可显式指定 `--transport curl`。curl 使用当前 Mac 的 `/usr/bin/curl` 8.7.1，禁用个人 curl 配置、环境代理、重定向和重试，保留 TLS 校验；敏感 URL／头部只经子进程 stdin，响应上限 10 MiB、总时限 20 秒。不会在失败后自动换传输重试。

核对已捕获凭证对应的两篇固定文章：

```bash
.venv/bin/python -m validation sample-check --transport curl --browser
```

程序串行处理猫笔刀和 stormzhang 的指定样本，不请求文章列表。每篇先校验号与文章标识，正文只向原样本地址发送已有 Cookie；本地配图下载不带凭证，最多 10 次图片请求、12 次评论／回复 API 请求。缺凭证、跨号或正文拒绝时停止相应后续请求，不匿名回退。去掉 `--browser` 即仅核对 HTTP 分项。

`--browser` 在 HTTP 访问、身份和评论状态门槛通过后，使用独立无头 Chrome 原页截图，不要求手动开页面或按 Enter。Cookie 仅在内存中按 HTTPS 文章主机设置，属性重建为 secure／session／Lax，原属性未知并记录；不写浏览器会话、不改变原页布局。产物在新建的 `archives/feasibility/*-credentialed-samples/` 及其引用目录，保留截图时间、范围和失败原因；整体返回 not_verified／退出码 2，每篇保留 blocked／failed／partial 等分项状态，等待实际证据和图像审阅。不会采集新凭证、改系统或启用订阅。

检查正常公众号主页的会话前置条件：

```bash
.venv/bin/python -m validation profile-context
```

该入口使用 Python HTTPS，两号各一次主页；仅在公开身份与会话字段均符合时再各一次列表，间隔 2 秒。新会话值只留内存，不写凭证；结果写入新的 `archives/feasibility/*-profile-context-pair/`。输出为 not_verified，退出码 2；结构观察不等于来源验收。任务用 `*-bridge` 入口只发布私有 FIFO 状态，需 Agent 控制器配合，使用方式与严格跳转边界见 [HTTP 说明](/Users/chenge/project/liumo/docs/http-route.md) 。

## 本机凭证实验准备

C17 的独立单次入口为 `.venv-capture/bin/python -m validation article-functional-session`，恢复入口为 `.venv-capture/bin/python -m validation article-functional-recover`。该单次目录已使用；功能核对入口 `.venv/bin/python -m validation.functional_check` 以不可覆盖标记限制为一次，重复运行只拒绝。取样、重复保护及数据位置见 [使用说明](/Users/chenge/project/liumo/docs/article-functional-validation.md) 。

查看不读取凭证、不访问网络的 C18 固定方案：

```bash
.venv/bin/python -m validation.functional_check --observation-plan
```

`--observation-once` 是另行明确授权后的单次功能观测入口，必须同时持有本机私有授权记录、原 C17 的固定失败回执和已验收恢复状态；缺少条件时停止。仍只使用同一固定文章候选，正文最多一次，身份通过后评论最多一次，每次 20 秒；保留 TLS 校验和原有本机上游，不重采凭证或修改系统。新尝试及结果使用独立文件，旧标记和回执保留。授权记录不由查看方案或运行该入口自动生成；具体字段、验收与证据见 [C18 施工边界](/Users/chenge/project/liumo/goals/20261017-1606-wechat-session-validation.md#c18传输观测补齐与无凭证只读对照) 。

独立核对本机 curl 的尺寸行为，不访问微信或外网、不读取凭证：

```bash
.venv/bin/python -m validation.curl_size_probe
```

该程序通过私有临时 Unix socket 提供固定构造 HTTP 响应，依次观察小响应、已知长度超限、分块超限、恰好等于 2 MiB 及提前中断。临时 socket 自动清理，固定数值结果写入新的 `archives/feasibility/*-curl-size-offline/size-summary.json`。本地权限不可用时停止并返回退出码 2；完成观测时返回 0，是否符合上游预期另看 `all_cases_match_upstream_expected`。它不测试 TLS 或账号功能，不发送真实文章请求。

查看 C19 同一候选的固定尺寸对照方案：

```bash
.venv/bin/python -m validation.functional_check --bounded-body-plan
```

该只读命令不读取凭证或联网。执行入口 `--bounded-body-once` 必须有另行明确授权的私有记录并绑定 C18 回执哈希；正文上限 10 MiB，评论仍 2 MiB，其余请求条件沿用 C18。标记和结果分别为 `functional-bounded-body-attempt.json` 与 `functional-bounded-body-result.json`，旧尝试保持原样，失败也不重跑。实际边界与验收见 [C19 清单](/Users/chenge/project/liumo/goals/20261017-1606-wechat-session-validation.md#c19正文尺寸单变量核对) 。

正文按固定参考的带凭证路径构造：公开文章 URL 加 `pass_ticket`／`wap_sid2` Cookie；`uin`、`key`、`appmsg_token` 等 API 字段保留在评论接口。缺必要 Cookie 时在请求前失败，不匿名回退。查看 C20 固定核对方案：

```bash
.venv/bin/python -m validation.functional_check --cookie-body-plan
```

该命令不读取凭证或联网。真实入口 `--cookie-body-once` 需新明确授权与绑定 C19 回执哈希的本机私有记录；仍同候选正文／条件满足后的评论各最多一次、每次 20 秒，正文 10 MiB／评论 2 MiB。标记和结果使用 `functional-cookie-body-` 前缀，原三次均保持原样。授权、HTTP 302 停止及分项验收见 [C20 清单](/Users/chenge/project/liumo/goals/20261017-1606-wechat-session-validation.md#c20纠正正文鉴权构造) 。

```bash
.venv/bin/python -m validation capture-plan
.venv/bin/python -m validation capture-fixture
.venv/bin/python -m validation capture-preflight
```

`capture-plan` 只显示实验配置及授权／恢复前提，不启动代理或生成 CA；具体授权状态以施工记录为准。`capture-fixture` 只处理虚假字段，检查私有落盘、过滤和停止，输出不含凭证的摘要；不会使用本机微信会话或访问网络。

`capture-preflight` 只读识别活跃网络服务和原代理配置，短暂检查回环端口能否绑定后立即关闭；不信任证书、不切换代理、不读取账号。完整配置只写入项目 `.auth/wechat-capture/baselines/` 的 0600 文件，普通输出仅含状态与私有文件路径；基线保存成功也不代表恢复控制或真实采集通过。

自研采集匹配模块及默认关闭的组件适配器见 [阶段报告](/Users/chenge/project/liumo/docs/wechat-session-validation.md) ，操作范围及恢复要求见 [操作提案](/Users/chenge/project/liumo/docs/wechat-session-operations.md) 。审阅输出中的底层命令不应直接运行；它不包含操作系统恢复控制。

当前 Mac 的可选实验组件独立安装于 `.venv-capture/`，固定依赖见 [requirements-capture.txt](/Users/chenge/project/liumo/requirements-capture.txt) 。该文件对应 macOS arm64、Python 3.14 的实验环境，不影响原 `.venv/`。在正常可访问 PyPI 的终端重建时：

```bash
python3 -m venv .venv-capture
.venv-capture/bin/python -m pip install --only-binary=:all: --require-hashes -r requirements-capture.txt
.venv-capture/bin/python -m pip check
.venv-capture/bin/mitmdump --version
```

安装不启动代理、不信任证书、不激活进程捕获或系统扩展。回归会在该可选环境存在时验证组件的真实头部对象；这仍不是实际 TLS 流量采集验证。

已执行结束的一次终端实验使用如下私有基线输入；以下保留为复现说明，已有实验目录会拒绝重跑，不应删除目录再次执行：

```bash
.venv/bin/python -m validation capture-session --baseline /Users/chenge/project/liumo/.auth/wechat-capture/baselines/202610170845537727700000-proxy.json
```

该入口只接受当前已启用、无认证且 HTTP／HTTPS 配置一致的本机原代理，自动衔接上游。程序先核对原值、生成私有恢复配置、检查证书主机约束，再验证代理往返。显示采集就绪后，在 Mac 微信中正常打开两篇样本；首次系统认证由用户完成。两号凭证保存、取消或最长 10 分钟到期后，独立工作进程恢复本次改动。恢复及进程停止均通过时，对已采集账号各运行一次最多 3 页的来源探针；不重新匿名请求正文，不启用正式订阅。

产物与最小状态写入新的 `archives/feasibility/*-capture-session/`，完整配置和本次证书仅在 `.auth/wechat-capture/session/`；已有实验目录会被拒绝，不能直接重跑。退出码 2 表示整体仍需核验，恢复结果以 recovery 字段为准。故障时按 [操作说明](/Users/chenge/project/liumo/docs/wechat-session-operations.md) 使用 `capture-recover`，不自行删除目录或覆盖系统原值。

## 主页／列表限定实验

第二次单独获准的实验已执行结束，固定目录保留。以下启动命令为该次操作说明，已有目录会拒绝再次执行：

```bash
cd /Users/chenge/project/liumo && .venv/bin/python -m validation profile-capture-session
```

程序自行取得新基线、确认上次实验已收尾、验证原值往返和本次主机限定证书信任。显示采集就绪后，在 Mac 微信中正常进入猫笔刀、stormzhang 的公众号主页并查看文章列表；无需按 Enter 或复制字段。系统认证由用户完成。收到两号列表并各完成一次即时核对、Ctrl+C 或最多 10 分钟到期后恢复代理与本次信任。

仅匹配两号 `/mp/profile_ext` 的 home／getmsg 请求，过滤后的必要查询、头部及 Cookie 保存在 `.auth/wechat-capture/profile-session/requests/`，0600 文件、0700 目录；不保存原始 URL、完整头部或流量、不读取经过代理的响应正文，不覆盖旧文章凭证。每号首次零偏移列表候选在 30 秒新鲜度内最多独立核对一次，使用系统 curl、同一 HTTPS 端点、TLS 校验和既有响应上限；失败不追加重试。过滤重建不等于完整原请求重放，列表身份、时间和分页仍独立核对。

该固定实验目录不可重跑。摘要保存到新的 `archives/feasibility/*-profile-capture-session/`；实时状态在本次私有 `state.json`／`capture.json`，只含固定状态与脱敏计数。恢复结果以 recovery 与 proxy_process_stopped 为准，退出码 2 不等于系统恢复失败或功能通过。故障时使用本次独立入口：

```bash
.venv/bin/python -m validation profile-capture-recover
```

恢复入口只检查本次实验；已记录恢复并停止的旧实验再次调用恢复时不改当前系统，也不声称重新核实了现状。两套实验目录保留，不能删除目录来续用授权。完整授权和现场检查见 [操作说明](/Users/chenge/project/liumo/docs/wechat-session-operations.md) 。

## 无凭证短诊断

`transport-diagnostic-session` 提供固定 120 秒的诊断入口，不采集 Cookie／令牌、不读取已有文章凭证或请求文章列表。该入口涉及新的单次证书／代理实验，须先取得对应明确授权，不能复用已结束实验的授权：

```bash
.venv/bin/python -m validation transport-diagnostic-session
```

程序先取得新基线，并核对前两次实验的恢复／停止记录；新实验目录为 `.auth/wechat-capture/diagnostic-session/`，已有目录拒绝重跑。设置与原值往返检查通过后，只向固定公开控制地址发一次无凭证 HTTPS 请求，显式使用本次回环代理和 CA 校验，正文直接丢弃。控制传输和代理侧控制请求／响应计数均成立后，才提示在 Mac 微信刷新猫笔刀主页一次；否则立即收尾。

控制流量与普通页面流量分开计数，TLS 仅记目标／其他／未知主机类别，不保存其他域名、任意路径或错误原文，不生成凭证文件。120 秒从实验计划创建时计起，Ctrl+C 或到期均恢复；设置与收尾的系统命令可能延长程序退出时间，实际恢复仍需核对。结果保存在新的 `archives/feasibility/*-transport-diagnostic-session/`，只说明传输阶段，不能作为账号、列表或归档验收。

本次独立恢复入口为：

```bash
.venv/bin/python -m validation transport-diagnostic-recover
```

诊断摘要另提供目标主机 TLS 错误的固定分类，不保存错误原文；分类描述组件消息，不证明证书固定等根因。Python 函数 observation_snapshot 可在运行窗口内取得刷新前／后时间与白名单计数，拒绝已结束、控制未通过或畸形状态；函数不执行 UI 操作、不写标记，也不把取样当作刷新成功。

具体范围、控制门槛及恢复边界见 [操作说明](/Users/chenge/project/liumo/docs/wechat-session-operations.md) 。

## Agent 操作的单次诊断

已明确授权、目标主页可安全确认后，可在普通终端启动独立的 120 秒诊断：

```bash
.venv/bin/python -m validation ui-transport-diagnostic-session
```

该入口核对旧三次实验均已恢复／停止，使用不可重跑的 ui-diagnostic-session 目录，不采凭证或请求文章列表。控制链路通过后由 Agent 记录前后样本并刷新目标主页，终端保持运行；到期恢复和摘要输出沿用原控制器。专用恢复命令为 `ui-transport-diagnostic-recover`，不得替换成旧实验恢复入口。实际操作与权限边界见 [操作说明](/Users/chenge/project/liumo/docs/wechat-session-operations.md) 。

## 文章页对照诊断

该入口用于一次另行授权的 120 秒文章页对照，保留前四次实验目录；只统计无凭证流量类别，不请求文章列表或评论接口。先在 Mac 微信中将猫笔刀固定样本文章单独前置、隐藏聊天，待 Agent 确认目标后，再在普通终端启动：

```bash
.venv/bin/python -m validation article-transport-diagnostic-session
```

控制通过后由 Agent 保存前后取样并刷新该文章一次；不要自行刷新或关闭终端。代理／信任和恢复边界沿用原控制器，只使用 HTTPS 代理与用户级目标主机限定信任。输出为新的 `archives/feasibility/*-article-transport-diagnostic-session/session-summary.json`；固定私有目录为 `.auth/wechat-capture/article-diagnostic-session/`，已存在即拒绝。该次专用恢复入口为 `article-transport-diagnostic-recover`，只在该次恢复确实需要时使用。详见 [操作说明](/Users/chenge/project/liumo/docs/wechat-session-operations.md) 。

## 离线证书域名约束

使用已有可选隔离环境签发构造证书，以内存 TLS 握手和本机显式证书验证评估域名约束；不安装证书、不搜索钥匙串、不监听或访问微信，不修改实际采集配置：

```bash
.venv-capture/bin/python -m validation certificate-scope-fixture
```

每次写入新的 `archives/feasibility/*-certificate-scope-offline/`，只保留公共证书和结果，临时私钥自动清理。macOS 使用 verbose 获取固定数字错误和信任结果；CT 提示不是独立失败原因，只有有效信任决定才作为接受／拒绝依据。`partial`／退出码 2 表示仍有验证器或真实微信项未通过，不能把单个离线矩阵通过当作可部署结论。组件已在原有隔离环境安装，此命令不安装依赖。方法与结果边界见 [离线报告](/Users/chenge/project/liumo/docs/certificate-scope-offline.md) 。

## 调度配置

[调度示例](/Users/chenge/project/liumo/examples/local.liumo.feasibility.plist) 是已生成的审阅文件，只调用不访问微信的轻量任务。需要重新生成时指定尚不存在的输出路径：

```bash
.venv/bin/python -m validation config --output .tmp/feasibility/review.plist
plutil -lint .tmp/feasibility/review.plist
```

配置使用每分钟日历触发，由 Python 按 `Asia/Shanghai` 门控四个检查点及合并补查，不依赖系统当前时区。不自动复制到 LaunchAgents，不调用 `launchctl`，也不改变休眠或系统时区。

## 文档入口

- [自研 HTTP 路线](/Users/chenge/project/liumo/docs/http-route.md) ：实际命令、凭证输入边界、产物与证据范围。
- [本机凭证验证](/Users/chenge/project/liumo/docs/wechat-session-validation.md) ：C0／C1 阶段交付、构造与真实证据分级；[操作提案](/Users/chenge/project/liumo/docs/wechat-session-operations.md) ：实际命令、待授权范围与恢复门槛。
- [exporter 机制研究](/Users/chenge/project/liumo/docs/exporter-mechanism.md) ：固定源码的采集、评论、凭证与导出流程，以及每日追更的借鉴范围。
- [GitHub 方案调研](/Users/chenge/project/liumo/docs/github-solutions.md) ：三组候选的当前一手资料、固定版本和能力边界。
- [产品设计](/Users/chenge/project/liumo/PRODUCT_DESIGN.md) ：一页纸产品定义、数据流图、存储规则与技术候选。
- [Roadmap](/Users/chenge/project/liumo/ROADMAP.md) ：真实进度、待验证清单与下一步执行顺序。
- [项目规则](/Users/chenge/project/liumo/AGENTS.md) ：工作流、工程边界与验证要求。
- [可行性结论](/Users/chenge/project/liumo/docs/feasibility.md) ：最多三条候选路线、证据等级及剩余条件。
- [Goal 施工记录](/Users/chenge/project/liumo/goals/20261016-2359-feasibility.md) ：授权、检查点与验收状态。
- [验证证据](/Users/chenge/project/liumo/evidence/feasibility/tests.json) ：必要测试与明确跳过项。

数据流图使用 Mermaid；在支持 Mermaid 的 Markdown 阅读器中可渲染，也可直接阅读图的源码。
