# 🧠 一、系统目标（Claude Code Level）

这个系统不再是“问答+写代码工具”，而是：

> ✔ 可以理解一个软件需求
> ✔ 自动拆解任务
> ✔ 在本地仓库中修改代码
> ✔ 执行编译 / 测试
> ✔ 自动修复错误
> ✔ 多轮自我迭代
> ✔ 可回滚 / 可审计 / 可观察

---

# 🏗️ 二、整体架构（升级版）

```text
                    ┌────────────────────────────┐
                    │        CLI / UI Layer       │
                    │  (Go CLI / Web / VSCode)    │
                    └────────────┬───────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────┐
│                    Agent Orchestrator                  │
│          (核心调度器 / 多 Agent 控制中心)             │
└───────────────────────┬────────────────────────────────┘
                        │
     ┌──────────────────┼──────────────────┐
     ▼                  ▼                  ▼
┌──────────┐   ┌────────────────┐   ┌──────────────┐
│ Planner  │   │ Code Agent     │   │ Review Agent │
│(任务拆解)│   │(写代码/修改)   │   │(代码审查)    │
└──────────┘   └────────────────┘   └──────────────┘
                        │
                        ▼
         ┌──────────────────────────────┐
         │      Tool Execution Layer    │
         │  fs / git / shell / test     │
         └────────────┬─────────────────┘
                      ▼
         ┌──────────────────────────────┐
         │      Sandbox Runtime         │
         │   Docker / Firecracker       │
         └────────────┬─────────────────┘
                      ▼
         ┌──────────────────────────────┐
         │         Codebase             │
         │ (Workspace + Git Repo)       │
         └────────────┬─────────────────┘
                      ▼
         ┌──────────────────────────────┐
         │   RAG / Memory System        │
         │ vector DB + embeddings       │
         └────────────┬─────────────────┘
                      ▼
         ┌──────────────────────────────┐
         │        LLM Layer             │
         │ GPT / DeepSeek / Claude      │
         └──────────────────────────────┘
```

---

# 🧠 三、核心升级点（和你之前版本的本质区别）

## ❌ 旧版本（你之前的）

* 单 Agent
* 无任务拆解
* 无代码理解
* 无沙箱
* 无记忆系统
* 无审查机制

---

## ✅ Claude Code 级版本

### 1️⃣ 多 Agent 架构（关键升级）

| Agent         | 职责                  |
| ------------- | ------------------- |
| Planner Agent | 拆任务（类似 PM）          |
| Code Agent    | 写代码                 |
| Debug Agent   | 修 bug               |
| Review Agent  | 审查代码                |
| Tool Agent    | 执行 shell / fs / git |

---

### 2️⃣ Sandbox 执行（非常关键）

所有代码运行：

> Docker / gVisor / Firecracker

防止：

* rm -rf /
* 恶意命令
* 死循环
* 系统破坏

---

### 3️⃣ Repo 级理解（不是文件级）

系统理解的是：

```text
整个 Git repo
├── dependencies
├── call graph
├── module structure
└── test coverage
```

---

### 4️⃣ RAG 代码记忆（核心能力）

存储：

* 历史代码
* 设计决策
* bug 修复记录
* API 使用方式

使用：

> 向量检索 + embedding + repo context injection

---

### 5️⃣ 自我修复循环（Claude Code 核心）

```text
write code → run → fail → read error → fix → retry
```

---

# 🧩 四、Go 工程结构（升级版）

```text
go-claudecode/
│
├── cmd/
│   └── cli/
│
├── core/
│   ├── orchestrator/     # Agent调度中心（核心）
│   ├── planner/          # 任务拆解
│   ├── coder/            # 代码生成
│   ├── reviewer/         # 代码审查
│   ├── debugger/         # 自动修复
│   ├── tools/            # 工具系统
│   ├── sandbox/          # Docker执行层
│   ├── rag/              # 向量记忆
│   ├── llm/              # 模型接口
│   └── memory/           # session memory
│
├── internal/
│   ├── git/
│   ├── fs/
│   ├── exec/
│   └── logger/
│
├── runtime/
│   ├── workspace/        # 用户代码运行区
│   └── sandbox/          # docker runtime
│
├── config/
└── prompts/
```

---

# ⚙️ 五、核心 Orchestrator（系统大脑）

```go id="or7x9a"
type Orchestrator struct {
    planner   *PlannerAgent
    coder     *CodeAgent
    reviewer  *ReviewAgent
    debugger  *DebugAgent
    tools     *ToolRegistry
    sandbox   *Sandbox
    rag       *RAGStore
}
```

---

## 主循环（Claude Code 核心逻辑）

```go id="p9zq3k"
func (o *Orchestrator) Run(task string) {

    plan := o.planner.Decompose(task)

    for _, step := range plan.Steps {

        code := o.coder.Generate(step)

        filePath := o.tools.WriteFile(code)

        result := o.sandbox.Run(filePath)

        if result.Error != nil {

            fix := o.debugger.Fix(result.Error, code)

            o.tools.ApplyPatch(fix)

            continue
        }

        review := o.reviewer.Check(code)

        if review.RiskLevel > 7 {
            continue
        }
    }
}
```

---

# 🧠 六、Planner（任务拆解 Agent）

```text id="k3p1aa"
输入：
“做一个 HTTP server + login + JWT”

输出：
1. 创建项目结构
2. 实现 server
3. 实现 auth
4. 加入 middleware
5. 写 test
```

---

# 🧪 七、Sandbox（关键生产能力）

```go id="s8d1qw"
func (s *Sandbox) Run(file string) Result {
    cmd := exec.Command(
        "docker",
        "run",
        "--rm",
        "-v", "/workspace:/app",
        "golang:1.22",
        "go", "run", file,
    )

    out, err := cmd.CombinedOutput()

    return Result{
        Output: string(out),
        Error: err,
    }
}
```

---

# 🧠 八、RAG（代码记忆系统）

### 存储内容：

* 代码片段
* 错误日志
* 修复历史
* API 使用方式

### 向量检索：

```text
query → embedding → vector DB → top-k code context
```

---

# 🔁 九、自我修复机制（Claude Code 精髓）

```text
1. 写代码
2. 运行
3. 报错
4. 读取 stacktrace
5. LLM 修复
6. patch code
7. retry
```

---

# 🧪 十、Review Agent（防“AI 写垃圾代码”）

负责：

* 安全性检查
* 性能问题
* Go idiom correctness
* 是否重复逻辑
* 是否破坏架构

---

# 🧰 十一、Tool System（统一工具层）

```go id="m1q8df"
type Tool interface {
    Name() string
    Execute(input string) (string, error)
}
```

工具包括：

* fs.write
* fs.read
* git.diff
* git.commit
* shell.run
* test.run
* docker.run

---

# 📊 十二、观测系统（工业级必备）

### 记录：

* 每一步 LLM 输出
* 每次工具调用
* 每次代码变更 diff
* 每次错误与修复

👉 用于：

* debugging
* prompt tuning
* agent performance eval

---

# 🚀 十三、运行方式（最终形态）

```bash
go run cmd/cli/main.go
```

输入：

```text
帮我做一个 JWT 登录系统
```

系统会自动：

1. 拆任务
2. 建项目结构
3. 写代码
4. 跑 docker test
5. 修 bug
6. 输出完成项目

---

# 🧠 十四、这个架构的本质（很重要）

你这个系统本质已经不是 CLI tool，而是：

> 🧠 “AI Software Engineering Runtime”

它具备：

* 类工程师能力
* 类 CI/CD 系统能力
* 类 IDE 能力
* 类自动化测试系统能力



 
