# 正常微信评论请求基线（C21／C22）

本轮解决的证据缺口是：正常微信成功加载留言时，实际请求条件与 C20 有哪些差异。C20 已取得并独立识别正文，但评论 HTTP 200／业务码 -3；旧候选请求次数已消耗，不继续猜测或重试。本次 C21 实验已结束并恢复：页面留言与回复可见，但未匹配到成功评论响应，未保存私有基线。

C22 的实现与构造回归已准备，C22 本次真实执行已结束并恢复，未取得成功评论基线；[准备证据](/Users/chenge/project/liumo/evidence/feasibility/comment-refresh-preparation.json) 与 [施工检查点](/Users/chenge/project/liumo/goals/20261017-1606-wechat-session-validation.md#c22明确刷新与固定匹配计数) 分开记录，未把准备当作成功评论基线。

施工清单见 [C21](/Users/chenge/project/liumo/goals/20261017-1606-wechat-session-validation.md#c21正常微信成功评论请求基线) ，准备证据见 [索引](/Users/chenge/project/liumo/evidence/feasibility/comment-baseline-preparation.json) 。沿用唯一 Goal，不新建或声称服务已恢复。

## 实验范围与成功标准

- 只对猫笔刀固定样本 `ihaxygZIbs2HwXMNiMaqEg` 的正常留言请求取一次基线。精确匹配 HTTPS mp.weixin.qq.com、GET、`/mp/appmsg_comment`、`action=getcomment` 和固定 biz／appmsgid／idx；未知 action、其他文章与账号不读取头部或响应正文。
- 用户另行明确授权后，复用已实测的受约束 CA／固定目标叶证书、临时用户级 SSL 信任及当前服务 HTTPS 代理，保留原本机上游。总计划窗口 180 秒，预留 120 秒收尾；控制请求仅一次、不带凭证。前八次系统实验必须已经恢复、停止，新目录不可重跑。
- Agent 先确认固定文章、聊天隐藏，再写近期 UI 就绪记录。控制通过、采集窗口仍有效后，只正常刷新一次并滚动至留言区；不发消息、留言或点赞。不要求用户抄写 token。遇到 UI 不可用或时间不够，停止当前实验。
- 最多处理第一条匹配响应。HTTP 非 200、业务非零、空列表、格式异常、截断或超限都停止，不自动尝试第二条，也不把空结果当作文章无留言。
- HTTP 200、整数 `base_resp.ret=0`、`elected_comment` 为非空对象列表，才写成功基线。这只证明该次原生请求成功，不证明全部评论／回复、自动接口、完整截图或追更成立。
- 匹配响应原字节转发，压缩与解压数据各限 1 MiB，仅在内存中解析；identity、gzip、deflate、已有 Brotli 1.2.0 有界 API 均有构造验证。flow 不保存正文，不落盘留言内容与昵称。其他响应直接流过。

## 私有字段与对照边界

新目录为 `/Users/chenge/project/liumo/.auth/wechat-capture/comment-baseline-session/` ，成功时排他创建一个 0600 `baseline.json`，不覆盖已有凭证：

| 字段 | 保存方式与用途 |
| --- | --- |
| query | 固定 18 项白名单的原编码与解码值；未知字段只计数量，不保存名称或值 |
| 请求头 | 仅 User-Agent、Accept、Accept-Language、X-Requested-With |
| Referer | 只保留固定文章的公开身份 URL、目标根 URL 或固定范围类别，去除鉴权参数 |
| Cookie | 此条固定请求的完整单个 Cookie 字段，仅用于本机离线比较；最多 16384 字符 |
| 响应 Cookie | 仅此条评论响应的 Set-Cookie 解析键值，不保留原始头；不是正文响应更新的观测 |
| 响应证据 | HTTP／业务数字状态、压缩／解压字节、留言条数与 UTC 捕获时间，不含留言内容 |

完整 Cookie 是本轮新增的敏感范围，真实写入需当次明确授权。不读取账号数据库、缓存、钥匙串会话或其他应用凭证；不保存原始 URL、全套头部、原始 Set-Cookie、原始流量或响应正文。

系统恢复分项通过后，离线读取新基线和原 C17 候选。只输出固定 query 与原四项 Cookie 的相同／变化／缺失类别、额外 Cookie 数量、选定头部对照及固定响应数字。C20 的 comment_id 没有保留，必须标记不可比较。原生令牌可能自然变化，字段差异不能单独证明 -3 的根因；基线也不触发接口重放。

## 可复现入口

只读方案无需授权，不读取真实凭证、不联网或修改系统：

```bash
cd /Users/chenge/project/liumo
.venv/bin/python -m validation comment-baseline-plan
.venv/bin/python -m unittest discover -s tests -p test_comment_baseline.py -v
.venv/bin/python -m unittest discover -s tests -v
```

实际会话入口下列命令仅在本次具体范围获准、目标 UI 已确认后使用。Agent 环境此前网络／系统前置检查受限，普通终端负责启动和必要 macOS 认证；不得借终端 UI 绕过当前执行权限。以下仅保留会话入口说明；C21 目录已经关闭，不得再执行 session／observe／finish。新的系统实验必须先明确独立目录、范围和授权：

```bash
.venv-capture/bin/python -m validation comment-baseline-session
```

会话需要 0600 私有授权记录 `/Users/chenge/project/liumo/.auth/wechat-capture/comment-baseline-authorization.json` ，绑定 C20 结果 SHA-256、授权 UTC 时间、`experiment=c21_comment_baseline`、`source=explicit_user_grant`、一次响应、两项 1048576 字节限制、完整单个 Cookie 明确授权、180 秒／120 秒预留。授权前不创建记录。近期就绪记录为 `/Users/chenge/project/liumo/.tmp/wechat-session-validation/comment-ui-ready.json` ，固定 `target=maobidao_fixed_article` 与 Unix 时间，最多 300 秒有效；只在确认目标页面后由 Agent 写入。

下列取样只有控制通过、窗口有效且采集仍开放时才可执行，不等于 UI 刷新成功：

```bash
.venv-capture/bin/python -m validation comment-baseline-observe --phase before_refresh
.venv-capture/bin/python -m validation comment-baseline-observe --phase after_refresh
```

成功或失败响应已关闭采集后，after_refresh 取样可能被拒绝。此时直接请求收尾；该命令不会伪造刷新证据，也不要求采集继续开放：

```bash
.venv-capture/bin/python -m validation comment-baseline-finish
```

收尾必须分别核对代理回读、有效撤销、进程停止和私钥清理。C17 自动撤销曾两次超时，后续独立恢复才通过；本次不承诺自动收尾必然成功或一定在窗口内完成。恢复失败只使用本次专用入口，不重新启动、重装或重采：

```bash
.venv-capture/bin/python -m validation comment-baseline-recover
```

只有成功基线与全部恢复门槛都通过后，才能执行离线比较；不发网络请求：

```bash
.venv-capture/bin/python -m validation comment-baseline-compare
```

比较输出到忽略的 `archives/feasibility/`，公开 evidence 仅收录脱敏摘要与校验值。没有成功基线则保留固定失败证据，真实验收未通过，不继续尝试第二次。

## 依据与验证等级

- 请求参考沿用已缓存、校验的 exporter 固定提交 `152f23832c7f3664b86148e84bd3f75e513e4dd2`，不是对当前上游版本的判断。[既有字段审计](/Users/chenge/project/liumo/evidence/feasibility/article-cookie-body-live.json) 保留来源链接和哈希；未复制上游运行代码。
- 本机 mitmproxy 12.2.3 源码 `/Users/chenge/project/liumo/.venv-capture/lib/python3.14/site-packages/mitmproxy/proxy/layers/http/__init__.py` 的 443 至 475 行说明流回调逐块接收、EOF 收到空字节，并仅在 store_streamed_bodies 开启时保留流正文；程序固定关闭该选项。实际已有组件的无监听回放验证了原字节转发、成功后关闭观察、flow 不保留正文。
- 已有 Brotli 1.2.0 的本机 API 支持 `process(..., output_buffer_limit=...)`；实际组件构造测试覆盖正常响应和超过解压上限的数据。以上不是微信实测。
- 默认完整回归中的浏览器／回环跳过不算通过。完整日志、代码与组件来源哈希、旧回执保全以及真实未执行范围见准备索引。

验收后仍需另行处理：依据差异作有限请求验证、两号多篇发现与分页、评论回复覆盖、原页单张完整截图、自动续期和设备休眠唤醒。这些不能由本次基线代替。

## 当前执行状态

2026-10-18 20:12：C21 已结束，约 60.8 秒完成代理恢复、有效撤销、进程停止与两份私钥清理，180 秒内收尾通过；公共材料身份与私钥不存在已核对。控制 HTTP 200／计数各 1，Agent 发送一次刷新快捷键并滚动两次，留言及作者回复实际可见；但文章 HTTP 各 0、普通目标各 2，匹配评论响应 0，未保存 Cookie 或基线，未执行离线凭证比较。刷新是否真正重载未独立确认，不能据此判断缓存、接口路径或 -3 根因。C21 目录已消耗，不再运行；282 项基线代码未变，未重复测试。原 Goal 服务仍 blocked、未完成。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/comment-baseline-live.json) 。

已核对此前 C16 使用同一 super+r 快捷键后有文章请求增量；这次没有，不能把差异直接归因于缓存、路由或客户端限制。采集期间未读取两条普通目标请求的原始路径，不能事后补证。恢复后仅尝试查看刷新菜单，坐标点击返回 AXError.notImplemented，截图未见菜单，不算菜单刷新已验证；未再次刷新。

C21 CLI 固定原因输出的缺陷已先失败复现再修正，282 项回归为 278 通过、4 跳过；旧终端 ProbeError 的具体原因仍无法恢复。真实运行后代码哈希未变，未重复测试。系统生命周期分项通过不等于正常评论基线、自动接口或整页归档通过。

## C22：明确刷新与固定匹配计数

当前无系统改动的 UI 检查确认：微信主应用原生「查看」菜单可通过 AX 打开，但只提供全屏和缩放，没有文章刷新项；菜单检查后已取消。文章自己的菜单没有进入 AX 树，既有坐标点击返回未实现。这个事实解释了为什么下一次不能依赖 Agent 的快捷键返回值；它仍不能证明 C21 的按键没有执行或网络为何没有文章增量。

C22 沿用 C21 的同文、GET、成功业务、一次响应、压缩／解压各 1 MiB、完整单个 Cookie 仅成功时 0600 保存等边界，不主动重放。只增加两个变化：

1. 控制通过时，终端明确提示用户点击固定文章标题右侧的圆形刷新箭头一次。Agent 负责监测、查看文章和滚动到留言区。用户反馈、实际请求增量和成功评论响应分别验收；不以其中任一项代替其他项。
2. 对固定目标域已知评论路径增加固定类别计数，区分没有观察到该路径和公开匹配条件未满足。分类只读 action、__biz、appmsgid、idx、comment_id 五项公开 query 值；其余参数值、无关 Cookie／头部／正文不读取，不记录任意字段名或路径。

固定类别为非 GET、无效 query、重复公开参数、非 getcomment、缺失／其他公众号、缺失／其他文章、缺失／其他 idx、无效 comment_id、公开身份形状匹配。每类分别计请求与响应次数。最后一类仅证明五项公开形状吻合，完整凭证字段、重复 token 等校验仍可能拒绝采集；分类不会放宽原有 matcher。

公开身份形状不符时，到固定计数即停止，不进入私有参数解析器。公开形状通过后才校验基线的既定 query 白名单；未知 query 值在分类和基线解析中都不解码，只有其字段数量进入摘要。

新目录 `/Users/chenge/project/liumo/.auth/wechat-capture/comment-refresh-session/` 独立且不可重跑，前九次必须关闭。新授权文件 `/Users/chenge/project/liumo/.auth/wechat-capture/comment-refresh-authorization.json` 绑定已恢复的 C21 state.json 哈希和恢复完成时间，不复用 C21 授权；还需明确 manual_menu_refresh_once 与 fixed_comment_match_counters。授权前不创建该文件、C22 目录或 UI 就绪记录。

仅有以下审阅和测试命令现在可以执行，不读取凭证或修改系统：

```bash
.venv/bin/python -m validation comment-refresh-plan
.venv/bin/python -m unittest discover -s tests -p 'test_comment*.py' -v
```

C22 目录已关闭；以下为已执行机制说明，session／observe／finish 不再运行。实际启动原要求 C22 获准、Agent 最近截图确认固定文章及聊天隐藏，由普通终端执行。就绪文件固定为 `/Users/chenge/project/liumo/.tmp/wechat-session-validation/comment-refresh-ui-ready.json` ，仍只允许 300 秒，不自行改时间或放宽门槛。系统预算继续 180 秒／120 秒收尾预留，信任／代理／上游保持原边界。控制通过前不要刷新；出现 ready_user_refresh_maobidao_comments 提示后，点击文章标题右侧的圆形刷新箭头一次，保持文章前置并回复「已刷新」，不要等待终端结束才反馈。

```bash
.venv-capture/bin/python -m validation comment-refresh-session
```

Agent 在有效窗口内取样或请求收尾；响应已关闭时直接 finish，不制造刷新后取样。系统收尾仍分项验收，失败只执行本次 recover，不启动第二次：

```bash
.venv-capture/bin/python -m validation comment-refresh-observe --phase before_refresh
.venv-capture/bin/python -m validation comment-refresh-observe --phase after_refresh
.venv-capture/bin/python -m validation comment-refresh-finish
.venv-capture/bin/python -m validation comment-refresh-recover
```

若成功基线存在且全部恢复通过，才离线比较，不发 API：

```bash
.venv-capture/bin/python -m validation comment-refresh-compare
```

无匹配、明确刷新仍不产生可观测请求、范围不合或业务失败时，只交付固定计数与失败阶段。不得补读其他流量、读取缓存或扩大证书／代理范围，也不据此认定平台永久不可用。C17 曾自动撤销超时，本次保留独立恢复，不承诺一定自动完成。

### C22 当前授权状态

2026-10-18 22:43：C22 本次授权已收到，0600 记录绑定已恢复 C21 的回执并通过门槛；旧九次恢复及原回执保全。刷新控件已按用户截图明确为文章标题右侧的圆形箭头，不需要打开菜单；终端提示已同步，291 项回归为 287 通过、4 跳过。Agent 已截图确认固定文章且聊天隐藏，下一步由普通终端启动，控制通过后用户点击箭头一次；实验尚未启动，未改系统或采集凭证，不需要再授权。原 Goal 服务仍 blocked、未完成。[现场记录](/Users/chenge/project/liumo/evidence/feasibility/comment-refresh-live.json) 。

### C22 实际结果

2026-10-18 22:49：C22 已结束，81.991 秒完成代理恢复、有效撤销、进程停止及私钥清理，180 秒内收尾通过。控制 HTTP 200／计数各 1；用户明确点击圆形箭头刷新，文章类 HTTP 各 1、普通目标各 20，页面点赞／收藏从 7010／1095 更新为 7058／1107，留言及作者回复可见。已知评论路径的 24 项分类计数全为 0，未读评论响应或保存 Cookie／基线，未执行离线比较。before_refresh 命名取样已含文章响应，不能当作用户动作前基线；依据总计、用户反馈与界面变化记录刷新证据。C22 已关闭不重跑，原因仍未定；55 份代码与 291 项基线一致，未重复测试。原 Goal 服务 blocked、未完成。[真实证据](/Users/chenge/project/liumo/evidence/feasibility/comment-refresh-live.json) 。

固定端点未观测到与筛选失败分开：24 项分类计数均为 0，没有证据表明是 idx、action、方法或账号不符。普通目标另有 19 条路径类响应，但本轮不保存任意路径或正文，不能事后追补。不同端点、内嵌数据、原生桥接或缓存都只是未验证假设。

定向 GitHub 调研暂未找到可支撑当前 Mac 新评论路线的一手资料；搜索结果中的[维护者停维护说明](https://github.com/wechat-article/wechat-article-exporter/issues/200) 针对项目与微信读书上游，不足以解释本机留言流量。访问日期为 2026-10-18 22:49（北京时间）；固定源码页面在网页工具返回缓存未命中，不据此判定源码失效。后续先核对静态材料，材料不足再提出最小独立取证范围，不重跑本次。
