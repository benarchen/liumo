# V1 发现来源最小程序

状态：准备代码和离线回归已完成，已执行小规模真实列表核对，来源关口未通过。运行代码自行编写，没有复制上游源码；仅使用项目隔离的微信读书会话，没有读取本机微信或普通 Chrome 凭证、枚举书架或请求评论。本阶段沿用 [V1 施工清单](/Users/chenge/project/liumo/goal/20261019-2121-v1-auto-follow.md) 。

## 请求设计及证据边界

| 字段 | 本地实现 | 参考与待验范围 |
| --- | --- | --- |
| 目标 | 猫笔刀：`MP_WXS_3198966508`；stormzhang：`MP_WXS_3085404720` | 从项目 `capture.py` 已有公开样本 `__biz` 常量做 Base64 解码；不是当前账号服务端身份通过。 |
| 列表请求 | GET `https://weread.qq.com/web/mp/articles`，query 为 `bookId`、`offset` | 对齐固定参考的组数候选，不发送 `count` 或添加书架。 |
| 头部 | `Accept: application/json, text/plain, */*`；`Accept-Language: zh-CN,zh;q=0.9,en;q=0.8`；`User-Agent` 为项目浏览器自身值；`Origin` 为微信读书源站，`Referer` 为首页 | 没有伪装为微信客户端，没有导出 Cookie。实际登录是否足够仍待正常请求。 |
| 认证 | 仅项目 `.auth/weread/` 的隔离浏览器会话，按站点 Cookie 规则向同源发送 | 本次已经正常访问专用站点并观察到会话更新；更新不等于认证通过，Cookie 不转给文章原站、图片域或第三方。 |
| 分页 | 从 0 开始，按顶层组数前进；最多 3 页、页间 2 秒 | 参考 [we-mp-rss 固定源码](https://github.com/rachelos/we-mp-rss/blob/d94db01372105bc479db81a0ac91829dac7f43e4/core/wx/model/weread_mp.py#L433) 。另一 [weread-mp 实现](https://github.com/steptian/weread-mp/blob/2bde705a8346844fab6c4ec53b43708497881594/weread_mp.py#L181) 使用时间游标，不自动混用；两者均不是微信官方契约。两份固定版本已在本次路线评审中读取，访问日期为 2026-10-19。 |
| 传输 | TLS 默认校验、不跟随重定向、请求最长 30 秒 | 列表响应返回后超过 2 MiB 不接受；这不是网络下载或总内存硬限制。没有取得本机真实传输证据。 |
| 文章身份 | 保留 `reviewId` 与可选 `originalId`，不由来源 token 拼微信短链 | `url=null`、`url_verified=false`；内容接口的同文响应及公开原链接解析尚未实现，不会调用旧评论程序替代。 |
| 时间与覆盖 | 列表时间只作候选；观察结束信号与覆盖通过分开 | 即便空页或 `clearAll=1`，身份、原链接、发布时间与窗口覆盖尚未核实，`coverage_complete` 仍为 false，命令不会返回整体验收成功。 |

空组／畸形字段、重复文章／重复页、非法终止标记和业务拒绝均停止本次扫描；前面有效页保留。业务错误只记录有限数字码和固定原因，不记录上游错误原文；不根据 `-2012`／`-2041` 唯一判断登录过期或自动重试。到页预算上限明确记录未覆盖，不能当成无更新。

## 已可复现的入口

在 `/Users/chenge/project/liumo` 运行：

```bash
.venv/bin/python -m validation weread-plan
.venv/bin/python -m unittest discover -s tests -p 'test_weread_discovery.py' -v
.venv/bin/python -m unittest discover -s tests -v
```

首条命令只输出请求设计和公开候选，不读 `.auth/`、不启动浏览器、不访问网络。专项回归覆盖不透明 ID、跨页失败保留、重复页、页预算、末页不冒充覆盖、畸形字段与诊断去敏；全部为构造／mock 证据。

首次准备回归为 368 项：364 通过、4 跳过，保留 [原准备证据](/Users/chenge/project/liumo/evidence/feasibility/weread-discovery-preparation.json) 。加入自动会话观察后，完整回归为 372 项：368 通过、4 跳过；新增 4 项覆盖必要 Cookie 比较、更新、超时、窗口关闭和站点限制。3 项完整浏览器归档集成未显式开启、1 项回环测试因普通沙盒权限拒绝跳过。另一次经批准的真实本地浏览器渲染通过，不能替代这 4 项或来源验收。

## 真实结果与止损

切换模式后，标准授权执行路径的 HTTPS 和无账号隔离浏览器通过。两号列表各核对一次，均 HTTP 200／业务码 -2012，无列表；随后仅正常打开项目专用微信读书站点，程序观察到必要会话 Cookie 更新并自动结束，没有要求用户终端 Enter，也未据此声称扫码或认证成功。猫笔刀更新后的一次列表核对为 HTTP 200／-2041，仍无文章；随即停止，未继续 stormzhang 后续请求或切换账号／传输绕过。

当前有 3 次列表 HTTP 观测、0 篇文章，尚无真实分页／时间／覆盖通过项；这些码不能证明永久关闭或唯一拒绝原因。本轮不再反复刷新、扫码、切 UA 或重放。[真实证据与代码基线](/Users/chenge/project/liumo/evidence/feasibility/v1-source-live.json) 、[权限结果](/Users/chenge/project/liumo/docs/execution-permissions.md) 。

## 一个备选的实际核对

2026-10-19 访问 [Wechat2RSS 官方免费列表](https://wechat2rss.xlab.app/list/all) 找到猫笔刀，未找到 stormzhang。对列表直接给出的猫笔刀公开 RSS 作一次无凭证 GET，HTTP 200／TLS 通过，返回 176879 字节 XML、20 条不同公开原链接，包含既有技术样本。仅证明这个源本次确实返回多篇，不证明时效、长期覆盖或原文发布时间；RSS 时间保持未验证。未借用微信读书凭证，未启用订阅或归档这 20 篇历史文章。

官方 [Q&A](https://wechat2rss.xlab.app/deploy/qa) 还明确其采集范围为群发消息、只抓最新 20 篇，更新时延可在 0～24 小时波动；[私有部署价格](https://wechat2rss.xlab.app/deploy/) 为 150 元／年软件授权，需要自行部署，也仍可能受限。因此它不是已经验证的两号全量替代，也不能直接建议购买后便满足现有要求。[备选证据](/Users/chenge/project/liumo/evidence/feasibility/v1-source-live.json) 。

## 正常网页核对：2026-10-19 22:22

按用户指定，在项目 `.auth/weread/` 专用 Chrome 窗口正常访问 [微信读书首页](https://weread.qq.com/) ，分别输入两个号并点击搜索图标。猫笔刀显示「电子书」及「全文中提到 猫笔刀 的书 · 1210」；stormzhang 显示「全文中提到 stormzhang 的书 · 2」。这些数字是搜索界面的书籍命中提示，不是公众号文章数；两次均没有进入目标号文章列表。页面中包含 `MP_WXS` 的链接计数均为 0，此选择器检查也不等价于证明全部入口不存在。

本次正常页面搜索可以使用，但没有取得两号多篇文章、原文身份、发布时间或真实翻页证据。未看到需要用户处理的验证码或登录提示，也未独立验证登录状态；不能据此证明微信读书 App 同样不可访问、网站永久取消公众号能力或前述接口错误的原因。本轮未手工重放 API、改 UA、添加书架／关注、读取其他应用会话或开展系统实验；专用窗口已正常关闭。

[脱敏证据](/Users/chenge/project/liumo/evidence/feasibility/weread-normal-pages.json) 记录 DOM 摘要与本机裁剪截图索引；截图只保留 stormzhang 搜索结果提示。猫笔刀为当时 DOM 记录，无截图，不为补图再次搜索。复现只需正常访问首页、逐个输入目标名称并点击输入框右侧搜索图标；无需执行终端命令、复制 Cookie 或 Enter 确认登录。网页会变化，本次结果不承诺未来一致。

## 当前待决事项

两号发现关口未通过，不进入正式运行包或单篇批量归档。用户选择的正常网页核对已执行，但未找到目标文章列表；不再把首页重复搜索或盲目扫码作为下一轮实验。如果已有来自正常微信读书 App 的目标号分享入口，可以据其核对平台差异；没有此类新证据时，建议停止投入当前微信读书候选，转向评估能覆盖两号的其他发现来源。接受公开 RSS 的账号／群发范围限制仍属于产品取舍，不能自动采用。付费、部署、联系第三方或公开申请新增源均未授权，不执行。

原 Goal 服务仍显示 blocked，工具未提供恢复状态接口；继续保留同一清单与未完成记录，不创建第二个或标记完成。
