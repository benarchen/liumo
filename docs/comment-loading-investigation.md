# 评论加载机制静态排查

核对时间：2026-10-18 22:57（北京时间）。本轮只读检查已有材料和公开源码；未启动新系统实验、读取旧凭证值或重放请求。原 Goal 服务状态为 blocked，评论真实验证未完成。

## 当前结论

当前缺口是正常文章的实际评论加载机制。还没有证据选择新端点、认定原生桥接或归因 Cookie。C22 的 24 项是同一个 `/mp/appmsg_comment` 路径的请求／响应分类计数，不是 24 个端点；即使请求方法、action 或文章标识不同，也先进入该路径的分类。全部为 0，只证明本次代理没有观测到这个路径。

C22 文章类响应 1 次，目标域响应共 20 次，其余 19 次只保留汇总计数，没有路径、正文或脚本。它们是否包含评论数据无法追溯。页面留言及作者回复可见，不能据此区分其他接口、HTML 内嵌数据、原生调用或已有页面状态。[C22 现场索引](/Users/chenge/project/liumo/evidence/feasibility/comment-refresh-live.json) 、[分类实现中的 comment_match_category](/Users/chenge/project/liumo/validation/comment_baseline.py) 。

## 本地材料核对

| 材料 | 实际保留内容 | 可用于评论脚本分析 |
| --- | --- | --- |
| 两份早期下载 HTML | 每份 18165 字节；含“环境异常／验证”提示，正文容器及已检查评论标记为 0 | 否，属于验证页面，不是可读文章 HTML |
| 四次早期浏览器观察 | 结构化页面观察与正文文本，没有原始 HTML 或脚本列表 | 否，不能从观察摘要恢复脚本 |
| C20 正文功能验证 | HTTP 200、3493257 字节、独立文章身份通过；只保留摘要 | 否，没有保存该 HTML |
| C22 正常微信刷新 | 请求计数、界面观察与恢复证据 | 否，没有保留文章 HTML 或其他响应 |

两份验证页中的 `js_content`、`cgiDataNew`、`appmsg_comment`、`getcomment`、`elected_comment`、`WeixinJSBridge`、`getappmsgext` 均为 0。这不是两篇文章没有评论或必须登录的证据。文件 SHA-256、固定标记数量和源码版本见 [静态证据索引](/Users/chenge/project/liumo/evidence/feasibility/comment-loading-investigation.json) 。

在项目根目录可重复以下本地核对；临时材料缺失时停止，不自动联网、补抓或登录：

```bash
.venv/bin/python - <<'PY'
import hashlib, json
from pathlib import Path
markers = ('环境异常', '验证', 'js_content', 'cgiDataNew', 'appmsg_comment',
           'getcomment', 'elected_comment', 'WeixinJSBridge', 'getappmsgext')
for name in ('maobidao', 'stormzhang'):
    raw = (Path('.tmp/feasibility/downloads') / (name + '.html')).read_bytes()
    text = raw.decode('utf-8')
    print(json.dumps({'sample': name, 'bytes': len(raw),
        'sha256': hashlib.sha256(raw).hexdigest(),
        'markers': {key: text.count(key) for key in markers}}, ensure_ascii=False))
PY
```

## 公开实现复核

以下访问日期均为 2026-10-18，仅作为源码证据，没有安装、运行或复制其代码进入留墨运行链。

