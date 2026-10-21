# 猫笔刀后台运行与停用恢复

用户于 2026-10-20 确认继续后台安装。留墨专用用户级任务已安装并加载；默认仍只访问公开 RSS 和腾讯配图，不使用账号会话、不打开微信原文。当前安装不改变 RSS 快照、原文时间待核实或原页截图暂缓的边界。

## 配置及运行

- 系统配置：[local.liumo.maobidao.plist](/Users/chenge/Library/LaunchAgents/local.liumo.maobidao.plist) 。
- 项目模板：[local.liumo.maobidao.plist](/Users/chenge/project/liumo/examples/local.liumo.maobidao.plist) ，安装时逐字节核对一致。
- 用户域与服务：`gui/501/local.liumo.maobidao`，只在当前用户登录会话内运行，不是登录前启动的系统守护程序。
- 工作目录为项目绝对路径，解释器使用项目 `.venv/bin/python`，调用 `-m liumo tick --data-dir /Users/chenge/project/liumo/state/maobidao`，不依赖 `.tmp/` 或终端保持打开。
- 原生日历每分钟触发轻量 tick，Python 按上海时区计算 22:00、22:30、23:00、23:30。错过多次合并，已知网络／服务失败到退避期限后可在窗口外恢复；不是每分钟请求 RSS。
- 输出与错误日志：[scheduler.log](/Users/chenge/project/liumo/state/maobidao/scheduler.log) 、[scheduler-error.log](/Users/chenge/project/liumo/state/maobidao/scheduler-error.log) 。不记录正文 HTML、Cookie 或凭证。

不修改 Mac 时区、网络、代理、证书或其他 LaunchAgent。无常驻 Python 进程时 `state = not running` 是正常空闲状态；是否加载、执行次数、退出码及日志需要一起判断。

## 状态检查

```bash
cd /Users/chenge/project/liumo
.venv/bin/python -m liumo status
launchctl print gui/501/local.liumo.maobidao | awk '/^[ \t]*(state|runs|last exit code) = /'
```

status 中 `status=complete` 表示查询命令成功，服务是否健康应看 `last_outcome`、`next_retry_at` 和未完成任务；不能用查询成功掩盖上一次网络失败。

## 暂停与恢复

临时停止当前登录会话的任务，配置及数据均保留：

```bash
launchctl bootout gui/501/local.liumo.maobidao
```

恢复已停止的任务：

```bash
launchctl bootstrap gui/501 /Users/chenge/Library/LaunchAgents/local.liumo.maobidao.plist
```

这对命令已在本轮新安装任务上实际验证，停用后任务确实不存在，恢复后再次加载并退出 0。配置、归档和 SQLite 均保留。不要对一个已经加载的任务反复 bootstrap。

bootout 只停止当前会话，下次登录仍可能自动加载。若要跨登录保持停用，可先执行以下专用开关，再 bootout：

```bash
launchctl disable gui/501/local.liumo.maobidao
```

之后恢复前先执行 enable，再 bootstrap：

```bash
launchctl enable gui/501/local.liumo.maobidao
```

本轮核对了 enable／disable 的本机命令语法，但没有额外演练持久禁用或注销／重新登录；不要把它写成设备重登通过。不通过删除 plist 或清空状态库停用项目。

## 验证边界

安装前没有同名任务、文件或用户禁用记录。安装后 RunAtLoad 实际执行退出 0；之后执行次数和输出条数自然增加，证明日历心跳已触发。停用／恢复验证退出码均为 0，未改其他任务或系统时区。

安装前正式状态已有一次 20:47 的 public_transport_failed，退避到 21:02:07。安装后的初次心跳返回 failure_backoff，没有提前请求 RSS；21:03:05 的自然日历执行实际补查成功，20 条记录、0 新增、0 未完成，清除了退避。未手动触发补查、未改时间或伪造时钟；这是已知失败后的真实后台补查，不证明此前失败根因或物理断网／联网行为。[后台证据](/Users/chenge/project/liumo/evidence/feasibility/maobidao-launchd.json) 。

本机通知测试已经提交并退出 0，用户随后明确回复「我看到了通知」，桌面可见性已获用户确认。2026-10-21 22:00:05 的正式后台检查发现并归档《带头大哥肿么了...》，22:00:07 完成，随后三次来源检查没有重复归档或未完成任务，正式归档通知调用成功。该次具体通知的桌面可见性未另获确认。真实断网／恢复、休眠唤醒和长期稳定性保留后续；不以心跳或构造代验。[结项证据](/Users/chenge/project/liumo/evidence/feasibility/maobidao-mvp-closeout.json) 。
