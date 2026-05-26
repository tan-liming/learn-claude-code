# Learn Claude Code — 深入学习与发现报告

## 一、项目概述

**Learn Claude Code** 是一个教育性开源仓库，系统性地教授如何构建 AI Agent 的 **Harness（框架层）**。它的核心理念是：

> **"The model IS the agent, the code IS the harness."**  
> 模型本身就是智能体，代码只是承载它的框架。

项目通过 12 个渐进式会话（s01–s12），从零开始构建一个越来越强大的 Agent 框架。每个会话引入一个独立的机制，最终在 `s_full.py` 中整合所有能力。

## 二、核心哲学：Harness 架构

### Harness 是什么？

传统 Agent 开发容易陷入"编排陷阱"——试图用代码规定模型的每一步行为。这个项目展示了另一种思路：**Harness 层只做连接，不做决策**。

```
+--------+      +-------+      +---------+
|  User  | ---> |  LLM  | ---> |  Tools  |
| prompt |      |       |      | execute |
+--------+      +---+---+      +----+----+
                    ^                |
                    |   tool_result  |
                    +----------------+
                    (loop until stop_reason != "tool_use")
```

这个不到 30 行的 `while` 循环就是整个 Agent 的核心骨架。后面 11 个章节的复杂机制全都在这个循环上叠加——**循环本身始终不变**。

### 关键洞察

每个会话文件都是独立可运行的，不互相导入。每节课引入**一种**新机制，文档和代码一一对应。这种设计让学习者可以单独运行和理解每个概念，而不需要理解整个系统。

## 三、12 个渐进式会话详解

### s01: The Agent Loop（智能体循环）

**核心模式**：`while stop_reason == "tool_use"`

这是整个项目的基石。代码不到 30 行：

1. 用户消息追加到 `messages[]`
2. 调用 LLM，传入 `messages + tools`
3. 追加 assistant 响应
4. 检查 `stop_reason`——不是 `"tool_use"` 就结束
5. 否则执行每个工具调用，收集结果
6. 结果作为 `tool_result` 追加回 `messages[]`
7. 回到步骤 2

**只有一个工具**：`bash`。包含基础安全防护（危险命令过滤）。

### s02: Tool Use（工具使用）

**核心洞察**："加工具不需要改循环。"

引入**工具分发机制**——`TOOL_HANDLERS` 字典：

```python
TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
}
```

**关键设计**：
- `safe_path()` 路径沙箱——防止文件操作逃逸工作区
- 每个工具是独立函数，通过 lambda 适配到统一接口
- 未知工具返回错误信息而非崩溃

### s03: TodoWrite（待办写入）

**问题**：多步任务中模型丢失进度，重复做、跳步、跑偏。

**解决方案**：`TodoManager` + nag reminder 机制。

- `TodoManager` 强制"同一时间只能有一个 `in_progress`"，迫使模型顺序聚焦
- **Nag Reminder**：连续 3 轮未调用 `todo` 工具时，在 `tool_result` 前注入 `<reminder>Update your todos.</reminder>`
- 利用模型的"责任压力"——系统提醒制造问责，模型会自觉更新计划

### s04: Subagents（子智能体）

**问题**：Agent 工作越久，`messages[]` 越胖，执行效率下降。

**解决方案**：子智能体用**独立的消息上下文**运行：

```
Parent agent                     Subagent
+------------------+             +------------------+
| messages=[...]   |             | messages=[]      |  <-- fresh!
| tool: task       | ----------> | while tool_use:  |
|   prompt="..."   |             |   call tools     |
|   result = "..." | <---------- | return last text |
+------------------+             +------------------+
```

- 子智能体可能跑 30+ 次工具调用，但整个消息历史直接丢弃
- 父智能体只收到一段摘要文本
- 子智能体没有 `task` 工具（防止递归生成）

### s05: Skills（技能加载）

**问题**：所有领域知识全塞进系统提示太浪费 token（10 个技能 × 2000 token = 20,000 token）。

**解决方案**：两层注入策略：

- **第一层（廉价）**：系统提示中只放技能名称列表（~100 token/个）
- **第二层（按需）**：模型调用 `load_skill("name")` 时，完整内容通过 `tool_result` 注入

