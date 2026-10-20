# C27／C28：内联脚本分析与限定取证

C27 独立离线 JS 分析已通过构造自测；C28 已执行并关闭，正常微信正文身份通过、AST 因本地节点上限未完成，整体 partial。C26／C28 原始 HTML 未保存，不能追补解析，已消耗的授权与目录均不复用。

## 组件与证据

已有标准库 HTMLParser 和词频无法区分现代 JS 中的注释、字符串与调用表达式，因此引入 Acorn，仅解析 AST，不执行输入。`validation/js/` 只承担该离线辅助职责，唯一直接依赖固定为 8.19.0，不安装全局依赖。

2026-10-19 查询的一手资料：[官方 package.json](https://github.com/acornjs/acorn/blob/master/acorn/package.json) 显示 8.19.0、MIT、无运行时依赖；该文件 blob 为 806bfc98b4bb9759ae970bd27dbe284a66905723。[固定提交的 CHANGELOG](https://github.com/acornjs/acorn/blob/ecd9b4260daaf0566db2f0fcc623791a9c75241f/acorn/CHANGELOG.md) 记录 2026-10-05 发布 8.19.0；[官方解析 API](https://github.com/acornjs/acorn/blob/ecd9b4260daaf0566db2f0fcc623791a9c75241f/acorn/README.md) 说明 parse 返回 ESTree，并支持 script／module 语法。该提交日期为 2026-10-14；[近期 issue](https://github.com/acornjs/acorn/issues/1471) 的关闭记录提供有限维护证据，不保证没有缺陷。实际 npm 安装包及本地完整性已核对，详见下节。[机器可读记录](/Users/chenge/project/liumo/evidence/feasibility/inline-script-preparation.json) 。

## 实际安装与完整性核对

2026-10-19 00:44 前两次 Agent 安装返回 ENOTFOUND 的历史保留。随后用户普通终端显示 added 1 package in 2s；Agent 本地核对安装／加载／lockfile 均为 8.19.0，来源为官方 HTTPS 注册表。缓存包 134282 字节的 SHA-512 与 lockfile 的 integrity 一致，包内 10 个文件与安装内容逐一匹配；构造脚本解析通过。该校验确认本地安装与锁定包一致，不是额外的发布者签名验证。

以下为用户已成功执行的本次安装命令，使用两个空配置、禁用生命周期脚本／审计／fund、限制网络重试；当前无需重跑。它依赖本轮项目临时空配置，仅作现场复现记录：

```bash
cd /Users/chenge/project/liumo
env -i PATH=/opt/homebrew/bin:/usr/bin:/bin LC_ALL=C \
  npm install --prefix /Users/chenge/project/liumo/validation/js \
  --userconfig=/Users/chenge/project/liumo/.tmp/wechat-session-validation/c27-user.npmrc \
  --globalconfig=/Users/chenge/project/liumo/.tmp/wechat-session-validation/c27-global.npmrc \
  --cache=/Users/chenge/project/liumo/.tmp/wechat-session-validation/npm-cache \
  --registry=https://registry.npmjs.org/ --fetch-retries=0 --fetch-timeout=20000 \
  --ignore-scripts --no-audit --no-fund
```

实际清单和 lockfile 均保存在 `validation/js/`；机器可读完整性和回归结果见本页证据入口。没有更换镜像、关闭 TLS 或修改系统设置。

## 无网络复现

```bash
.venv/bin/python -m validation.inline_scripts --fixture
.venv/bin/python -m unittest discover -s tests -p test_inline_scripts.py -v
.venv/bin/python -m unittest discover -s tests -v
```

辅助入口也接受 stdin JSON 数组，每项严格为 source／source_type，source_type 只接受 script 或 module。不接受源代码命令行参数或任意文件路径；构造输入不含真实凭证。结果只输出固定计数及状态，退出 0 表示静态分析完成，退出 2 表示失败或部分分析；退出 0 不代表文章、评论或网络鉴权通过。

`validation/js/analyze.mjs` 只做 Acorn 语法解析与 AST 遍历；`validation/inline_scripts.py` 校验输入、限制子进程并校验输出 schema。识别范围仅包含 `/mp/appmsg_comment`、`/mp/getappmsgext` 的字面量／受限静态拼接、fetch／ajax 调用形状和 WeixinJSBridge.invoke 形状。结果不输出完整 URL、query、任意属性／方法名或代码。普通字符串与调用候选分开计数；ajax 的 spread、重复 url 或计算属性均标记动态未知。

不解析变量绑定、别名、完整调用图或任意常量传播；fetch／ajax 名称可能被遮蔽，计数只是语法形状。动态构造地址、原生桥接结果及未分析脚本不能由静态结果排除。C28 的 HTML 连接仅完成构造验证，没有分析真实新响应或抓取外部脚本。

## 实现及验收边界

输入只经 stdin 和受限子进程内存，输出限固定协议类别、数量和失败码；不输出源码、AST、任意字符串／名称／参数／解析异常。禁止执行文章代码、动态求值、下载外部脚本、读取账号或旧凭证。静态调用候选不冒充实际网络调用。

输入 JSON 最多 9 MiB、最多 128 段源码、源码 UTF-8 合计 4 MiB、访问节点最多 200000、静态字符串最多 2048 字符及 12 层静态拼接；父进程限制 10 秒、Node old-space 上限 256 MiB、输出最多 8192 字节。old-space 不等于操作系统进程总内存硬限制。错误仅返回固定类别；Acorn 的栈耗尽转换为固定资源失败，不输出异常原文。

12 项专项构造测试覆盖注释／字符串／调用、转义／拼接／模板、现代 module 语法、动态值、ajax 歧义、输入不执行、语法部分失败、输入／节点／栈资源拒绝及 CLI。超时、异常退出和恶意子进程输出保护用故障注入验证，不能当作实际设备超时实验。新的微信取证、评论通道、完整截图及原 Goal 仍未完成。

## C28：一次 HTML 内存连接实验

目的：正常微信取得固定猫笔刀文章的一份 HTML，在内存中核对独立文章身份后，分析内联 JS，区分文本词频与静态调用候选；同时解释外部脚本来源被拒绝的固定形状。仍不取得评论内容或成功鉴权基线，不把零候选判为没有评论。

`validation/html_inline.py` 复用既有 UTF-8、独立号／文章／标题／正文及受限内容门槛；通过后才允许 Node 启动。最多 128 个 script，经典 JS 的受支持类型与 module 分别解析，JSON 等已知数据类型和未知类型明确计数。它是保守类型子集，不声称覆盖浏览器所有脚本类型。外部代码一律不下载，即使 URL 在原公共白名单内也标明未覆盖；JSON 数据也不算 AST 已分析。

对外部 src 仅记录 accepted_public／invalid_shape／relative_source／non_https／unknown_host／authority_rejected／known_host_path_rejected 数量。拒绝来源的主机、路径、查询、片段及任意类型名不落盘；保留原白名单检查，不根据分类自动放宽或追加请求。

### 系统范围与授权

- 固定文章仍是猫笔刀《上个月最值的一笔消费》，一次圆形箭头刷新，最多一份被动响应；不访问列表、重放评论或下载脚本。编码／解压各 4 MiB，等价双头、严格 UTF-8 与独立身份门槛保持。
- 系统总窗口 180 秒、收尾预留 120 秒；沿用受约束的临时用户级 SSL 信任、当前网络服务 HTTPS 代理及原本机上游，一次公开控制请求。Node 最长 10 秒，取实际活跃窗口剩余预算的较小值；结束后再次检查门槛，过期结果丢弃，不写摘要。
- 仅 C28 将本次代理独立进程组及其继承的一个 Node 子进程纳入停止与不存在验收。当前子进程对象或严格命令身份、组归属明确后才发送 TERM／必要时 KILL；父进程不在而组仍在、权限不可用或身份未知均不算停止通过。旧模式不改变。
- 四项收尾为代理原值回读、临时信任有效撤销、上述进程组消失及私钥清理，独立验收。恢复失败优先处理，不继续实验。原始 HTML／JS／AST／Cookie／留言不保存；只写固定摘要到本次 0600 文件。
- C28 固定目录为 `/Users/chenge/project/liumo/.auth/wechat-capture/article-inline-session/` ，授权文件绑定已恢复 C26。C28 已由普通终端启动、读取一份响应并完成四项恢复，本次授权已消耗，不再执行 session／observe／finish；C26 亦不重跑。

### 复现与实际入口

无网络审阅和构造验证：

```bash
.venv/bin/python -m validation html-static-inline-plan
.venv/bin/python -m validation html-static-inline-fixture
.venv/bin/python -m unittest discover -s tests -p test_html_inline.py -v
```

fixture 包含一个未下载的外部脚本，预期整体 partial、退出 2，内联语法分项 passed；不能为了退出 0 隐藏覆盖缺口。

以下为已执行的 C28 历史入口，现已关闭，不再运行：

```bash
.venv-capture/bin/python -m validation html-static-inline-session
```

本次用户在控制门槛通过后反馈一次刷新，已匹配一份固定文章响应。独立恢复入口 html-static-inline-recover 保留，已验收恢复时只返回记录，不重新修改系统或采集。

构造验证覆盖身份先行、类型／来源固定分类、实际 mitmproxy gzip／等价双头与 Node 连接、原字节透传、一次写入、窗口过期丢弃、未授权拒绝及真实本机无网络的 Python／Node 进程组收尾；超时等故障注入独立标记。[C28 准备证据](/Users/chenge/project/liumo/evidence/feasibility/html-inline-preparation.json) 。

### C28 真实结果

2026-10-19 08:00 核对：HTTP 200／gzip，两条 Content-Type 完整归一化等价；编码 789880 字节、解码 3493944 字节，独立号／文章／标题／正文身份通过。57 个 script 中，经典 JS 53、module 2、外部 2、nomodule 属性 4，数据／未知类型 0。两条外部来源均为 known_host_path_rejected，只能认定命中既有静态主机而路径未通过，不能追补具体地址或拒绝子原因。

AST 返回 failed／node_limit：触发本项目代码中的累计 200000 节点遍历上限。当前实现触发后只保留固定失败码，未保存此前已处理脚本数或调用计数；不能据此推断真实调用不存在、解析语法失败或微信拒绝。整体 partial／html_inline_coverage_partial。原始 HTML／JS 按授权已丢弃，没有新 Markdown／配图／整页截图。

普通终端控制器 14.705 秒完成代理回读恢复、有效撤销、代理及 Node 进程组停止和私钥清理；公开材料身份、两份私钥不存在、0600 摘要、旧十三次回执及 355 项执行代码基线已独立核对。进程组和系统恢复决定依据本次控制器实际回执，不冒充 Agent 独立 ps／系统查询验证。[实际证据](/Users/chenge/project/liumo/evidence/feasibility/html-inline-live.json) 。

### 离线容量复核

```bash
.venv/bin/python -m validation.parser_capacity
```

该程序只生成 55 段高节点密度构造 JS，用临时分析器副本比较 200000 与候选 8388608 上限；不修改运行时、不接触真实 HTML／账号、不联网。源码量分别为本次实际 HTML 字节数 3493944 和 4 MiB，JSON／源码／脚本数／10 秒父进程限制及 Node old-space 256 MiB 保持。

| 构造源码字节 | 上限 200000 | 候选 8388608 | 候选耗时 | 候选遍历节点 |
| --- | --- | --- | --- | --- |
| 3493944 | node_limit，退出 2 | 55 段完成，退出 0 | 0.677 秒 | 3491235 |
| 4194304 | node_limit，退出 2 | 55 段完成，退出 0 | 0.788 秒 | 4191605 |

两次候选输出各识别 55 个构造 fetch 候选，构造秘密未回显。此数据证明现有 20 万节点限制不足以覆盖声明大小内的高密度合法输入；候选上限仅为离线测得可行，尚未采用，不保证真实脚本同样通过或能确定评论通道。

峰值 RSS 未验证。最初 time -l 包装器及独立公开控制均因 sysctl kern.clockrate 权限退出 1，不能计为容量通过；失败计量独立保留。之后直接 Node 的退出码与父进程单调时钟另验，不再读取受限指标。old-space 256 MiB 不等于进程总内存硬限制。[容量证据](/Users/chenge/project/liumo/evidence/feasibility/parser-capacity.json) 。

### 下一轮证据保留方式，待用户决策

现行方案丢弃原始输入，触发本地边界后无法离线复核，必须重新安排一次刷新。建议下一轮允许将同一固定猫笔刀样本的一份身份通过 HTML，编码／解码仍各 4 MiB，以 0700 目录／0600 文件、排他创建和内容哈希，保存在拟定的 `/Users/chenge/project/liumo/.auth/wechat-capture/article-offline-input-session/article-source.html` 。该路径在 Git 忽略范围内；后续仅离线解析该固定文件，避免因程序修正反复操作微信，原页面代码不执行。

该原始 HTML 可能含临时会话字段，属于扩大当前仅内存范围；不保证通过通用替换即可完整去敏。不得进入 Git、普通日志或对话，不读取／保存 Cookie 头，不增加评论／列表／脚本网络请求；只保存这一份固定样本，不开启历史归档或订阅。完成分析后再明确确认清理，不承诺后台定时删除。

这只是建议，当前规则与运行程序仍禁止保存原始 HTML／JS。用户可以选择继续仅内存并在离线修正后另做一次取证；受控本机保留方案必须先获明确的数据范围决策，再实现和自测，不能视作 C28 授权的延续。


2026-10-19 07:57：C28 本次授权已排他记录并绑定已恢复 C26；旧十三次关闭哈希及 71 份源码／配置对应的 355 项基线核对通过。用户确认文章前置／聊天隐藏，Agent 截图核对及 300 秒 UI 就绪已完成；系统只读预检仍返回 preflight_system_authorization_unavailable，尚未创建真实目录、改系统、刷新或读取 HTML，待普通终端启动本次入口，无需再次授权。原 Goal 未完成。[现场记录](/Users/chenge/project/liumo/evidence/feasibility/html-inline-live.json) 。
