# 留墨版本管理与首次工程基线

用户于北京时间 2026-10-20 授权初始化 Git、提交当前快照、建立本地分支与附注基线标签，并创建、同步公开 GitHub 仓库 `benarchen/liumo`。本次授权替代此前阶段“不提交／不推送”的范围限制；不改变产品验收条件，不创建新 Goal。

## 分支与标签

- `dev`：日常开发与提交，完成同步后切回此分支。
- `main`：经过相应检查的集成快照；不等于每次都已完成正式试用。
- `baseline-20261020`：首次工程基线的附注标签，包含范围、验证与未完成项说明，不作为 `v1.0.0` 发布。

首次仓库从 `dev` 创建根提交，随后从同一提交建立 `main`。此时不存在旧的 `main` 历史需要合并，也不人为增加空提交或合并提交。核对 `main` 后打标签，再切回 `dev`；两个分支及标签解引用必须相同。

后续在 `dev` 完成提交、文档同步与必要检查后，再按以下顺序集成：

```bash
git switch main
git merge --ff-only dev
# 根据当次已授权的版本名创建附注标签。
git switch dev
```

`--ff-only` 在分叉时停止，不丢弃另一侧的提交。既有基线标签不移动；本次不添加全局 Git 配置、自动推送钩子、CI 或分支保护。

## 基线内容与验收边界

纳入现有运行代码 `liumo/`、可行性程序 `validation/`、必要测试、固定依赖清单、项目文档、脱敏证据、构造样本及 plist 模板。旧实验代码保留为历史验证工具，不代表默认运行链，也没有改为验收通过。

猫笔刀单号 RSS 快照、队列／去重／恢复及本机后台已交付；本次完整回归为 415 项全部通过。技术样本已保存正文及配图；正式库截至 2026-10-20 23:30 检查仍只有 20 条基线，没有正式新增归档。用户已确认本机通知可见。原站截图、评论、原文时间与第二号暂缓；正式新增、设备行为和长期可靠性保留未验证状态。打标签不关闭当前长期 Goal。

## 公开范围与本机数据

公开同步目标：[https://github.com/benarchen/liumo](https://github.com/benarchen/liumo) 。推送使用本机已有 SSH 身份，远端 `main` 为默认分支，同时同步 `dev` 和上述基线标签；不创建 GitHub Release。

`.gitignore` 排除 `.auth/`、`archives/`、`state/`、`.tmp/`、日志、环境文件、虚拟环境、Node 依赖及本地 AI 配置。公开范围检查包含：Git 实际候选清单、私钥／常见 token／凭证赋值／敏感 URL 扫描、命中项人工分类、受保护路径的忽略核对；构造值和公开文章 ID 与真实凭证分开。扫描不构成不存在任意未知秘密的绝对保证。

GitHub 保存工程文件，不能恢复真实文章、本机数据库、凭证或系统中已安装的任务；它不代替这些数据的独立备份。现有绝对本机路径保留为本机文档入口，在其他电脑需使用其实际项目路径；示例 plist 不会因克隆仓库自动安装。

## 核对入口

```bash
git status --short --branch
git rev-parse main dev 'baseline-20261020^{}'
git show --no-patch baseline-20261020
git remote -v
git ls-remote origin refs/heads/main refs/heads/dev refs/tags/baseline-20261020 'refs/tags/baseline-20261020^{}'
```

版本名与提交身份以实际 Git 引用为准；公开仓库可见性与默认分支以 GitHub 返回结果为准。基线自测与范围记录见 [验证摘要](/Users/chenge/project/liumo/evidence/feasibility/git-baseline.json) ，项目验收状态见 [ROADMAP.md](/Users/chenge/project/liumo/ROADMAP.md) 。