技能文件结构：
```
skills/
  pdf/SKILL.md          # YAML frontmatter + Markdown body
  code-review/SKILL.md
  agent-builder/SKILL.md
```

`SkillLoader` 递归扫描 `SKILL.md` 文件，解析 YAML frontmatter（name, description, tags）和正文。

### s06: Context Compact（上下文压缩）

**问题**：上下文窗口有限，不压缩智能体无法在大项目中工作。

**解决方案**：三层压缩策略，激进程度递增：

| 层级 | 名称 | 触发条件 | 操作 |
|------|------|----------|------|
| Layer 1 | `micro_compact` | 每次 LLM 调用前 | 将超过 3 轮前的 tool_result 替换为 `[Previous: used {tool_name}]` |
| Layer 2 | `auto_compact` | token > 50,000 阈值 | 存完整 transcript，LLM 生成摘要，替换整个 messages |
| Layer 3 | `compact` 工具 | 手动调用 | 与 auto_compact 相同，手动触发 |

- 完整历史保存到 `.transcripts/` 目录，信息没有真正丢失
- 摘要后会写 `[Compressed]` 标记
- token 估算使用简单方法：`len(str(messages)) // 4`

### s07: Task System（任务系统）

**问题**：s03 的 TodoManager 只是内存中的扁平清单，没有依赖和持久化。

**解决方案**：磁盘持久化的**任务图（DAG）**：

```
.tasks/
  task_1.json  {"id":1, "status":"completed", "blockedBy":[], ...}
  task_2.json  {"id":2, "blockedBy":[1], "status":"pending", ...}
```

- 每个任务一个 JSON 文件，状态 `pending → in_progress → completed`
- `blockedBy` + `blocks` 构建双向依赖边
- 完成任务时自动从所有其他任务的 `blockedBy` 中移除
- 定义三个核心查询：什么可做（pending + blockedBy 为空）/ 什么被卡住 / 什么完成了
- 任务图是 s07 之后所有机制的协调骨架

### s08: Background Tasks（后台任务）

**问题**：`npm install`、`pytest`、`docker build` 需要数分钟，阻塞式循环下模型只能干等。

**解决方案**：后台线程执行 + 通知队列：

- `BackgroundManager.run()` 启动守护线程，立即返回 task_id
- 子进程用 `threading.Thread` + `subprocess.run` 执行
- 完成后结果进入线程安全的通知队列
- 每次 LLM 调用前排空队列，以 `<background-results>` 形式注入结果
- 主循环保持单线程，只有子进程 I/O 被并行化

### s09: Agent Teams（智能体团队）

**问题**：子智能体（s04）是一次性的、没有身份、没有跨调用记忆；后台任务（s08）能做 shell 但不能做 LLM 引导的决策。

**解决方案**：持久化队友 + JSONL 邮箱通信：

```
.team/config.json        # 团队名册 + 状态
.team/inbox/
  alice.jsonl            # 追加写入，读取后清空
  bob.jsonl
  lead.jsonl
```

- 每个队友在独立线程中运行完整的 agent loop
- `MessageBus`：`send()` 追加一行 JSON 到目标邮箱；`read_inbox()` 读取全部并清空（drain）
- 5 种消息类型：`message`、`broadcast`、`shutdown_request`、`shutdown_response`、`plan_approval_response`
- 每次 LLM 调用前队友检查收件箱，将消息注入上下文
- REPL 支持 `/team` 和 `/inbox` 命令

### s10: Team Protocols（团队协议）

**问题**：s09 中队友缺少结构化协调——关机直接杀线程，高风险变更没有审批流程。

**解决方案**：基于 `request_id` 的请求-响应模式：

**关机协议：**
```
Lead --[shutdown_req, request_id=abc]--> Teammate
Lead <--[shutdown_resp, request_id=abc, approve=true]-- Teammate
```

**计划审批协议：**
```
Teammate --[plan_approval, plan="..."]--> Lead (审查)
Teammate <--[plan_approval_response, approve=true/reject]-- Lead
```

两者共享同一个有限状态机：`pending → approved | rejected`

### s11: Autonomous Agents（自治智能体）

**问题**：s09-s10 中队友只在被明确指派时才动，扩展不了。

**解决方案**：自组织生命周期——WORK → IDLE → SHUTDOWN：

