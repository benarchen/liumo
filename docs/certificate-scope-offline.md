# 证书域名约束：离线验证

2026-10-18，北京时间。对应原 Goal 的 C13；仅构造证书和离线验证，不安装信任、不监听、不访问微信或修改系统设置。[证据索引](/Users/chenge/project/liumo/evidence/feasibility/certificate-scope-offline.json) 。

## C14 补充定位：无效信任结果与框架内部错误

本次保持 `-N`、`-L`、`-R offline`、SSL 主机策略与 C13 同一组公共证书不变，只将 `-q` 换成 `-v`。一次实际诊断取得：退出码 1、`NSOSStatusErrorDomain / -26276`、`TrustResultValue = 0`，同时仍有 CT／SCT 提示。旧正对照没有得出有效信任决定，不能当作名称约束拒绝，更不能把 CT 提示当作唯一原因。[C14 证据](/Users/chenge/project/liumo/evidence/feasibility/native-control-diagnostic.json) 。

这里有一个已确认的程序诊断问题：Apple 的 [verify_cert.c](https://github.com/apple-oss-distributions/Security/blob/main/SecurityTool/macOS/verify_cert.c) 在 quiet 模式隐藏主要失败信息，而 TLS 扩展输出不受同一条件保护。留墨此前 `native_CT_policy_control_failed` 分类名称不准确，现改为读取 verbose 输出中的固定数字字段；CT 只作为是否出现该提示的布尔值。

Apple [SecBasePriv.h](https://github.com/apple-oss-distributions/Security/blob/main/base/SecBasePriv.h) 将 -26276 命名为 errSecInternal；本机 MacOSX27.0 SDK 的公开 SecTrust.h 第 90 至 97 行将结果 0 定义为 Invalid、1／4 为成功、3／5／6 为拒绝、7 为其他错误。源码访问日期为 2026-10-18；Apple main 文件未与本机 macOS 27.0.1／26A434 二进制逐版本匹配，固定标签文件读取未成功，不能推断内部错误的具体触发机制。SDK 路径和 SHA-256 见索引。

已修正验证程序：退出码 0 还须有有效成功决定且没有矛盾错误；内部错误、结果 0／7、未知或矛盾诊断都保持未验证；结果 3／5／6 才记录拒绝，最终矩阵仍要求正负对照完整。`Cert Verify Result: No error.` 这类附带文字不能覆盖数值错误。CT 提示与一个真实成功决定共存时，也不会单独把成功改成失败。没有改变证书、SSL 目的、CT 或系统信任策略。

普通终端对照现已取得：2026-10-18 14:45：已核对普通终端 C14 离线结果。macOS 正对照退出 0、信任结果 4，CT 提示与成功决定并存；两个验证器各 51 项均取得结果，改进候选各 17 项符合预期，朴素方案各有 7 个范围遗漏。未安装信任、改代理或访问微信。程序／测试 38 份哈希与 200 项回归基线一致，未重复运行。显式根结果不等于安装后信任或微信兼容；新证书亦使本次不能单独证明旧 Agent 内部错误的根因。该离线检查点完成，原 Goal 仍 blocked、未完成。[终端证据](/Users/chenge/project/liumo/evidence/feasibility/native-control-terminal.json) 。

本次新归档的 macOS 无约束对照为 14 接受／3 拒绝，朴素约束为 9 接受／8 拒绝，改进候选为 2 接受／15 拒绝；OpenSSL 结果逐项一致。范围外拒绝具有效信任结果 5，没有把工具错误计作保护成功；范围类结果数字错误为 -67689，过期与错误签名对照分别为 -67818／-25318，不据代码数字自行扩展未核对的原因解释。

新档案 [certificate-scope.json](/Users/chenge/project/liumo/archives/feasibility/20261018T064123479907Z-certificate-scope-offline/certificate-scope.json) 包含 102 行真实离线结果和 20 张公共证书；已核对证书签名、critical 约束、SAN、无私钥内容及代码基线。原 C13／Agent 诊断档案保留，不覆盖为成功。

新增内部错误与 CT 并存、成功与 CT 并存、真实拒绝／无效结果、矛盾输出、超长输出和脱敏测试；当前完整回归为 200 项，196 通过、4 跳过。以下保留 C13 原始阶段结果，其证据未覆盖改写。

## C13 结论与证据等级

- **Python／OpenSSL 离线分项通过**：改进候选的 17 个场景均符合预期。目标域及其大小写形式通过，12 个范围外证书被域名约束拒绝，另外 3 个错主机／过期／错误签名对照也被拒绝。
- **朴素方案不满足边界**：只许可 DNS 子树时，子域、子域通配符、带子域的混合 SAN、IPv4／IPv6 及带 IP 的混合 SAN 共 7 个场景仍被接受，不能把这种证书称为精确限定目标域。
- **macOS 未验证**：显式根的无约束目标正对照退出码为 1，输出含“缺少至少两个合格 SCT”的 CT 提示。程序记录固定诊断类别，但它不足以认定唯一失败原因，更不能当作域名约束拒绝成功。后续 51 行 macOS 矩阵均标记未执行／未验证，没有关闭 CT 或改换验证策略强行通过。
- **微信未验证**：没有调用微信客户端，没有把候选接入代理，不能证明它会接受该证书，或在将根安装为系统信任锚后仍执行同样限制。整体为 `partial`，原 Goal 未完成。

本轮只完成离线检查点，不足以直接移除旧信任命令中的 `-s` 或启动新抓取实验。

## 设计与实际矩阵

三张构造根使用同一公钥、主题及有效期，仅约束配置等证书字段不同；每个场景的同一张服务端证书在三种根下重复核验，减少密钥、签名、主机匹配等差异。根直接作为测试验证器的显式信任锚，不使用“无约束根＋受限中间证书”代替根约束验收。

| 配置 | 根证书约束 | 用途 |
| --- | --- | --- |
| unconstrained | 无 NameConstraints | 每个场景的签名、有效期与主机匹配对照，不可部署 |
| dns_only | critical；许可 DNS 子树 mp.weixin.qq.com | 验证朴素方案遗漏的范围 |
| exact_dns_no_ip | critical；许可目标 DNS 子树；排除 `.mp.weixin.qq.com` 子域及全部 IPv4／IPv6 | 本轮候选，在已测 OpenSSL／macOS 显式根场景成立 |

Python 3.14.5／OpenSSL 3.6.3 使用 SSLContext、CERT_REQUIRED、主机检查、VERIFY_X509_STRICT 和显式测试根；禁用 CN 回退，没有忽略证书错误或降低校验。TLS 客户端和服务端通过 MemoryBIO 交换真实 TLS 字节，无 TCP 监听或网络请求，实际成功握手为 TLSv1.3。

| 场景 | 无约束对照 | DNS 子树许可 | 改进候选 |
| --- | --- | --- | --- |
| 目标域、目标域大写形式，2 项 | 接受 | 接受 | 接受 |
| 无关域、恶意后缀、相似前缀、父域通配符，4 项 | 接受 | 拒绝 | 拒绝 |
| 目标＋无关域的混合 SAN，1 项 | 接受 | 拒绝 | 拒绝 |
| 子域、子域通配符、目标＋子域混合 SAN，3 项 | 接受 | 接受 | 拒绝 |
| IPv4、IPv6、目标＋IPv4／IPv6 混合 SAN，4 项 | 接受 | 接受 | 拒绝 |
| 错主机、过期、错误签名，3 项 | 拒绝 | 拒绝 | 拒绝 |

完整逐项结果和公共证书位于 [最终复现目录](/Users/chenge/project/liumo/archives/feasibility/20261018T043506479196Z-certificate-scope-offline) ，其中 [certificate-scope.json](/Users/chenge/project/liumo/archives/feasibility/20261018T043506479196Z-certificate-scope-offline/certificate-scope.json) 有 102 行矩阵：51 次实际内存握手及 51 行未执行的 macOS 结果。原始服务端私钥临时文件已清理，CA 私钥仅在内存；档案只留公共证书。测试证书有效期很短，复现时生成新证书，不安装或复用归档证书。

C13 的 macOS 命令使用 `security verify-cert -q -N -L -R offline -p ssl -n HOST -r TEST_ROOT -c TEST_LEAF`；C14 仅将静默参数改为 `-v`。只读取显式测试文件，不搜索钥匙串，不请求在线补链／吊销信息。无约束正对照不成立后不执行其他矩阵请求；非零退出、未知诊断、超时或工具不可用都不能标记为约束保护成功。首次程序运行和一次正对照输出核对后，补齐固定诊断分类，再完成 C13 最终程序复现；没有尝试通过关闭 CT 或更换校验策略来消除失败。

## 复现与自测

复用 `.venv-capture/` 已有 cryptography 46.0.4；标准库不能直接签发 X.509 构造证书，因此使用已安装组件，不新增依赖。主验证环境仍为 `.venv/`；只有这项离线签发探针需要隔离环境。

```bash
cd /Users/chenge/project/liumo
.venv-capture/bin/python -m validation certificate-scope-fixture
.venv/bin/python -m unittest discover -s tests -v
```

第一条生成新的独立归档，整体为 partial 时退出码为 2，表示离线分项结果已交付、其他验证器及微信没有通过。它不写 `.auth/`、不修改实际采集证书、不启动采集。CLI 不接受任意域名、URL、证书或系统操作参数。

C13 阶段完整回归为 198 项：194 通过、4 跳过、0 失败；C14 修正后为 200 项、196 通过、4 跳过，本次代码哈希未变。C13 新增 5 项测试覆盖矩阵完整性／重复项、正对照失败、未知验证错误不误报、固定本地校验参数、真实内存握手、7 个遗漏样本及混合 SAN、私钥清理、异常清理和已有输出不覆盖。真实握手测试额外阻止 socket 创建，macOS 固定命令由构造回放验证；macOS 实际执行结果以新普通终端归档为准。4 项跳过仍为 3 项浏览器未开启和 1 项回环监听权限拒绝。

## 一手依据及剩余门槛

以下资料访问日期均为 2026-10-18。

- [RFC 5280，第 4.2.1.10 节](https://datatracker.ietf.org/doc/html/rfc5280#section-4.2.1.10) 说明名称约束及 DNS 子树语义；[第 6.2 节](https://datatracker.ietf.org/doc/html/rfc5280#section-6.2) 明确实现可处理或忽略信任锚自签证书中的额外信息。因此，“证书写了约束”不能等同所有客户端都会执行。实际处理以各验证器的结果为准。
- [cryptography 46.0.4 NameConstraints API](https://cryptography.io/en/46.0.4/x509/reference/#cryptography.x509.NameConstraints) 用于构造测试证书，未复制或执行业务参考源码。
- [Python 3.14 MemoryBIO 文档](https://docs.python.org/3.14/library/ssl.html#ssl.MemoryBIO) 支持将 TLS 与网络 IO 分离；本次使用实际内存握手，非模拟接受／拒绝结果。
- [Chromium 当前 macOS 信任代码](https://chromium.googlesource.com/chromium/src/+/main/net/cert/internal/trust_store_mac.cc) 的读取位置及固定版本证据沿用 [C12 报告](/Users/chenge/project/liumo/docs/wechat-profile-route-review.md) 。当前源码处理信任锚约束，不能据此推定本机微信的内核版本、调用路径或行为。

macOS 显式根正对照及矩阵已通过，下一步需要区分显式测试锚与已安装信任锚的行为。尚未证明微信接受候选，也未证明安装后的约束行为。[下一次无网络对照方案](/Users/chenge/project/liumo/docs/installed-anchor-experiment.md) 已明确不使用旧 -s 字符串的变更与风险；C15 普通终端安装后矩阵及后续独立撤销已取得有效通过证据，原 120 秒自动收尾未通过。撤销预算已修正且回归通过，尚未重新系统实测；微信兼容仍独立待验证，无需用户重复命令。没有安装后及实际客户端证据，就不将候选纳入真实采集链。