1. exporter 固定提交 `152f23832c7f3664b86148e84bd3f75e513e4dd2`：`fetchComments` 使用 `/mp/appmsg_comment?action=getcomment`，回复使用同一路径的 `getcommentreply`。源码支持现有请求的参考来源，但不能证明当前 Mac 微信实际走此路径。[评论实现](https://github.com/wechat-article/wechat-article-exporter/blob/152f23832c7f3664b86148e84bd3f75e513e4dd2/utils/download/Downloader.ts#L462) 。本轮重新在线读取评论函数，并核对既有 32 份参考文件的 SHA-256。
2. 同版本 exporter 从文章内的 `window.cgiDataNew` 脚本提取数据。[HTML 解析实现](https://github.com/wechat-article/wechat-article-exporter/blob/152f23832c7f3664b86148e84bd3f75e513e4dd2/shared/utils/html.ts#L132) 。该变量存在与否不等于评论正文已内嵌；上游执行脚本的方式也不需要直接照搬到本轮静态检查。
3. `ltaoo/wx_channels_download` 固定提交 `124f044235bc706fe796c043a14ff442a150ae5d`：公众号解析器同样检查文章脚本，前端读取 `cgiDataNew`／`cgiData` 并创建正文下载任务。[解析器](https://github.com/ltaoo/wx_channels_download/blob/124f044235bc706fe796c043a14ff442a150ae5d/pkg/scraper/wxmp/util.go#L96) 、[页面变量读取](https://github.com/ltaoo/wx_channels_download/blob/124f044235bc706fe796c043a14ff442a150ae5d/pkg/scraper/wxmp/inject/mp.utils.js#L22) 、[正文下载入口](https://github.com/ltaoo/wx_channels_download/blob/124f044235bc706fe796c043a14ff442a150ae5d/pkg/scraper/wxmp/inject/mp.main.js#L139) 。已读四份公众号相关文件并核对 Git blob 身份；未找到可借用的评论取数逻辑。`sns_write_comment_btn` 在所读代码中是下载按钮复用的 CSS 类，不能误判为评论接口。没有把其视频号代码当作公众号方案，也没有采用其页面注入或系统设置。

有限搜索未找到新端点，不证明不存在新端点；旧镜像文章和第三方 HTTP 测试流量未作为当前微信协议依据。当前不继续扩展候选工具，也不依据“看起来类似”修改请求。

## 下一步最小取证方案

以下保留 C23 提案的范围。C24／C25 未读到 HTML；C26 已取得一份独立身份通过的有效 HTML，仅在内存分析后丢弃。真实两条 Content-Type 已证明等价，但不能倒推旧实验。57 个 script 中 2 个外部来源均被拒绝，未取得白名单脚本地址；标记词频不证明调用关系，评论通道仍未知。C26 已恢复并关闭，不再要求刷新或重跑。实际结果见 [实施说明](/Users/chenge/project/liumo/docs/article-static-validation.md) 。

优先取得同一猫笔刀技术样本的一次有效文章响应，在内存中做静态分类，先判断应分析哪份页面代码。它不是重跑 C21／C22，也不再预设评论必须走旧端点。

- 范围：只匹配固定文章、正常刷新一次；复用已验证的有限时控制与收尾机制，使用新的独立单次目录。最多读取一份文章 HTML，编码及解压后各不超过 4 MiB。超限明确失败，不截断分析。
- 输出：正文身份验证结果、固定评论／桥接／内嵌数据标记数量，以及经过域名和路径白名单验证、移除查询及片段的腾讯公共静态脚本来源。有效身份通过前不输出脚本清单；不保存原始 HTML、Cookie、token、任意内联脚本或留言文本，不执行页面脚本、不注入代码、不读取应用缓存。
- 后续：仅在公开脚本来源得到确认后，再只读获取这些公共脚本，提取具体调用依据；若出现其他域名或动态地址，停止并评审，不能发送会话字段去探测。未经核对的请求路径不直接写普通日志。
- 自测要求：构造有效正文、验证页面、错文、畸形编码、压缩超限、含敏感查询的脚本地址和未知主机；检查拒绝路径、输出脱敏、一次性与超时收尾。不以构造结果代替正常微信实测。
- 实际验收：文章身份通过且取得可用加载线索，才能算“页面静态取证”通过；仅有变量名或脚本 URL 仍不算成功评论基线。没有线索时记录失败，不再重复同一方向的刷新实验。
- 权限边界：C24／C25／C26 授权均已执行并消耗，不能继续使用旧目录或回执取得重试。

C27 当前只准备内联脚本语法分析：使用构造样本区分注释、字符串与静态调用候选，不执行 JS。真实 HTML 已丢弃，不能用旧摘要代替新输入；新的真实取证须待程序自测后独立评审。Acorn 已在普通终端安装成功，版本／缓存包完整性／lockfile 和 12 项 AST 构造专项已核对，完整回归 341 项为 337 通过、4 跳过；当前未分析真实内联脚本。C28 已实测并恢复：正文身份通过、经典 53／module 2／外部 2，内联 AST 触发本地 node_limit；原始输入已丢弃，不能追补计数。离线容量候选构造通过、RSS 未验；下一轮证据保留方式待用户明确，旧 C28 不重跑。[依赖证据与复现步骤](/Users/chenge/project/liumo/docs/inline-script-validation.md) 。

若该阶段仍无法确定实际通道，需要另行比较可验证的取证手段或向用户提交产品取舍；不能静默改成正文截图、重绘评论页或放弃自动追更。两号评论、回复与原页单张整图仍分别待验收。
