# exporter 实现机制与留墨可借鉴路线

研究日期：2026-10-17（北京时间）。只读获取公开源码，不安装、不执行上游代码，不访问真实微信接口，不读取本机会话或安装证书／代理。exporter 固定版本为 `2.3.21`、提交 `152f23832c7f3664b86148e84bd3f75e513e4dd2`；wxdown-service 固定为 `v0.27.1`、提交 `28feff2095359acb158f856c40b357e77b686d2c`。文件、源码位置与校验索引见 [证据](/Users/chenge/project/liumo/evidence/feasibility/exporter-mechanism.json) 。本文属于源码结论与建议，不是接口实测通过。

## 结论

留墨每天只追更两个号，可以去掉全历史扫描、批量选择界面、浏览器数据库、公共代理池和多数导出格式，保留小规模串行处理。请求量与代码规模会降低，但自动发现的覆盖范围、评论凭证续期和原页完整截图仍是独立条件。离线后可能累积多篇，仍不能只看最新一篇。

最值得借鉴的是「发现、HTML 下载、评论快照、导出」分离，以及正文结构解析、留言游标、回复补取。建议沿用留墨现有 Python 验证包与浏览器组件，只借鉴必要逻辑，不为此引入 Nuxt、Vue、Cloudflare 服务或整套 exporter。微信读书不是这条正文／评论技术路线的必需依赖。

exporter 固定版本的 `LICENSE` 为 MIT；若后续复制代码，应保留相应版权和许可声明。本轮仅阅读，没有将上游代码接入留墨运行链。

## 代码实际如何工作

| 环节 | 固定源码位置 | 已确认的实现 | 留墨借鉴判断 |
| --- | --- | --- | --- |
| 主发现通道 | `apis/index.ts`、`server/api/web/mp/appmsgpublish.get.ts` | 公众号后台 Cookie／token，按 fakeid、begin、count 请求列表，展开每次发布中的多篇文章 | 借鉴分页与多图文展开；上游当前可用性未通过，不能作为已选来源 |
| Credential 备用列表 | `profile_ext_getmsg.get.ts`、`CredentialsDialog.vue` | 对 `/mp/profile_ext?action=getmsg` 发送 biz、offset、count 和会话参数；UI 的 pullData 仅取数据后 console.log，未接入完整归档闭环 | 小规模追更的候选之一；代码仍是未完成的集成，不应当成现成自动订阅 |
| 正文获取 | `BaseDownloader.ts`、`Downloader.ts` | 经代理用 HTTP fetch 取 HTML，校验页面结构，缓存原始 HTML 和 commentID；普通非付费正文路径不主动附加阅读凭证 | 可借鉴 HTTP 优先、原始 HTML 与元信息留存；留墨本机后端可以研究直接请求腾讯，取消前端跨域代理依赖，但实际可用性仍待验证 |
| 正文解析 | `shared/utils/html.ts`、`renderer.ts`、`markdown.ts` | 提取文章脚本中的 cgiDataNew，区分图文／图片／文字类型，处理 data-src，转换 Markdown | 借鉴结构与类型分支；遇到解析失败应显式失败，不能凭一个容器存在就认定完整 |
| 留言与回复 | `Downloader.ts`、`utils/comment.ts` | 主下载器分页取 elected_comment，按回复总数补取回复，分别缓存；导出时重新渲染为 HTML | 借鉴获取协议与快照分层，需补齐完整性核对；重新渲染不能替代原页截图 |
| 资源与 PDF | `Exporter.ts`、`pdf/generate.post.ts` | HTML／PDF 路径提取图片、CSS、背景资源，重写路径；Puppeteer 渲染加工后的 HTML，以内容高度输出 PDF | 借鉴离线资源清单；PDF 不等于原页 PNG，不能直接通过截图验收 |

