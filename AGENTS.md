# liumo 项目规则

## 项目定位与导航

liumo（留墨）是个人公众号新文章自动归档项目；当前单号 RSS 版本保存 Markdown、本地配图及来源信息，原页截图暂缓。

- 优先遵守用户全局 `AGENTS.md` 和用户最新明确指令；本文件仅补充项目业务与工程约定，不额外收紧全局授权原则，是项目规则唯一内容源。
- 进入项目先读本文件和 [ROADMAP.md](/Users/chenge/project/liumo/ROADMAP.md) 。
- 产品定义、数据流、工程边界和选型候选见 [PRODUCT_DESIGN.md](/Users/chenge/project/liumo/PRODUCT_DESIGN.md) ；当前使用入口见 [README.md](/Users/chenge/project/liumo/README.md) 。
- 产品设计中的「已确认」来自用户明确需求；「建议」和「待验证」不能表述为已确认或已实现。

## 结构与工作流

- 根目录维护项目规则、产品设计、当前进度和使用入口；不复制归墟的知识编译体系。
- `goal/` 保留用户指定的 V1 路线重定向清单与验收记录；新增独立 Goal 按全局规则保存于 `goals/`，已有记录不搬移、不覆盖；V1 不开展旧实验路线。`validation/` 保存可行性验证程序，不作为已完成的 MVP；`tests/` 保存逻辑与页面构造样本测试；`examples/` 保存脱敏输入与页面样本；`docs/` 保存可复用技术结论；`evidence/` 只保存不含凭证的验证摘要与来源索引。新增子目录沿用所属目录职责。
- `validation/js/` 仅保存离线 JS 语法分析辅助程序及固定 npm 清单，`validation/inline_scripts.py` 负责受限子进程与输出校验；Acorn 只解析输入，不执行文章脚本。输入只经 stdin／内存，输出限定类别与计数，不输出源码、AST、任意名称、值或解析错误原文；不下载页面脚本或连接微信。静态调用形状不证明实际运行、变量绑定或完整调用链。依赖仅安装于该目录，禁用生命周期脚本和用户 npm 配置。
- 真实文章、截图和本机验证结果保存在忽略的 `archives/`；浏览器专用会话保存在忽略的 `.auth/`，不得使用或读取其他应用的账号会话。临时下载、测试运行结果和依赖缓存保存在 `.tmp/feasibility/`。
- 归档内容、任务状态、日志、浏览器会话与凭证属于本机数据，按 `.gitignore` 隔离；示例必须脱敏。
- 临时试验放入 `.tmp/<task-slug>/`；可复用的调研结论写入产品设计，实际证据与进度摘要写入 Roadmap。
- 开发前先明确目标、边界、失败路径和验收方式；按「设计 → 技术验证 → 单篇归档 → 自动闭环 → 真实试用」推进。

## 工程边界

