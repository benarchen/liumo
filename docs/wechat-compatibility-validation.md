# 微信兼容验证：独立单次入口与恢复

2026-10-18 16:08：C16 单次文章兼容与限时收尾通过。普通终端启动后，安装前对照／不信任及安装后 17 项范围检查成立；控制 HTTP 200、代理控制计数各 1。Agent 对猫笔刀固定文章正常刷新一次，页面可读且未见证书警告；文章请求／响应从 0 增至各 1，普通目标域从 0 增至各 20，TLS 失败计数均为 0。约 60.3 秒完成代理回读恢复、明确有效撤销、进程停止及两份私钥删除，180 秒窗口内收尾通过。未采凭证或发列表／评论探针，不证明旧错误的唯一根因、两号兼容或凭证功能；236 项基线哈希未变，未重复运行代码测试。C16 已关闭，不重跑；原 Goal 未完成。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-compat-live.json) 。

## 单次运行与恢复（C16 已结束，保留复现说明，不可重跑）

```bash
cd /Users/chenge/project/liumo
.venv-capture/bin/python -m validation wechat-compat-session
```

正常终端保持运行；macOS 认证由用户完成，用户不要刷新。Agent 必须已在最近 300 秒实际确认目标文章且工具可用，写入项目私有临时 UI 就绪记录后，才允许创建固定一次目录；记录是前置门槛，不是刷新或兼容证据。失效时重新核对 UI，不让用户修改记录绕过。Agent 在控制通过及状态就绪后执行以下取样与一次界面刷新，随后请求收尾：

```bash
.venv-capture/bin/python -m validation wechat-compat-observe --phase before_refresh
# 只有确认文章与剩余时间后，Agent 才通过 Computer Use 执行一次正常刷新。
.venv-capture/bin/python -m validation wechat-compat-observe --phase after_refresh
.venv-capture/bin/python -m validation wechat-compat-finish
```

到期、预算不足、父进程退出或取消均进入恢复；不要求按 Enter。若自动恢复未通过，只运行本次独立恢复入口，不能重跑 session：

```bash
.venv-capture/bin/python -m validation wechat-compat-recover
```

状态与固定计数保存在 `.auth/wechat-capture/wechat-compat-session/`，终端结束后生成忽略的 `archives/feasibility/*-wechat-compat-session/session-summary.json`。系统预检失败不会生成一次目录或启动进程。若签发／写盘或工作进程启动前中断，可能留下本次私有材料，恢复入口仍以本次公开证书身份为准；未取得明确回执，不宣称清理成功。工作进程遭 SIGKILL、断电或无法识别遗留进程身份时需要人工检查，不能保证自动恢复。

程序入口为 [compat_session.py](/Users/chenge/project/liumo/validation/compat_session.py) ，组件适配为 [compat_addon.py](/Users/chenge/project/liumo/validation/compat_addon.py) 。`anchor_scope.Native` 只增加默认行为保持不变的证书身份钩子，C15 回归仍通过；旧实验目录、采集入口和凭证文件未改变。

## 离线程序与实测范围

```bash
cd /Users/chenge/project/liumo
.venv/bin/python -m validation wechat-compat-plan
.venv-capture/bin/python -m validation wechat-compat-fixture
.venv/bin/python -m unittest discover -s tests -v
```

审阅命令不生成证书或运行系统操作。构造命令使用已有 mitmproxy 12.2.3／cryptography 46.0.4，自行签发受约束 CA 和独立密钥的目标叶证书；根许可 `mp.weixin.qq.com`、排除子域与全部 IP。根与固定叶有效期 20 分钟。所有私钥仅在本次唯一 0700 临时目录，文件 0600，成功或可处理异常均自动清理；档案只保存公共证书和固定结果。不复制参考项目源码，也不安装新依赖。