```
WORK PHASE: 标准 agent loop
IDLE PHASE: 每 5 秒轮询一次（最长 60 秒）
   ├── 检查收件箱 → 有消息 → 回到 WORK
   ├── 扫描 .tasks/ 任务看板 → 有未认领 → claim → 回到 WORK
   └── 60 秒超时 → SHUTDOWN
```

**身份重注入**：上下文压缩后模型可能忘了自己是谁。当 `len(messages) <= 3` 时，在消息开头插入身份块：
```python
<identity>You are 'coder', role: backend, team: my-team</identity>
```

**任务认领**：
- 找 `pending` 状态、无 `owner`、`blockedBy` 为空的任务
- 认领时写入 owner + 改为 `in_progress`
- `_claim_lock` 防止竞态

### s12: Worktree + Task Isolation（工作树任务隔离）

**问题**：所有任务共享一个目录，并行修改互相污染。

**解决方案**：每个任务一个独立的 git worktree 目录：

```
Control plane (.tasks/)       Execution plane (.worktrees/)
task_1.json (status=in_progress, worktree="auth-refactor")  ↔  auth-refactor/ (branch: wt/auth-refactor, task_id=1)
task_2.json (status=pending, worktree="ui-login")           ↔  ui-login/ (branch: wt/ui-login, task_id=2)
```

**双向绑定**：创建 worktree 时绑定 task_id，自动将任务推进到 `in_progress`；删除 worktree 时可自动完成任务。

**事件流**：每个生命周期步骤写入 `.worktrees/events.jsonl`：
```json
{"event": "worktree.create.after", "ts": 1730000000, ...}
```

事件类型：`worktree.create.before/after/failed`、`worktree.remove.before/after/failed`、`worktree.keep`、`task.completed`。

**可恢复性**：崩溃后从 `.tasks/` + `.worktrees/index.json` 重建现场。

## 四、s_full.py：集大成者

`s_full.py` 整合了 s01-s11 的所有机制（s12 的工作树隔离是独立教学单元），包含：

| 会话 | 机制 | 在 s_full 中的集成 |
|------|------|-------------------|
| s01 | Agent Loop | 核心 while 循环 |
| s02 | Tool Dispatch | TOOL_HANDLERS 字典 |
| s03 | TodoWrite | TodoManager + nag reminder |
| s04 | Subagent | run_subagent() |
| s05 | Skills | SkillLoader |
| s06 | Compact | micro_compact + auto_compact + compress tool |
| s07 | Tasks | TaskManager（文件持久化） |
| s08 | Background | BackgroundManager + 通知队列 |
| s09 | Teams | MessageBus + TeammateManager |
| s10 | Protocols | shutdown_requests + plan_requests |
| s11 | Autonomy | 空闲轮询 + 任务认领 + 身份重注入 |

**REPL 命令**：`/compact`、`/tasks`、`/team`、`/inbox`

Agent Loop 中的执行前顺序：
1. `micro_compact()` 压缩旧结果
2. `auto_compact()` 检查 token 阈值
3. 排空 background 通知
4. 检查 lead 收件箱
5. LLM 调用
6. 执行工具
7. Todo nag reminder 注入
8. 手动压缩检测

## 五、Web 前端（交互式学习平台）

仓库包含一个完整的 Next.js 16 + React 19 + Tailwind 4 前端应用：

- `/web` 目录，国际化支持（中/英/日）
- `extract-content.ts` 脚本在构建前自动将文档提取为 JSON 数据
- 交互式组件：
  - **simulator**：可视化 agent loop 的逐步执行过程
  - **visualizations**：每个会话专用的可视化图表（s01 的循环图、s02 的分发图等）
  - **architecture**：架构图、设计决策、执行流程、消息流
  - **diff**：代码差异对比
  - **timeline**：12 个会话的时间线
- 每个会话都有独立的 `scenarios/` 和 `annotations/` JSON 数据

## 六、Skills 系统

5 个内置技能：

| 技能 | 用途 |
|------|------|
| `agent-builder` | 设计和构建 AI Agent，包含核心哲学、渐进复杂度指南、反模式 |
| `code-review` | 结构化代码审查（安全→正确性→性能→可维护性→测试） |
| `mcp-builder` | MCP（Model Context Protocol）服务器构建 |
| `pdf` | PDF 文件处理 |