主发现通道作者已于 2026-07-30 [宣布停止维护](https://github.com/wechat-article/wechat-article-exporter/issues/200) ，归因于核心上游关闭，亦说明 Credential 通道未真正接入主流程。这里的备用 UI 代码与公告相符；它不证明备用接口当前能工作，也不能据此认定正文、评论等所有接口均已关闭。

## 评论机制：上一轮简化接口以外的主路径

上一轮只读到 `server/api/web/misc/comment.get.ts` 的简化调用，本轮找到实际批量下载使用的 [Downloader.ts](https://github.com/wechat-article/wechat-article-exporter/blob/152f23832c7f3664b86148e84bd3f75e513e4dd2/utils/download/Downloader.ts#L339) 。二者不是同一条调用链，实施前应以前者之外的主下载器为重点：

- 从已下载 HTML 提取 commentID，并使用文章的 appmsgid、itemidx 和目标号 biz。
- `action=getcomment` 每页请求 `limit=100`；按响应 `buffer`、`continue_flag` 继续，不是只取第一页。主下载器附带 `uin`、`key`、`pass_ticket`、`appmsg_token`，设置微信 UA／Referer，有 Cookie 时同时携带。源码常量和字段是否仍必需或有效，未做当前接口验证。
- 对 `reply_total_cnt` 与内嵌 `reply_list.length` 不一致的留言，调用 `action=getcommentreply`，携带 content_id、max_reply_id，单次 `limit=100`。已读代码没有对每条留言继续循环补取回复，也没有把补取结果与原内嵌回复按稳定标识合并后核对数量；不能据此保证所有回复完整。是否确实丢失取决于接口返回语义，尚未实测。
- 只处理 elected_comment；协议类型还包含 friend_comment、my_comment。不能把当前导出范围直接等同于正常微信窗口所有可见区域。
- 评论数组和每条回复写入不同缓存。留言渲染优先使用独立回复缓存，否则用内嵌回复；最终输出是作者编写的模板，不是微信原页 DOM。

留墨若借鉴，应增加分页进展与终止条件、回复标识合并和计数核对，区分无评论／不可访问／加载失败／范围未完成，保留已取得的部分结果及时间。现有用户要求是首次可访问、可加载快照，不要求长期追踪或把留言转成 Markdown；不能把接口范围更大作为扩大采集的理由。

## 凭证怎样产生、保存与传递

源码链路为：微信内正常打开文章 → 本机 mitmproxy 观察符合条件的文章响应 → `resources/data/credentials.json` → 本机 WSS → exporter 页面 localStorage → 配置的下载代理 → 微信。

[wxdown-service 的 credential.py](https://github.com/wechat-article/wxdown-service/blob/28feff2095359acb158f856c40b357e77b686d2c/resources/credential.py#L43) 记录带参数的文章 URL、Set-Cookie、biz 与捕获时间；[watcher.py](https://github.com/wechat-article/wxdown-service/blob/28feff2095359acb158f856c40b357e77b686d2c/watcher.py#L66) 从本机文件向连接的客户端推送。前端再解析参数和 Cookie。`config/index.ts` 的 25 分钟是前端有效性判定常量，helper 的 30 分钟是推送过滤窗口，均不是留墨实测的服务端有效期。

本轮读取的 helper 与前端文件没有提供不打开微信文章就能定期刷新这些凭证的完整自动流程。保持代理进程运行，只能继续观察新请求；不能从源码推出它会主动获取每天可用的新凭证。因此，每日少量下载虽省请求，但持续追更仍需要解决凭证从何而来和何时失效。

不能原样采用的具体做法：

- [BaseDownloader](https://github.com/wechat-article/wechat-article-exporter/blob/152f23832c7f3664b86148e84bd3f75e513e4dd2/utils/download/BaseDownloader.ts#L34) 在未配置私有代理时默认使用公共代理；评论请求把带凭证目标 URL、Cookie 请求头编码进代理请求的查询参数。URL 编码不提供凭证保密，代理运营者会收到这些内容。留墨应优先研究本机直接请求腾讯，不使用其公共代理池。
- helper 会将完整凭证写入普通 JSON，插件还打印解析后的 URL；前端在 localStorage 中保存凭证，后台代理登录分支还有 token 日志。留墨不复制这些存储与日志策略；任何未来凭证实现都应受 `.auth/` 隔离和不输出敏感信息的约束。
- 安装 CA 和修改系统代理超出本 Goal 授权，现阶段未实施。是否需要扩大这部分范围，应等技术证据与替代路径明确后单独决定，不能因为有源码就默认执行。

## 两项会影响产物验收的差异

**Markdown 不等于已离线配图。** [startExport 与 exportMarkdownFiles](https://github.com/wechat-article/wechat-article-exporter/blob/152f23832c7f3664b86148e84bd3f75e513e4dd2/utils/download/Exporter.ts#L62) 显示：Markdown 路径只将重建正文转为文本，未执行 HTML／PDF 路径中的资源下载与本地路径替换。不能仅凭其支持 Markdown 就承诺本地配图；留墨需独立资源清单及相对引用核对。

**导出内容不等于原页截图。** `normalizeHtml` 清理 DOM、调整样式；`renderComments` 重建留言；PDF 接口对提供的 HTML 使用 `setContent` 和 `page.pdf`。已读链路不是打开原始微信页面并完成留言展开后做 PNG 截图。广告等附属区域还可能被清理。其浏览器可以隐藏运行，说明不必长期显示 Chrome 窗口，但不能解决原页评论加载条件，也不能证明超长 PNG 单图可靠。

另外，cgiDataNew 是通过执行文章脚本取得的：客户端使用 iframe，服务端使用带时间限制的 QuickJS 沙箱。本轮仅阅读代码，未执行任何文章脚本。留墨优先沿用既有受控解析／浏览器能力，不复制任意 eval 或无隔离 iframe，也不为这次研究新增脚本运行依赖。

## 建议的轻量路线与下一步顺序

建议保留留墨现有「来源发现 → 独立待归档队列 → HTTP 正文与本地配图 → 评论快照 → 原页截图 → 分项状态」结构。借鉴 exporter 的字段与步骤，不移植其前端产品和代理系统。

1. **先确定两项必要条件。** Credential 列表是否能覆盖最新多篇及离线空档；评论凭证是否存在可接受的持续取得路径。二者都是现有源码可继续核对的候选，尚未选定，也未实际通过。
2. **正文层优先直接 HTTP。** 按已读普通文章路径设计最小请求与校验，失败明确记录，不以换 UA、增加重试或代理切换代替访问条件核对。图片保持独立下载与离线核验。
3. **评论层保留分页与回复补取，重写状态判断。** 不直接复用上游的 completed、缓存覆盖、重试和凭证日志行为。受限即停，部分结果不丢，首次快照不持续更新。
4. **截图维持原验收。** 仍需正常可访问评论的原页渲染路径；HTTP 数据重建页是备选产物，若需替代原页截图须由用户决定。当前不引入替代、不降低要求。

研究阶段至此可确定的是借鉴范围与验证重点；真实自动发现、评论获取、回复覆盖、单张原页截图及凭证持续性均保持未通过。没有修改验证代码、重跑浏览器、安装候选项目或要求用户重新登录。