程序实际加载 CertStore／TLSConfig，但不调用 master.run，不启动服务器；TLS 使用 MemoryBIO。测试禁止 IPv4／IPv6 网络 socket、连接和 DNS；asyncio 的本地 Unix socketpair 只用于事件循环自唤醒。构造输入是证书与上下文，不是实际微信流量。

| 验证 | 方法 | 结果 |
| --- | --- | --- |
| 真实组件签发的 15 个场景 | 同一叶证书在无约束公共根对照和受约束根下分别实际握手，共 30 次 | 目标两种大小写接受；范围外与错主机拒绝；无约束对照成立 |
| 默认推导的证书 | 给 TLSConfig 提供构造的上游通配符证书、目标 SNI 和解析 IP，再握手两次 | 无约束对照接受，受约束根拒绝，说明默认额外 SAN 与当前边界冲突 |
| 固定目标证书 | 使用组件自己的 certs 配置，关闭上游证书信息推导，保持上游 TLS 校验；同一上下文选择并握手 | 选中预期指纹，只有目标 SAN；目标握手接受，错主机拒绝 |

合计 34 次实际离线 TLS 校验；没有调用 macOS 信任命令。过期和错误签名不在本次组件生成的 15 个场景中，沿用 C15 的独立控制证据，不声称这里重测了 17 项。

默认 SAN 风险来自真实组件对构造上下文的行为；没有采集当前微信的实际上游证书，不能据此断言它就是 C12 失败根因。固定证书在 OpenSSL 下可用，也不能推定微信内核会接受。

本机已安装的一手实现位置：

- [certs.py](/Users/chenge/project/liumo/.venv-capture/lib/python3.14/site-packages/mitmproxy/certs.py) 的 CertStore.from_store／from_files／get_cert／add_cert_file，版本 12.2.3。读取格式为 CA 私钥与公共根，固定目标证书使用独立叶私钥。生成缺失的默认 CA 属于组件行为，因此程序先检查材料存在并固定根字节，不接受 CA 回退。
- [tlsconfig.py](/Users/chenge/project/liumo/.venv-capture/lib/python3.14/site-packages/mitmproxy/addons/tlsconfig.py) 的 configure／get_cert，版本 12.2.3。会加入上游 CN／SAN、SNI、server.address；关闭 upstream_cert 后仍可能加入 server.address，因此仅改这个选项不足以保证目标 SAN 单一，需同时配置固定目标证书。
- [options.py](/Users/chenge/project/liumo/.venv-capture/lib/python3.14/site-packages/mitmproxy/options.py) 的 upstream_cert 选项只控制上游证书信息推导，独立于 ssl_insecure。实际实例核对 ssl_insecure 为 false。

访问日期与源码 SHA-256、公共样本及程序哈希见 [证据索引](/Users/chenge/project/liumo/evidence/feasibility/wechat-compat-preparation.json) 。这些是本机固定安装文件证据，不冒充远端最新 HEAD 核对。

## 收尾审阅结论

C15 的 70 秒只覆盖两条证书撤销命令与回读。加入代理后，现有控制器还需代理回读／恢复／再回读，以及停止进程和删除本次私钥；不能将 70 秒原样沿用。

现有旧采集控制器的 verify 将所有非零返回视为 false，不能直接用于新试验的撤销验收。新的运行入口须使用 C15 的固定数字分类：有效成功、明确不信任、未知／内部错误分开；公共根只作为链证书提供，不用显式根掩盖系统信任状态。现有采集入口未更改。

下一次提案的完整收尾等待预算如下，预算测试属于构造验证，没有真实运行这些步骤。

| 步骤 | 秒 |
| --- | --- |
| 关闭解密／观测并写状态 | 5 |
| 读取当前代理 | 5 |
| 只恢复本次仍占用的 HTTPS 代理 | 30 |
| 原值回读 | 5 |
| 撤销本次用户信任 | 30 |
| 按指纹删除本次证书与信任设置 | 30 |
| 证书不存在回读 | 5 |
| 带公共根链的有效目标不信任验证 | 5 |
| 停止进程并删除本次私钥文件 | 5 |
| 合计 | 120 |

