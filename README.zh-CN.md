# Project Governor

[English](README.md) | [简体中文](README.zh-CN.md)

Project Governor 是一个面向 iOS 与 SwiftUI 项目的 Codex 插件。它通过明确的项目契约、可复现的真实证据和独立评审来约束功能迭代。

当前 `0.1.0` 是 iOS/SwiftUI MVP。它是本地质量门，不是不可绕过的安全边界。

## 为什么需要 Project Governor？

功能迭代很容易不断积累页面、概念、入口和一次性交互模式。Project Governor 会在接受变更前把这些成本暴露出来：

- 实现功能前，先明确项目意图与边界。
- 现有代码只是证据，不会自动成为正确规范。
- 功能变更不能暗中修改契约、例外或 reviewer 设置。
- 构建、测试、模拟器、截图和交互结论必须有真实证据。
- 架构与 UI reviewer 使用隔离的只读 bundle，看不到实现过程的对话。
- 最终 gate 使用明确条件，不使用综合评分。

## 公开 skills

| Skill | 作用 |
| --- | --- |
| [`project-governor-init`](plugins/project-governor/skills/project-governor-init/SKILL.md) | 扫描 iOS 项目、初始化 `.governance`，或单独重新校准已批准契约。 |
| [`project-governor-change`](plugins/project-governor/skills/project-governor-change/SKILL.md) | 准备并实现一次有边界的功能变更，收集证据并执行 gate。 |
| [`project-governor-review`](plugins/project-governor/skills/project-governor-review/SKILL.md) | 重新执行只读架构或 UI 评审，不修改代码，也不规定解决方案。 |

## 工作流程

```text
inspect → 用户确认 → initialize
                        ↓
                   prepare 变更
                        ↓
                    实现候选
                        ↓
             构建/测试 + 模拟器证据
                        ↓
              隔离的架构/UI reviewer
                        ↓
                 pass / fail / blocked
```

只有当所有必要检查与 reviewer 均通过、证据完整、受保护状态与锁定版本一致、候选没有漂移、且不存在 `unverified` 声明时，gate 才会通过。

## 环境要求

- macOS
- Git
- Python 3.9 或更高版本；runtime 只使用标准库
- Codex CLI
- Xcode 与项目要求的 iOS Simulator runtime
- 用于构建和 UI 测试证据的 shared Xcode scheme

如果缺少确定性的 XCUITest 场景或必要 runtime，UI 变更会返回 `blocked`；纯架构评审仍可运行。

## 安装

先添加仓库 marketplace，再安装插件：

```bash
codex plugin marketplace add zkhCreator/agent-team-skills
codex plugin add project-governor@personal
```

本地开发安装：

```bash
git clone https://github.com/zkhCreator/agent-team-skills.git
codex plugin marketplace add /absolute/path/to/agent-team-skills
codex plugin add project-governor@personal
```

检查安装结果：

```bash
codex plugin list
```

## 快速开始

在 Codex 中打开一个 iOS/SwiftUI 仓库，然后初始化项目契约：

```text
使用 $project-governor-init 扫描这个仓库，并帮助我初始化治理契约。
```

执行一次功能变更：

```text
使用 $project-governor-change，在已批准的项目契约内实现这个功能：<目标>。
```

独立重跑最新评审：

```text
使用 $project-governor-review 评审最新的 Project Governor 候选。
```

初始化 skill 会刻意分开只读扫描和写入操作。当 Xcode container、scheme、产品偏好、参考页面或其他契约决策无法安全推断时，它会要求用户确认。

## Runtime CLI

插件提供七个稳定命令：

```text
governor.py inspect       只读扫描项目与能力
governor.py initialize    创建已确认的 .governance 状态
governor.py recalibrate   重新锁定单独批准的治理更新
governor.py prepare       创建变更 spec 与事实 ledger
governor.py verify        冻结、检查、取证、评审并执行 gate
governor.py review        对已有冻结 run 重新评审
governor.py eval          运行插件自身测试
```

只读扫描示例：

```bash
python3 plugins/project-governor/scripts/governor.py inspect \
  --project-root /path/to/ios-project
```

退出码属于稳定自动化接口：

| 退出码 | 含义 |
| --- | --- |
| `0` | 通过 |
| `1` | 有证据支持的检查或规则失败 |
| `2` | 因证据缺失、版本不兼容、工具不可用、漂移或治理冲突而阻塞 |
| `3` | 配置或内部错误 |

