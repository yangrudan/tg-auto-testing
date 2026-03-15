# crew-tg-tester User Manual

Telegram Bot 自动化功能测试工具 — 以真实用户身份向 crew-rs bot 发送消息，捕获完整响应生命周期，执行断言，生成测试报告。

---

## 目录

1. [前置条件](#1-前置条件)
2. [安装](#2-安装)
3. [配置](#3-配置)
4. [快速验证：hello.py](#4-快速验证hellopy)
5. [运行测试场景：tester.py](#5-运行测试场景testerpy)
6. [YAML 场景格式](#6-yaml-场景格式)
7. [输出格式](#7-输出格式)
8. [已有场景](#8-已有场景)
9. [编写自定义场景](#9-编写自定义场景)
10. [安全注意事项](#10-安全注意事项)
11. [故障排除](#11-故障排除)

---

## 1. 前置条件

| 项目 | 说明 |
|------|------|
| Python 3.10+ | 系统已安装 |
| Telegram 账号 | 用你自己的主号 |
| Telegram API 凭据 | 从 my.telegram.org 获取（见下方） |
| crew-rs gateway | 已运行，bot 可正常对话 |

### 获取 Telegram API 凭据

1. 打开 https://my.telegram.org/auth ，输入手机号（带国家代码），用收到的验证码登录
2. 登录后点击 **API development tools**（注意：选 Telegram API，不是 Bot API 或 Gateway API）
3. 填写表单：App title（随意，如 `crew-tester`）、Short name、Platform 选 **Desktop** 或 **Other**（不影响功能）
4. 提交后页面会显示 **api_id**（数字）和 **api_hash**（字符串），记下来

> 每个手机号只能创建一个 api_id。如果之前已创建过，直接使用已有的即可。

---

## 2. 安装

```bash
cd crew-tg-tester
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> macOS 上 Homebrew 安装的 Python 不允许全局 pip install，必须使用 venv。

---

## 3. 配置

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`：

```yaml
telegram:
  api_id: 12345                  # 替换为你的 api_id
  api_hash: "abc123def456"       # 替换为你的 api_hash
  bot: "@your_bot_username"      # 替换为你的 crew-rs bot 的 @username
  session_file: "crew_tester"    # 可选，session 文件名（默认 crew_tester）
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `api_id` | 是 | 从 my.telegram.org 获取的数字 |
| `api_hash` | 是 | 从 my.telegram.org 获取的字符串 |
| `bot` | 是 | 目标 bot 的 @username（场景文件可覆盖） |
| `session_file` | 否 | Telethon session 文件名，默认 `crew_tester` |

---

## 4. 快速验证：hello.py

首次使用前，先用 `hello.py` 验证连接是否正常。

```bash
source venv/bin/activate
python3 hello.py
```

### 首次运行

会出现交互提示：

```
Please enter your phone (or bot token): +8613800138000
Please enter the code you received: 12345
```

- 输入你的手机号（带国家代码）
- Telegram 会给你发一条验证码消息（在 Telegram app 中查看）
- 输入验证码

验证成功后会生成 `crew_tester.session` 文件，**以后不再需要验证**。

### 预期输出

```
Logged in. Sending to @your_bot ...

>>> Test Hello World
  [2026-03-14T12:00:02.500Z] NEW  id=101  ✦ Thinking...
  [2026-03-14T12:00:10.500Z] EDIT id=101  ✦ Pondering... (8s · 500↑ 0↓)
  [2026-03-14T12:00:12.000Z] DEL  id=101
  [2026-03-14T12:00:12.100Z] NEW  id=102  Hello! 这是一条测试回复...
  [2026-03-14T12:00:13.100Z] EDIT id=102  Hello! 这是一条测试回复，我收到了你的消息。
  [2026-03-14T12:00:18.100Z] EDIT id=102  Hello! 这是一条测试回复，我收到了你的消息。有什么可以帮你的吗？

============================================================
Done. Captured 6 events in 23s.
============================================================

Bot final reply:
  [msg 102] Hello! 这是一条测试回复，我收到了你的消息。有什么可以帮你的吗？
```

事件类型说明：

| 事件 | 含义 |
|------|------|
| `NEW` | bot 发送了新消息 |
| `EDIT` | bot 编辑了消息（流式输出或状态更新） |
| `DEL` | bot 删除了消息（如 "Thinking..." 状态气泡） |

程序等到 bot **连续 10 秒没有新动作**后自动退出。

---

## 5. 运行测试场景：tester.py

`hello.py` 验证通过后，使用 `tester.py` 运行 YAML 定义的测试场景。

### 基本用法

```bash
# 运行单个场景
python3 tester.py scenarios/hello.yaml

# 运行目录下所有 .yaml 场景
python3 tester.py scenarios/
```

### 命令行参数

```
python3 tester.py <场景文件或目录> [-o 输出目录] [-c 配置文件]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `<场景>` | (必填) | `.yaml` 文件或包含 `.yaml` 的目录 |
| `-o <dir>` | `output/` | 输出目录 |
| `-c <file>` | `config.yaml` | 配置文件路径 |

### 运行过程

tester.py 对每个场景：

1. 按顺序执行 `steps` 中的每一步
2. 每步：发送消息/文件 → 等待 bot 回复稳定 → 执行断言
3. 实时在终端打印事件流和每步结果
4. 结束后生成 `timeline.jsonl` 和 `report.md`

终端输出示例：

```
Running scenario: Session Management
Bot: @crew_bot  |  Steps: 23
============================================================

>>> /new
  [2026-03-14T21:30:01.000Z] NEW  id=200  Session cleared.
  [N-01] ✅ PASS

>>> 我之前问了什么？
  [2026-03-14T21:30:07.500Z] NEW  id=201  ✦ Thinking...
  [2026-03-14T21:30:09.000Z] DEL  id=201
  [2026-03-14T21:30:09.100Z] NEW  id=202  I don't have any previous...
  [N-02] ✅ PASS

>>> /new a#b
  [2026-03-14T21:32:00.000Z] NEW  id=210  Invalid session name...
  [N-16] ✅ PASS

============================================================
Scenario: Session Management
Results:  21 PASS / 1 FAIL / 1 TIMEOUT / 23 total
============================================================
  Timeline: output/2026-03-14T21-30-00_Session_Management/timeline.jsonl
  Report:   output/2026-03-14T21-30-00_Session_Management/report.md
```

### Settle Detection（等待策略）

tester.py 不使用固定等待时间。发送消息后启动一个滑动窗口计时器：

- 每收到 bot 的事件（NEW/EDIT/DEL），计时器归零
- 连续 `settle_timeout` 秒无事件 → 判定回复完成，进入下一步
- 超过 `max_wait` 秒 → 强制进入下一步，标记 TIMEOUT

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `settle_timeout` | 5 秒 | crew-rs 流式编辑间隔为 1 秒，5 秒无事件可确信输出完成 |
| `max_wait` | 120 秒 | 与 crew-rs session_actor 默认超时一致 |

---

## 6. YAML 场景格式

### 基本结构

```yaml
name: "场景名称"               # 用于报告标题
bot: "@bot_username"           # 可选，覆盖 config.yaml 中的 bot

defaults:                      # 全局默认值（每步可覆盖）
  settle_timeout: 5
  max_wait: 60

steps:
  - send: "消息文本"
    tag: "STEP-01"
    # ... 更多字段见下方
```

### Step 字段一览

#### 发送动作

| 字段 | 类型 | 说明 |
|------|------|------|
| `send` | string | 发送文本消息。如果同时有 `send_file`，则作为文件的 caption |
| `send_file` | string | 发送文件，路径相对于场景文件所在目录 |

每步至少要有 `send` 或 `send_file` 其中之一，否则跳过 settle 等待。

#### 等待控制

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `settle_timeout` | number | 5 | 覆盖本步的 settle 超时 |
| `max_wait` | number | 120 | 覆盖本步的最大等待时间 |

#### 断言

| 字段 | 类型 | 说明 |
|------|------|------|
| `expect_contains` | string | bot 最终回复必须包含此子串，否则 FAIL |
| `expect_not_contains` | string | bot 最终回复不能包含此子串，否则 FAIL |
| `tag` | string | 步骤标签（如 `"N-01"`），出现在报告中 |

"最终回复"= 本步期间 bot 发送的所有未被删除的消息，取各消息最后编辑版本，拼接而成。"Thinking..." 等被删除的状态气泡不计入。

#### 条件分支

```yaml
- send: "问一个问题"
  on_response:
    - contains: "预期回答A"
      steps:
        - send: "继续A路线"
          tag: "BRANCH-A"
    - contains: "预期回答B"
      steps:
        - send: "继续B路线"
          tag: "BRANCH-B"
    - default:
        steps:
          - tag: "BRANCH-FAIL"
```

匹配规则：从上到下，**第一个命中的 `contains`** 执行其 `steps`，不再继续。都不命中则执行 `default`。无 `default` 则跳过。

---

## 7. 输出格式

每次运行在 `output/` 下生成带时间戳的目录：

```
output/2026-03-14T21-30-00_Session_Management/
├── timeline.jsonl    # 完整事件时间线（机器可读）
└── report.md         # 测试报告（人类可读）
```

### timeline.jsonl

每行一个 JSON 对象，三种 `dir`：

```jsonl
{"ts":"...","dir":"out","type":"send","text":"/new","step":0,"tag":"N-01"}
{"ts":"...","dir":"in","type":"new","msg_id":200,"text":"Session cleared."}
{"ts":"...","dir":"sys","type":"result","step":0,"tag":"N-01","result":"PASS","detail":null}
```

| dir | 含义 |
|-----|------|
| `out` | 我们发出的消息 |
| `in` | bot 的事件（new/edit/delete） |
| `sys` | 系统判定（result: PASS/FAIL/TIMEOUT/SKIP） |

### report.md

Markdown 格式的测试报告，包含汇总表和逐步详情：

```markdown
# Test Report: Session Management
- Date: 2026-03-14 21:30
- Bot: @crew_bot
- Scenario: scenarios/new_session.yaml

## Summary
| Total | PASS | FAIL | TIMEOUT | SKIP |
|-------|------|------|---------|------|
| 23    | 21   | 1    | 1       | 0    |

## Details
| # | Tag  | Sent    | Expected | Reply (truncated) | Result |
|---|------|---------|----------|-------------------|--------|
| 0 | N-01 | /new    |          | Session cleared.  | PASS   |
| 1 | N-02 | 我之前...  |          | I don't have...   | PASS   |
```

---

## 8. 已有场景

| 文件 | 测试用例 | 覆盖内容 |
|------|---------|----------|
| `scenarios/hello.yaml` | 1 | 最简测试，发一句 Hello |
| `scenarios/00_env_probe.yaml` | E-01~E-04 (4) | 系统可用性探测：adaptive/queue/sessions 状态 |
| `scenarios/01_adaptive.yaml` | A-01~A-21 (21) | /adaptive 命令解析、模式切换、QoS、行为验证、一致性 |
| `scenarios/02_new_session.yaml` | N-01~N-23 (23) | /new、/s、/sessions、/back、/delete、输入验证、中文名称 |
| `scenarios/03_queue.yaml` | Q-01~Q-20 (20) | /queue 命令解析、各模式行为（followup/collect/steer/interrupt/spec）、排斥性 |
| `scenarios/04_cross_feature.yaml` | X-01~X-05 (5) | adaptive+queue 联动、speculative 下命令不冲突、会话隔离 |

共 **73 个测试用例** + 1 个 hello 验证。

运行全部场景：

```bash
python3 tester.py scenarios/
```

---

## 9. 编写自定义场景

### 示例：测试文件处理

```yaml
name: "File Handling"

defaults:
  settle_timeout: 10
  max_wait: 180

steps:
  - send: "/new"
    tag: "SETUP"

  - send_file: "./test_files/sample.pdf"
    send: "帮我总结这个文件的内容"
    tag: "FILE-01"
    max_wait: 300
    on_response:
      - contains: "总结"
        steps:
          - tag: "FILE-01:PASS"
      - default:
          steps:
            - tag: "FILE-01:FAIL"
```

### 要点

- 文件路径（`send_file`）相对于场景文件所在目录
- 长时间任务（如文件处理）建议增大 `max_wait`
- 使用 `tag` 给每步编号，方便在报告中定位
- AI 回复不确定时，用 `on_response` 分支处理不同情况

---

## 10. 安全注意事项

| 项目 | 说明 |
|------|------|
| `*.session` 文件 | 等同于账号完整访问权限，**不要分享或上传** |
| `config.yaml` | 包含 api_hash，已加入 .gitignore |
| Telegram 风控 | settle 等待自然形成 5+ 秒间隔，低频操作不会触发风控 |
| FloodWaitError | 程序自动捕获并等待指定秒数后重试 |
| 测试数据 | `test_files/` 中不放敏感文件，`output/` 已加入 .gitignore |

---

## 11. 故障排除

| 问题 | 解决 |
|------|------|
| `ModuleNotFoundError: No module named 'telethon'` | 确认已激活 venv：`source venv/bin/activate`，然后 `pip install -r requirements.txt` |
| `error: externally-managed-environment` | 必须使用 venv，见[安装](#2-安装) |
| `FileNotFoundError: config.yaml` | 运行 `cp config.example.yaml config.yaml` 并编辑 |
| `ValueError: Your API ID or Hash are invalid` | 检查 config.yaml 中的 api_id 和 api_hash |
| 验证码收不到 | 检查 Telegram app 的 "Saved Messages" 或 SMS |
| `Bot username not found` | 确认 bot 的 @username 拼写正确，且 bot 在线 |
| 所有步骤 TIMEOUT | 确认 crew-rs gateway 正在运行且 bot 可正常对话 |
| `FloodWaitError` | 程序会自动等待。如频繁出现，说明操作太快，增大 settle_timeout |
