# 微信公众号链接立即归档

`save URL` 接收任意公众号的公开 HTTPS 文章短链或长链，不需要先订阅，也不等待 RSS 收录。它通过项目专用的正常 Chrome 页面读取可见图文正文，保存 Markdown、本地配图和元数据。自动追更仍是猫笔刀单号 RSS，两种入口和去重账本分别维护。

## 使用

在 `/Users/chenge/project/liumo` 运行：

```bash
.venv/bin/python -m liumo save 'https://mp.weixin.qq.com/s/aZD7YZl0Fjsjsa7MHVyMoA'
```

整个 URL 使用引号包住，尤其是包含 `&` 的长链。仅接受 `https://mp.weixin.qq.com/s/公开标识` 或带 `__biz`、`mid`、`idx`、`sn` 的 `/s` 长链；分享追踪参数和片段会去除。其他网站、登录地址、含凭证参数的链接会在访问前拒绝。文章日期不受 RSS 启用时间限制，单篇手动保存不意味着启动历史批量导入。

命令输出 JSON，`output` 是本次保存目录；退出码 `0` 表示正文快照齐全或已核对复用，`2` 表示失败、受限或部分完成。首次读取显示一个独立 Chrome 窗口，读取结束自动关闭。不启动后台任务，也不发送归档通知。

```bash
# 同一链接再次执行：文件及图片哈希齐全时直接复用，不请求页面。
.venv/bin/python -m liumo save 'https://mp.weixin.qq.com/s/aZD7YZl0Fjsjsa7MHVyMoA'

# 主动重新读取，保留新目录；已有快照不会被覆盖。
.venv/bin/python -m liumo save 'https://mp.weixin.qq.com/s/aZD7YZl0Fjsjsa7MHVyMoA' --refresh

# 不显示窗口；页面未就绪或需要验证时返回失败原因。
.venv/bin/python -m liumo save 'https://mp.weixin.qq.com/s/aZD7YZl0Fjsjsa7MHVyMoA' --headless
```

`--wait-seconds 0..300` 控制有界面时等待正文或正常人工验证的时间，默认 `180` 秒。单次导航超时为 30 秒，随后正文滚动、图片下载另有有限预算；等待参数不是整个任务的总时限。没有自动轮换身份、反复刷新或无限重试。失败／部分完成后，排除原因再执行原命令即可创建新尝试；正常完成的快照需要 `--refresh` 才会重新读取。

## 会话与访问边界

专用浏览器会话在 [.auth/manual-article/](/Users/chenge/project/liumo/.auth/manual-article) ，不读取微信客户端、微信读书或日常浏览器会话。首次可能需要操作系统允许 Chrome 启动。若微信页面显示验证，用户只在该专用窗口正常完成验证；程序不操作验证码。如果页面要求登录，登录对象是微信文章页面，凭证保留在本机专用浏览器目录，不会写入 Markdown、普通日志或公开证据。

页面请求限于 `mp.weixin.qq.com` 及受限的腾讯静态／验证 CDN；阻止已知评论、回复和互动补充接口及站外顶层导航。没有调用评论接口的代码，也不保存评论；不承诺页面内部所有未来端点都能仅凭名称识别。配图单独按原文公开地址下载，只接受已限定的腾讯 HTTPS 图片主机，不携带浏览器 Cookie。不会关闭 TLS 校验、改系统代理或安装证书。

## 数据与状态

- [archives/manual/](/Users/chenge/project/liumo/archives/manual) ：`<请求链接哈希>/<UTC 时间-随机标识>/` 内保存 `article.md`、`images/` 和 `metadata.json`；失败也保留对应元数据。
- [state/manual/](/Users/chenge/project/liumo/state/manual) ：独立互斥锁和原子更新的 `index.json`，按公众号 `biz`、文章 `mid`、序号 `idx` 去重，短长链可归并到同一文章。
- [.auth/manual-article/](/Users/chenge/project/liumo/.auth/manual-article) ：仅此入口的 Chrome 会话。以上目录均被 Git 忽略，不属于源码备份。

元数据标记 `archive_kind=manual_page_snapshot`。`complete` 只表示当次可见正文、保留的正文配图和元数据齐全；`comments_status=not_requested`，`screenshot.status=deferred`。它与 `rss_snapshot` 的来源不同，不是包含评论的原站完整归档。

正文身份来自页面公开字段，长链中的预期身份还需与实际页面核对。原文时间只有页面 epoch 与渲染日期／分钟相符时才标记已核实；否则 `published_at=null`、`publication_time_verified=false`。每次保留保存时间、图片和 Markdown 的 SHA-256。

`partial` 表示至少存在图片失败或页面滚动未到底等未完成项，`reasons` 说明原因；付费、删除、身份冲突、验证等待结束等返回 `blocked`，不保存冒充完整文章的内容。意外异常使用固定错误类别，不打印浏览器异常原文中的 URL 或会话信息。缓存文件损坏会重新创建尝试，旧文件仍保留；刷新后的正文变化通过 `previous_output`、`body_changed` 追溯。

## 验收与限制

2026-10-22 用户指定链接已通过真实入口保存《-12%，跌太狠了》的 Markdown 和 2 张本地配图，核对文章身份、原文时间、文件哈希与本地引用；重复执行直接复用。证据见 [链接归档验证摘要](/Users/chenge/project/liumo/evidence/feasibility/manual-url-archive.json) 。此前匿名 HTTP 请求受限的失败记录保持原样，不据此推断失败的唯一原因。

当前针对可正常访问的标准图文页面，不保证所有公众号页面都可取得。付费／权限／风控限制不会绕过；图集专用版式、视频、音频和交互组件未实现完整转换。单篇上限为 10 MiB 提取正文、25 个保留图片节点、每张图片 25 MiB，滚动最多 100 步。图片型正文是否含可见文字不由 OCR 补全。隐藏面板被过滤，但不承诺复制原站排版。手动已保存的文章未来仍可能被 RSS 另存为快照，这是两个来源的独立档案，不会修改自动追更基线。

复现专项测试：

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_manual.py' -v
LIUMO_BROWSER_TESTS=1 .venv/bin/python -m unittest discover -s tests -p 'test_manual_browser.py' -v
```

前者验证输入、状态与失败路径；后者使用本地构造页面验证实际 Chrome 提取和离线图片加载，不访问真实微信，不把构造测试等同于真实公众号全覆盖。完整检查入口见 [README](/Users/chenge/project/liumo/README.md) 。