## 项目内状态

初始化只会在目标仓库写入 `.governance/`。主要内容包括：

```text
.governance/
├── project.json
├── lock.json
├── contracts/
├── references/
├── decisions/
├── changes/<change-id>/
└── .runs/<run-id>/
```

契约、决策、参考配置和 `lock.json` 都是受保护内容。普通功能变更不能修改它们。如果变更需要例外或新标准，本轮会被阻塞，必须先通过独立的 `recalibrate` 操作批准并重新锁定该决策。

## 独立评审

每个 reviewer 都会在新的临时目录中运行，通过 ephemeral Codex 进程、只读 sandbox 与严格 JSON Schema 产生结果。它只能看到：

- 冻结的候选快照
- 当前变更的 spec 与事实 ledger
- 已批准的契约、规则和参考资料
- 当前构建、测试、截图与交互证据
- 已绑定的候选、契约和证据摘要

bundle 不包含 main agent 的实现对话、自我评价、旧 reviewer 对话或旧候选结果。reviewer 只报告规则冲突与证据缺口，不提供修改方案，也不能临时新增规则。

## iOS 与 SwiftUI 规则

首版固化了以下平台边界：

- 新增 UI 表达前，先搜索并复用项目已有设计系统。
- 保留原生导航栏、返回可访问性和 interactive pop。
- 将 pre-iOS-26 兼容逻辑集中在共享 appearance 层。
- 通过 availability 边界保留 iOS 26 及以后原生 Liquid Glass 行为。
- 使用项目自己的语义颜色、本地化与明暗模式策略。
- 导航变更必须同时提供最低支持的 pre-iOS-26 runtime 与 iOS 26+ 证据。
- 交互结论必须来自已登记的 XCUITest 场景和导出的 `.xcresult` 附件。

## 开发与验证

运行标准库测试：

```bash
python3 plugins/project-governor/scripts/governor.py eval
```

仓库当前包含：

- 摘要、未跟踪文件、受保护状态、规则路由、退出码和 gate 真值表的单元测试
- 使用 fake Codex 覆盖 reviewer 隔离、Schema、非法 JSON、额外字段、进程失败与超时的集成测试
- 包含合规、架构违规、UI 违规、证据缺失及 holdout 案例的规则评测集
- 最小 SwiftUI App 与 UI test target，覆盖原生导航、边缘返回、滚动、sheet、中英文、亮色与暗色模式

fixture 已在 iOS 17.0 和 iOS 26.5 验证通过，并从两个 result bundle 中成功导出截图附件。

## 仓库结构

```text
.agents/plugins/marketplace.json
plugins/project-governor/
├── .codex-plugin/plugin.json
├── skills/
├── scripts/
├── rules/
├── schemas/
└── evals/
```

插件不包含 MCP server、托管服务、外部数据库或 SaaS 依赖。

## 公开仓库规范

本仓库按 [Apache License 2.0](LICENSE) 为公开协作做好准备。发布任何版本前，先运行：

```bash
python3 scripts/public_release_audit.py --root .
python3 -m unittest discover -s tests -v
python3 plugins/project-governor/scripts/governor.py eval
```

自动审计会检查当前候选树中的社区文件、常见凭据材料、个人绝对路径、生成物、Python 文件级结构化注释、JSON 有效性、GitHub Actions 权限和公开插件元数据。它不能替代[公开发布规范](docs/PUBLIC_RELEASE.md)要求的完整历史、所有权与 GitHub 远端设置审查。

修改仓库可见性前，还需运行 `python3 scripts/public_release_audit.py --root . --history`。非 noreply 的提交邮箱必须由作者明确确认；使用确认参数前请先阅读公开发布规范。

项目政策：

- [安全问题报告](SECURITY.md)
- [隐私与本地数据处理](PRIVACY.md)
- [贡献指南](CONTRIBUTING.md)
- [行为准则](CODE_OF_CONDUCT.md)
- [支持范围](SUPPORT.md)
- [变更记录](CHANGELOG.md)

## 当前边界

- `0.1.0` 只支持 iOS 与 SwiftUI
- 定位是本地质量门，不是合并保护或安全沙箱
- 不提供云端证据存储或 CI 凭据管理
- 暂未提供公共 marketplace 发布流程
- 评审质量仍受已批准契约、可用证据和启用规则包的边界约束