已授权实验总窗口 180 秒，只给安装、控制与一次 UI 观察合计最多 60 秒，其余 120 秒预留收尾。双时钟取更紧的剩余时间，只有剩余量覆盖下一项操作和全部收尾预算才开始；认证、控制或界面耗时导致预算不足就提前恢复，不压缩收尾。该设计不承诺系统停滞、断电或收尾进程遭 SIGKILL 时仍能自动恢复。

## 真实实验的具体范围（已获本次独立授权）

用户“确认，去干吧”已授权以下具体范围，无需再次授权。系统运行／恢复入口已实现及自测，当前未越过只读预检门槛，不能写成实际信任、微信或收尾通过。

1. 固定独立目录 `.auth/wechat-capture/wechat-compat-session/`，不可重跑；前五次代理实验和 C15 均已恢复、停止，并取得相应生命周期锁。新基线只读取当前活跃服务配置，不扫描账号数据。
2. 新建受约束 CA 和固定目标叶证书。实际代理需要私钥：仅将新 CA 和叶私钥暂存在本次 0700 目录、文件 0600，目标固定证书与 CA 密钥分开；不复用 C15 公共测试根，不输出密钥，不写普通配置／日志／归档。进程停止后删除本次私钥文件；异常未收尾时保留明确恢复入口，不能宣称已删除。
3. 仅用户级 SSL 信任，不带旧 -s 策略字符串，不使用系统级或无约束根。安装前对照和约束门槛须成立，工具内部错误／未知结果直接停止。只修改当前活跃服务 HTTPS 代理，衔接原有本机上游；不改 HTTP、PAC、旁路或系统时区。
4. 总窗口 180 秒，预留 120 秒收尾。一次无凭证公开控制请求通过且代理侧计数成立后，Agent 在安全确认的猫笔刀固定样本文章窗口记录前后计数、正常刷新一次并观察证书错误与页面状态。刷新前需有足够剩余操作时间；目标不明或 Computer Use 不可用，不启动依赖界面的实验。
5. 只解密 `mp.weixin.qq.com:443`；其他域保持隧道转发，继续严格校验上游 TLS。只记录固定 HTTP／TLS 计数、时间和必要目标文章 UI 证据；不采集 Cookie／令牌、不保存原始 URL／头部／响应正文，不发列表／评论探针，不读缓存、内存、聊天或无关账号。访问受限或出现证书警告时停止，不绕过。
6. 到期、取消、异常或范围门槛失败，先关闭解密和观测，再按本次占用状态恢复原代理；不覆盖并行用户改动。分别验收代理原值回读、有效信任撤销、进程停止及私钥删除。恢复失败优先该次恢复，禁止开展下一实验。没有读取原页面或请求计数的真实证据，不标记微信兼容通过。

授权覆盖一次上述系统实验、必要目标文章 UI 观察和恢复，不覆盖凭证采集、正式订阅、常驻代理、后台安装或实际归档。用户仅在必要的普通终端启动／macOS 认证时介入；其余观察由 Agent 完成。

## 自测、验收与交付

已完成离线部分的测试覆盖：完整预算和双时钟边界、固定审阅 CLI 不执行系统动作、真实组件选择与 34 次 TLS、缺 CA 私钥不静默重建、错误私钥拒绝、未知结果不算通过、旧目录／符号链接／宽权限拒绝及成功／异常私钥清理。

新增 14 项测试及完整回归共 236 项：232 通过、4 跳过。安装前未知结果、部分安装、范围逃逸、控制失败、双时钟／真实父管道 EOF、日志失败仍恢复、外部代理保全、未知撤销结果拒绝成功、进程身份保护、变更／符号链接私钥保全和重复恢复无系统写入均有构造检查。实际 mitmproxy 配置及适配器事件已在禁止网络 socket 的测试中运行，证明未读取 Cookie／正文且日志失败会关闭观测；这仍不等于真实微信流量。实际系统限时恢复、网络控制及刷新待普通终端实验验收。