`agent-builder` 技能最为完整，包含 `references/`（哲学、最少 Agent 代码、子智能体模式、工具模板）和 `scripts/init_agent.py`（脚手架生成器）。

## 七、环境与多提供商支持

`.env.example` 展示了 Anthropic 兼容 API 的多提供商配置：

- **Anthropic**：默认 `claude-sonnet-4-6`（SWE-bench 79.6%）
- **MiniMax**：`MiniMax-M2.5`（SWE-bench 80.2%）
- **GLM (Zhipu)**：`glm-5`
- **Kimi (Moonshot)**：`kimi-k2.5`
- **DeepSeek**：`deepseek-chat`（V3.2）

支持国内外不同地区的端点 URL，使用 `ANTHROPIC_BASE_URL` + `ANTHROPIC_API_KEY` 的标准 API 模式。

`ANTHROPIC_AUTH_TOKEN` 环境变量在使用非 Anthropic 提供商时会被清除，避免认证冲突。

## 八、架构模式总结

### 渐进式复杂度设计
```
s01  核心循环       ─┐
s02  工具分发         │ 基础层（必须）
s03  任务规划        ─┘
s04  子智能体       ─┐
s05  技能加载         │ 增强层（按需）
s06  上下文压缩      ─┘
─────────────────────────────────
s07  持久任务       ─┐
s08  后台执行         │ 协作层
s09  团队通信         │
s10  团队协议         │
s11  自治能力        ─┘
s12  隔离执行        ── 隔离层
```

### 核心设计原则

1. **循环不变性**：从 s01 到 s12，核心的 `while stop_reason == "tool_use"` 循环从未改变
2. **工具即插件**：新能力 = 新 handler + 新 schema，循环和分发机制不变
3. **文件即状态**：任务（`.tasks/`）、团队（`.team/`）、工作树（`.worktrees/`）都通过文件系统持久化
4. **上下文隔离**：子智能体用独立 messages[]、worktree 用独立目录、后台任务用独立线程
5. **模型主导**：Harness 不规定模型的行为路径，只提供能力和约束
6. **按需加载**：知识（skills）、历史压缩（compact）都是按需触发，避免浪费

### Harness 各层的职责

| 层 | 职责 | 对应会话 |
|----|------|----------|
| 循环层 | 连接模型与工具 | s01 |
| 工具层 | 扩展模型触达边界 | s02 |
| 规划层 | 保持模型不偏航 | s03, s07 |
| 隔离层 | 保护模型上下文 | s04, s12 |
| 知识层 | 按需领域专长 | s05 |
| 压缩层 | 无限会话能力 | s06 |
| 并行层 | 非阻塞执行 | s08 |
| 协作层 | 多模型协调 | s09, s10, s11 |

### 有趣的实现细节

1. **Nag Reminder**（s03）利用模型对系统提示的敏感性——不强制更新，但注入 `<reminder>` 制造"责任压力"
2. **Micro Compact**（s06）通过 `tool_use_id` 反向查找 `tool_name`，在占位符中保留"曾用过什么工具"的语义信息
3. **身份重注入**（s11）通过判断 `len(messages) <= 3` 来推测是否发生过压缩——简洁而有效的启发式
4. **双向依赖绑定**（s07）的 `update` 在添加 `blocks` 时自动更新被阻塞任务的 `blockedBy`，保持图一致性
5. **Worktree 删除即任务完成**（s12）——一个 `worktree_remove(name, complete_task=True)` 调用完成清理、解绑、完成、事件四个操作
6. **CLAUDE.md** 本身也是系统提示的一部分——它告诉 AI 如何处理这个仓库（"The model IS the agent, the code IS the harness"）

## 九、总结

Learn Claude Code 不仅是一个代码仓库，更是一套完整的 Agent 框架设计哲学。它用 12 个逐步复杂的会话，系统地展示了从最简单的循环到完整的自治多 Agent 团队所需的所有机制。每个机制都是独立的、可组合的、渐进复杂的。

**最大的教学价值**在于它清晰地划分了"模型应该做什么"和"框架应该做什么"的边界——模型负责推理和决策，框架负责提供连接、约束和持久化。这种分离让 Agent 系统既强大又可控。
