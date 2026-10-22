# 开发、依赖与质量检查

当前实际验证环境为 macOS 27.0.1、arm64、Python 3.14.5、系统 `/usr/bin/curl` 8.7.1。浏览器检查使用本机 Chrome 155.0.8059.85 和 Playwright 1.64.0。旧 JS 实验使用 Node v26.0.0 与已有项目内 Acorn。其他平台与 Python 版本未纳入本轮验收。

## 运行代码与依赖

- `liumo/common.py`：文件原子写入、互斥锁、时间与公开链接清理。
- `liumo/render.py`：纯正文 Markdown 和本地图渲染，不启动浏览器或自带网络客户端。
- `liumo/browser.py`：可见正文选择、页面观察、时间核对和限定字面量提取；只在调用驱动时加载 Playwright。
- `liumo/schedule.py`、`liumo/notify.py`：上海四点计算与本机通知出口。
- RSS、账本、历史、完整性和修复仍在原有业务模块；不改变目录、身份、schema 或归档类型。
- `validation/` 保留旧实验和显式诊断，反向引用正式共享实现；`liumo/` 不导入 `validation`。`tools/` 只做工程检查，不进入产品运行链。

[核心依赖](/Users/chenge/project/liumo/requirements-core.txt) 包含已固定的 BeautifulSoup、markdownify 及其运行依赖，共 5 个包；RSS、历史、完整性检查和注入页面的产品逻辑测试无需 Playwright、Node 或抓包组件。[浏览器依赖](/Users/chenge/project/liumo/requirements-browser.txt) 在核心之上增加既有 Playwright、pyee、greenlet，用于显式手动读取页面。根 `requirements.txt` 保留完整浏览器环境的兼容安装入口，不新增第三方依赖。

新建独立环境，而非覆盖正在运行的 `.venv/`：

```bash
mkdir -p .tmp/development
python3.14 -m venv .tmp/development/core-env
.tmp/development/core-env/bin/python -m pip install -r requirements-core.txt
.tmp/development/core-env/bin/python -m pip check
.tmp/development/core-env/bin/python -m tools.check --suite product
```

本轮复现实际使用全新 `.tmp/p1-p2-remediation/g4/env/`，从本机已有固定 wheel 缓存离线安装，无 system-site-packages，也不链接旧 site-packages。安装命令额外使用 `--no-index --find-links .tmp/feasibility/downloads`；缓存仅用于本次重建，不是产品运行依赖。本轮未重新验证在线包下载。

手动页面环境可安装 `requirements-browser.txt`，使用已安装 Chrome，不默认运行浏览器下载命令。缺少 Playwright 时，普通 CLI 与核心功能仍可加载；真正调用页面驱动才返回 `browser_dependency_missing_install_requirements_browser`，对应处理为：

```bash
.venv/bin/python -m pip install -r requirements-browser.txt
```

旧抓包构造测试继续使用已有独立 `.venv-capture/` 和 `requirements-capture.txt`，不将其加入产品依赖；安装组件不代表授权启动真实抓包、证书或系统实验。

## 版本化检查入口

在项目根目录执行：

```bash
.venv/bin/python -m tools.check --static-only
.venv/bin/python -m tools.check --suite product
.venv/bin/python -m tools.check --suite browser
.venv/bin/python -m tools.check --suite legacy
.venv/bin/python -m tools.check --suite all --list
.venv/bin/python -m tools.check --suite all
```

所有入口先核对 Python 语法、正式模块的静态／字面量动态导入边界、Markdown 围栏及本地链接／锚点、Roadmap 记录顺序和条数。静态检查不运行页面脚本、不自动改文件；测试使用隔离目录，会生成可重建产物。

`product` 为产品纯逻辑，`browser` 为显式本地页面回归，`legacy` 为旧实验构造回归（其中也有本地浏览器和回环测试）。后两组及 `all` 显式启用本地浏览器测试，不请求微信。`--list` 只收集，不执行测试，使用能导入对应测试依赖的环境。

报告提供收集、实际运行、通过、失败、错误、跳过数及分层计数；失败、漏跑或跳过返回非零。分组依据实际文件清单并核对并集，既有全量入口保持可用：

```bash
mkdir -p .tmp/wechat-session-validation
LIUMO_BROWSER_TESTS=1 .venv/bin/python -m unittest discover -s tests -v
```

不设置浏览器开关时，unittest 的显式跳过不能当成验证通过。若沙盒阻止 Chrome 或回环监听，通过平台权限机制处理，不能把浏览器启动失败改为测试通过，也不用用户换普通终端代跑。

## 诊断入口迁移

历史原页 `liumo page-sample` 已迁到 `validation page-sample`，参数仍为 `--headed` 和 `--wait-readable`。仅查看帮助不会打开页面；真正执行会请求来源并读取原页，属于旧诊断，不是日常 RSS 使用步骤，不自动重开：

```bash
.venv/bin/python -m validation page-sample --help
```

历史共享函数的导入入口保留兼容，底层实现统一到 `liumo/`。数据文件无需迁移，也不会因为重构批量重写旧 metadata。`complete`、`processing_status`、文件完整性与来源覆盖继续分别解释，见 [完整性说明](/Users/chenge/project/liumo/docs/archive-integrity.md) 和 [历史导入说明](/Users/chenge/project/liumo/docs/history-import.md) 。