交付沿用原 Goal：可复现程序与必要测试、脱敏现场摘要及公共证书校验值、明确通过／失败／未验证项，更新本方案、Goal 和 Roadmap。即使微信兼容分项通过，发现来源、两号列表／分页／时间、评论／回复及原页单图仍分别待验。

## 离线准备交付记录（历史）

2026-10-18 15:28：C16 离线准备通过：已有 mitmproxy 12.2.3 实际加载受约束 CA 与独立目标叶证书，15 场景双根对照加选择检查共 34 次 MemoryBIO TLS 符合预期。构造上游通配符／解析 IP 时默认 SAN 推导被约束拒绝，固定目标证书后选择与握手通过；这不是当前微信失败根因证明。222 项回归为 218 通过、4 跳过，临时私钥已清理。未改系统、开监听或访问微信，C15 仍关闭。新实验提案为 180 秒／120 秒收尾预留与临时私钥文件，需按该具体范围单独确认；系统入口未实现，微信及原 Goal 未完成。[准备证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-compat-preparation.json) 。

## 本次运行入口交付

2026-10-18 15:51：C16 独立运行／恢复入口已实现，已获一次具体授权。236 项回归为 232 通过、4 跳过；新增 14 项含实际组件无网络回放和构造生命周期验证，不冒充系统实测。Agent 截图确认猫笔刀固定文章且聊天隐藏，尚未刷新；实际只读预检返回 preflight_system_authorization_unavailable，停止于证书生成、监听及系统变更前，固定一次目录未创建。下一步只需普通终端启动和必要 macOS 认证，Agent 负责取样与一次刷新；C15 不重跑。微信及原 Goal 未完成。[入口证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-compat-runner.json) 。

## 实际验收及边界

2026-10-18 16:08：C16 单次文章兼容与限时收尾通过。普通终端启动后，安装前对照／不信任及安装后 17 项范围检查成立；控制 HTTP 200、代理控制计数各 1。Agent 对猫笔刀固定文章正常刷新一次，页面可读且未见证书警告；文章请求／响应从 0 增至各 1，普通目标域从 0 增至各 20，TLS 失败计数均为 0。约 60.3 秒完成代理回读恢复、明确有效撤销、进程停止及两份私钥删除，180 秒窗口内收尾通过。未采凭证或发列表／评论探针，不证明旧错误的唯一根因、两号兼容或凭证功能；236 项基线哈希未变，未重复运行代码测试。C16 已关闭，不重跑；原 Goal 未完成。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/wechat-compat-live.json) 。

前取样时间为 2026-10-18T08:04:40.134705+00:00，刷新动作位于该时间与 08:05:01.784972 的后取样之间；finish 命令随后的取样覆盖同一后取样文件，最终文件时间以证据为准，计数相同。一次 ⌘R 已由 Computer Use 返回，通用 AX 树未变化；前后页面仍可读，点赞从 6992 变为 6998、收藏从 1092 变为 1093，文章网络计数同步增加。UI 证据仅在工具输出，未保存本机 PNG，不作为含评论整页截图。普通路径计数不保存具体 URL，因此不能把其余 19 次认定为评论接口或账号有效性。

C12 与本次在 CA 信任表达、固定叶选择及运行证书等条件上不同；本次说明当前组合可用，不能单独归因旧失败。C17 候选凭证采集已取得用户另行授权，当前独立入口已实现；[C17 具体提案](/Users/chenge/project/liumo/goals/20261017-1606-wechat-session-validation.md#c17固定文章凭证功能验证) 先复用当前一篇正常页面，采白名单候选并至多核对一次同文正文／评论，仍逐项验收，不重跑 C16。