- 自动追更是 MVP 必需能力；手动输入链接用于验证和补救，不能替代自动追更验收。
- 用户已授权新增任意公众号文章链接的独立 `save` 入口，立即读取原文，不依赖 RSS；正文与本地配图归档，评论不请求、截图暂缓。职责见 `liumo/manual.py`，数据分属 `state/manual/`、`archives/manual/` 和 `.auth/manual-article/`，不改变自动追更账本或历史导入。仅使用项目专用正常浏览器会话，验证由用户正常完成，不轮换账号／UA 或自动操作验证码；无访问权限、付费、删除、身份未知均不得标完整。施工见 [链接归档 Goal](/Users/chenge/project/liumo/goals/20261022-0800-manual-url-archive.md) 。
- V1 按用户最新确认交付 RSS 内容快照版：保存 RSS 提供的正文、本地配图及公开原链接；暂缓原页截图与原文发布时间核实，原文时间明确待核实，新增内容按启用后的首次发现暂存。RSS 内容完整性不能冒充已对照原文验证。不请求评论，记录 `not_requested`；截图记录 `deferred`，不伪造原页图片。
- 自动追更维持猫笔刀单号，以 Wechat2RSS 公开 RSS 发现群发文章；历史入口已验收指定公众号、给定 RSS 输入及日期范围的处理能力；猫笔刀 2026 年全年覆盖仍未交付，来源清单尚缺。来源保留窗口不足时必须报告缺口，不能把可见窗口存完等同全年完成。stormzhang 自动追更与微信读书来源退出当前 MVP；历史记录保留。评论／代理／证书／页面脚本实验不进入运行链。
- `liumo/` 保存单号 MVP 的 RSS 解析、RSS 快照归档、SQLite 状态与命令入口；原页诊断仅保留显式入口。`tests/test_mvp*.py` 保存对应失败路径及本地页面集成测试。正式共享实现位于 `liumo/common.py`、`render.py`、`browser.py`、`schedule.py`、`notify.py`；旧实验单向引用正式实现，正式运行不得导入 `validation`。浏览器驱动仅显式请求页面时加载，不调用旧实验控制器或凭证入口。`state/` 保存忽略的本机状态；正式文章在 `archives/maobidao/`，样本在独立忽略目录；运行不依赖 `.tmp/`。
- 内容主存储使用可独立阅读的文件；运行时不默认接入大模型。
- `liumo/integrity.py` 负责三类归档的离线只读核验，`liumo/repair.py` 负责显式单篇恢复；两者不进入每分钟 tick 的全库扫描。账本 complete 与文件完整性分别报告，修复先校验新产物再发布引用，旧文件保留。入口、互斥、数据范围与验收见 [完整性说明](/Users/chenge/project/liumo/docs/archive-integrity.md) 。
- 新文章发现与单篇归档分开实现；只为当前公众号需求编写必要模块，不预建通用插件或爬虫框架。
- exporter 只作为协议与设计参考，运行代码全部自行实现，不复制上游源码。HTTP、评论快照和凭证输入分别位于 `validation/http.py`、`validation/comments.py`、`validation/credentials.py`；HTTP 正文归档位于 `validation/http_archive.py`，Credential 列表候选位于 `validation/mp_source.py`。不默认使用公共代理、抓包、安装证书或修改系统代理，原页截图仍独立验收。
- 实验执行不再附加逐轮授权、固定一次目录、新授权文件或前次回执哈希等审批门槛；已明确授权且对象、数据与操作范围不变的工作，按全局规则连续执行，只在关键歧义、范围扩大或新的重大风险时确认。系统和平台权限要求仍须遵守。
- 每次运行可自动分配唯一运行目录以隔离数据，但目录不是授权单位；不覆盖旧归档、凭证、回执或删除标记获得重试。保留请求边界、有限重试、并发互斥、TLS 校验、凭证保护及实际系统恢复验收，不把取消重复审批理解为无限请求或扩大数据范围。
- 旧实验的程序职责、字段范围和恢复说明见 [历史实验约束存档](/Users/chenge/project/liumo/docs/legacy-experiment-constraints.md) 。其中逐轮授权和单次目录审批条款已作废，不再作为现行项目规则。旧程序仍可能硬编码这些门槛，文档变更不等于代码迁移；若未来确需复用，应先按现行范围调整实现并验证，不伪造授权记录或绕过程序保护。V1 当前不运行这些历史实验。
- 当前环境权限应在受支持的工具或客户端配置中解决；记录实际失败及未验证范围，不反复要求用户代跑命令，不通过普通终端、其他应用或更换通道绕过明确权限门禁。需要用户扫码、认证或真正新增授权时，集中说明具体动作及原因。
- `complete` 以具体 `archive_kind` 的正文、配图与元数据验收：RSS 为 `rss_snapshot`，手动原文为 `manual_page_snapshot`；两者都不表示含评论／截图的整页归档。原文时间须独立核实，否则明确待核实；截图暂缓。旧实验结果不追溯改为通过。默认 RSS 追更不打开原文或读取账号会话；用户显式 save 才使用独立项目浏览器读取文章，旧原页样本入口不自动运行。
- 运行设备为当前 Mac；按 `Asia/Shanghai` 每天 22:00、22:30、23:00、23:30 检查。离线恢复后在窗口外补查一次，错过多次合并；本机通知保留未来微信接入位置，当前不实现微信通知。
- 用户级后台任务固定为 `local.liumo.maobidao`，配置位于 `/Users/chenge/Library/LaunchAgents/local.liumo.maobidao.plist`，只调用项目 tick。安装、启停及恢复按用户对应指令执行，先核对该任务和配置身份，不覆盖同名不同配置、不触碰其他任务。操作与证据见 [后台运行说明](/Users/chenge/project/liumo/docs/maobidao-scheduler.md) 。
- 初始化时列表已有条目只建基线，不自动补历史。后续按首次发现暂存 RSS 新条目，上游延迟可能带来早于启用时间的发布；原文时间未核实就不作发布时间边界已通过声明。补抓受来源可访问范围约束，不承诺永久零漏存。
- 历史导入使用独立本机账本和归档目录，不改追更基线、启用时间或调度。日期筛选以 RSS pubDate 转换到 Asia/Shanghai 后的日期为准，包含首尾日期；缺失／无效时间单独报告，不能用发现时间顶替。历史文件、正文及运行报告仍留在忽略目录，已有快照与变稿不静默覆盖。施工与全年验收见 [历史归档清单](/Users/chenge/project/liumo/goals/20261020-2339-rss-history.md) ，历史代码可随明确授权的工程快照版本化，是否交付以 Roadmap 验收状态为准；各标签的具体内容见版本管理说明。
- 原文和已有归档不得静默覆盖、删改或用 AI 改写替代；检测到同源内容变化时保留旧结果并报告。
- 登录失效或访问受限时记录并停止相关请求，不绕过验证码、付费边界或访问控制；凭证不进入代码、Git、普通日志或外部不可信服务。
- liumo 与 guixu 独立维护；归档结果不自动触发归墟入库。

## 验证与交付

- Git 使用 `dev` 作为日常开发分支、`main` 作为通过相应检查的集成分支；同步优先使用 `--ff-only`，出现分叉先核对，不自动生成合并提交。基线采用附注 tag，指向 `main` 已核对的提交，再切回 `dev`；工程基线不代表产品试用验收完成。首次建仓及公开范围见 [版本管理说明](/Users/chenge/project/liumo/docs/version-control.md) 。
- 验证事项和顺序以 Roadmap 为准；技术候选未经当前官方资料核对和样本验证，不写成已确定方案。
- 文档修改后检查 Markdown 结构、内部链接、需求对应关系和已确认／建议／待验证状态。
- 当前 MVP 入口为 `.venv/bin/python -m liumo --help`，历史验证入口仍为 `.venv/bin/python -m validation --help`；必需检查为 `.venv/bin/python -m unittest discover -s tests -v` 和 `.venv/bin/python -m tools.check --static-only`；分层测试及环境契约见 [开发说明](/Users/chenge/project/liumo/docs/development.md) 。浏览器集成测试必须显式使用 `LIUMO_BROWSER_TESTS=1`；跳过不等于通过。复现步骤及权限边界见 [README.md](/Users/chenge/project/liumo/README.md) 。
- `tools/` 只保存只读静态质量检查与显式分层测试入口；核心依赖在 `requirements-core.txt`，可选页面依赖在 `requirements-browser.txt`，根依赖清单保留兼容安装入口，旧抓包环境独立。
- 完成实现或影响项目状态的文档变更后更新 Roadmap；完成和验证记录使用操作时获取的北京时间。
- 文件写入不包含 Git 提交、推送、公开发布、账号登录或安装系统调度的授权；后续按具体任务范围执行。
