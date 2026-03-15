# crew-tg-tester 设计文档

Telegram Bot 自动化功能测试工具

---

## 1. 定位与目标

### 要解决的问题

crew-rs gateway 连接 Telegram 后，bot 的行为需要系统性验证：
- 多轮对话上下文是否正确保持
- 文件上传/下载是否正常工作
- 斜杠命令（`/adaptive`、`/new`、`/queue` 等）是否返回预期结果
- 流式输出、状态气泡（`✦ Thinking...`）、消息编辑等过程行为是否正常

目前只能通过人工在 Telegram 客户端逐条发消息验证，效率低且不可重复。

### 工具目标

一个 **Python 命令行工具**，能够：
1. 读取 YAML 测试场景文件
2. 以真实 Telegram 用户身份向 bot 发送消息和文件
3. 捕获 bot 的完整响应生命周期（发送、编辑、删除）
4. 按时间线记录所有交互
5. 执行简单断言（包含/不包含关键词）
6. 输出结构化测试报告

### 不做什么（V1 范围）

- 不做 CI/CD 集成（需要 Telegram session，不适合无人环境）
- 不做 AI 驱动的响应质量评判
- 不做并发多场景执行
- 不做 Telegram inline keyboard 按钮点击模拟

---

## 2. 技术选型

### 核心依赖：Telethon (Python)

| 考虑项 | 结论 |
|--------|------|
| **为什么不能 bot-to-bot？** | Telegram 平台禁止 bot 看到其他 bot 的消息，必须用真实用户账号 |
| **为什么选 Telethon？** | 8+ 年成熟度，文件收发一行代码，事件系统完整覆盖 NewMessage/Edited/Deleted |
| **为什么不选 grammers (Rust)？** | pre-1.0，文件 API 不稳定，文档少。未来可迁移 |
| **为什么不选 TDLib？** | 需要编译 C++，对测试工具来说太重 |
| **合法性？** | Telegram API TOS 允许第三方客户端。用自己的账号、低频操作、不群发，风险极低 |

### 依赖清单

```
telethon>=1.36
pyyaml>=6.0
```

### 前置条件

| 项目 | 获取方式 |
|------|----------|
| Telegram API ID + Hash | [my.telegram.org](https://my.telegram.org) 注册获取 |
| Telegram 账号 | 使用自己的主号即可 |
| Bot username | 你的 crew-rs bot 的 Telegram @username |
| Python 3.10+ | 系统已安装 |

---

## 3. YAML 场景格式规范

### 完整 Schema

```yaml
# 场景元信息
name: "场景名称"             # 必填，用于报告标题
bot: "@your_bot_username"    # 必填，目标 bot

# 全局默认值（每个 step 可覆盖）
defaults:
  settle_timeout: 5          # 秒，bot 回复稳定判定时间
  max_wait: 120              # 秒，单步最大等待时间

# 测试步骤
steps:
  - send: "消息文本"         # 发送文本
  - send_file: "./path"      # 发送文件（可选搭配 send 作为 caption）
  - expect_contains: "关键词"  # 断言：最终回复包含
  - expect_not_contains: "X"   # 断言：最终回复不包含
  - settle_timeout: 10         # 覆盖本步等待时间
  - max_wait: 300              # 覆盖本步最大等待
  - tag: "N-01"                # 步骤标签，用于报告
  - on_response:               # 条件分支
      - contains: "关键词"
        steps: [...]
      - default:
          steps: [...]
```

### 字段说明

#### 发送动作

| 字段 | 类型 | 说明 |
|------|------|------|
| `send` | string | 发送文本消息。如果同时有 `send_file`，则作为文件的 caption |
| `send_file` | string | 发送文件，路径相对于场景文件所在目录 |

每个 step 至少要有 `send` 或 `send_file` 其中之一（除非是纯断言步骤）。

#### 等待控制

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `settle_timeout` | number | 5 | bot 回复"稳定"的判定时间（秒）。从最后一次 NewMessage/MessageEdited 事件起计算，超过此时间无新事件则认为 bot 说完了 |
| `max_wait` | number | 120 | 单步最大等待时间（秒）。超时后强制进入下一步，标记为 TIMEOUT |

#### 断言

| 字段 | 类型 | 说明 |
|------|------|------|
| `expect_contains` | string | bot 最终回复文本必须包含此子串，否则标记 FAIL |
| `expect_not_contains` | string | bot 最终回复文本不能包含此子串，否则标记 FAIL |
| `tag` | string | 步骤标签，映射到测试计划编号（如 `"N-01"`），出现在报告中 |

#### 条件分支

```yaml
on_response:
  - contains: "匹配文本"
    steps:
      - send: "分支A的操作"
  - contains: "另一个匹配"
    steps:
      - send: "分支B的操作"
  - default:
      steps:
        - send: "兜底操作"
        - tag: "FAIL:未匹配预期"
```

匹配规则：从上到下，**第一个命中的 `contains` 执行其 `steps`**，不再继续。如果都不命中，执行 `default`。无 `default` 则跳过。

### 场景示例

```yaml
name: "会话管理基础测试"
bot: "@crew_test_bot"

defaults:
  settle_timeout: 5
  max_wait: 60

steps:
  # 清除历史
  - send: "/new"
    expect_contains: "Session cleared"
    tag: "N-01"

  # 验证清除生效
  - send: "我之前问了什么？"
    expect_not_contains: "苹果"
    tag: "N-02"

  # 创建 research 会话
  - send: "/new research"
    expect_contains: "Switched to session: research"
    tag: "N-03"

  # 在 research 中种下记忆
  - send: "记住关键词：苹果"
    tag: "N-04"

  # 切到 coding，验证隔离
  - send: "/new coding"
    expect_contains: "Switched to session: coding"
    tag: "N-05"

  - send: "我之前说的关键词是什么？"
    expect_not_contains: "苹果"
    tag: "N-06"

  # 切回 research，验证上下文恢复
  - send: "/s research"
    expect_contains: "Switched to session: research"
    tag: "N-07"

  - send: "我之前说的关键词是什么？"
    on_response:
      - contains: "苹果"
        steps:
          - tag: "N-08:PASS"
      - default:
          steps:
            - tag: "N-08:FAIL 上下文丢失"

  # 文件测试
  - send_file: "./test_files/sample.pdf"
    send: "帮我总结这个文件的内容"
    max_wait: 180
    tag: "FILE-01"

  # 非法名称
  - send: "/new a#b"
    expect_contains: "Invalid session name"
    tag: "N-16"

  # 清理
  - send: "/delete research"
  - send: "/delete coding"
  - send: "/s"
```

---

## 4. 消息捕获机制

### crew-rs bot 的消息生命周期

```
用户发送消息
    │
    ├─ [0s]   Telegram typing indicator ("正在输入...")
    ├─ [2s]   NewMessage: "✦ Thinking..."          ← status bubble
    ├─ [10s]  MessageEdited: "✦ Pondering... (8s)"  ← status 更新
    ├─ [12s]  MessageDeleted: id=100                ← status 删除
    ├─ [12s]  NewMessage: "根据你的问题..."          ← 流式回复开始
    ├─ [13s]  MessageEdited: "根据你的问题，我认为..." ← 流式累积
    ├─ [14s]  MessageEdited: "...⚙ `web_search`..." ← 工具执行
    ├─ [20s]  MessageEdited: "...✓ `web_search`..." ← 工具完成
    ├─ [25s]  MessageEdited: "(最终完整回复)"         ← 最终内容
    └─ [settle_timeout 后] → 进入下一步
```

### Telethon 事件映射

| Bot 行为 | Telegram API 事件 | Telethon handler |
|----------|-------------------|------------------|
| 发送新消息 | `UpdateNewMessage` | `events.NewMessage(from_users=bot)` |
| 编辑消息 | `UpdateEditMessage` | `events.MessageEdited(from_users=bot)` |
| 删除消息 | `UpdateDeleteMessages` | `events.MessageDeleted` |
| 正在输入 | `UpdateUserTyping` | `events.UserUpdate` (raw) |

### 捕获数据结构

每个捕获的事件记录为：

```
{
  "timestamp": "2026-03-14T12:00:01.234Z",
  "event_type": "new" | "edit" | "delete",
  "message_id": 100,
  "text": "消息内容",
  "has_media": false,
  "media_path": null
}
```

### "最终回复"的判定

一个 step 发送后，bot 可能产生多条消息和多次编辑。**最终回复**的判定规则：

1. 收集该 step 期间 bot 发送的**所有未被删除的消息**
2. 对每条消息，取**最后一次编辑后的文本**
3. 将所有消息文本按时间序拼接（`\n` 分隔）作为**最终回复文本**
4. 断言（`expect_contains` 等）在此文本上执行

被删除的消息（如 `✦ Thinking...`）不计入最终回复，但会记录在 timeline log 中。

---

## 5. 等待策略：Settle Detection

### 原理

不使用固定等待时间。每次发送消息后，启动一个**滑动窗口计时器**：

```
用户发送消息
    │
    ├─ 收到 bot 事件 → 重置计时器
    ├─ 收到 bot 事件 → 重置计时器
    ├─ ...
    ├─ [settle_timeout 秒内无任何事件]
    │   └─ → 判定为"稳定"，进入下一步
    │
    └─ [达到 max_wait]
        └─ → 强制进入下一步，标记 TIMEOUT
```

### 哪些事件重置计时器

| 事件 | 重置？ | 原因 |
|------|--------|------|
| `NewMessage` from bot | ✅ | bot 还在发新消息 |
| `MessageEdited` from bot | ✅ | bot 还在更新内容（流式输出） |
| `MessageDeleted` | ✅ | 可能是 status bubble 被删、真正回复即将到来 |
| Typing indicator | ❌ | 太频繁（每5秒），不作为稳定性判据 |

### 参数选择依据

| 参数 | 默认值 | 依据 |
|------|--------|------|
| `settle_timeout: 5s` | 5 秒 | crew-rs 流式编辑间隔为 1 秒（`EDIT_THROTTLE`），5 秒无编辑可以确信输出完成 |
| `max_wait: 120s` | 2 分钟 | crew-rs session_actor 默认超时也是 120 秒 |

---

## 6. 目录结构

```
crew-tg-tester/
├── README.md                 # 快速开始指南
├── requirements.txt          # telethon, pyyaml
├── config.example.yaml       # API credentials 模板
├── tester.py                 # 主程序入口
├── scenarios/                # 测试场景
│   ├── adaptive.yaml
│   ├── new_session.yaml
│   ├── queue_modes.yaml
│   └── file_handling.yaml
├── test_files/               # 测试用文件
│   ├── sample.pdf
│   ├── sample.txt
│   └── image.png
├── output/                   # 运行结果（git ignored）
│   ├── 2026-03-14T12:00:00_adaptive/
│   │   ├── timeline.jsonl    # 完整事件时间线
│   │   ├── report.md         # 人类可读测试报告
│   │   └── downloads/        # bot 回传的文件
│   └── ...
└── .gitignore                # 忽略 *.session, output/, config.yaml
```

### config.yaml 格式

```yaml
telegram:
  api_id: 12345
  api_hash: "your_api_hash"
  session_file: "crew_tester"   # 生成 crew_tester.session 文件
  bot: "@your_bot_username"     # 可被场景文件覆盖
```

---

## 7. 运行方式

### 首次使用

```bash
cd crew-tg-tester
pip install -r requirements.txt
cp config.example.yaml config.yaml
# 编辑 config.yaml 填入 api_id, api_hash, bot

# 首次运行会要求输入手机号和验证码（之后自动保存 session）
python tester.py scenarios/adaptive.yaml
```

### 日常使用

```bash
# 运行单个场景
python tester.py scenarios/new_session.yaml

# 运行目录下所有场景
python tester.py scenarios/

# 指定输出目录
python tester.py scenarios/adaptive.yaml -o ./my_results
```

### 输出

#### timeline.jsonl（机器可读）

每行一个 JSON 事件：

```jsonl
{"ts":"2026-03-14T12:00:00.000Z","dir":"out","type":"send","text":"/adaptive","step":0,"tag":"A-01"}
{"ts":"2026-03-14T12:00:00.500Z","dir":"in","type":"new","msg_id":101,"text":"**Adaptive Routing**\n  mode: hedge\n..."}
{"ts":"2026-03-14T12:00:00.500Z","dir":"sys","type":"settle","step":0,"result":"PASS"}
{"ts":"2026-03-14T12:00:01.000Z","dir":"out","type":"send","text":"/adaptive off","step":1,"tag":"A-02"}
{"ts":"2026-03-14T12:00:01.300Z","dir":"in","type":"new","msg_id":102,"text":"Adaptive mode: off (static priority, failover only)"}
{"ts":"2026-03-14T12:00:06.300Z","dir":"sys","type":"settle","step":1,"result":"PASS"}
```

#### report.md（人类可读）

```markdown
# 测试报告：adaptive模式切换
- 日期：2026-03-14 12:00
- Bot：@crew_test_bot
- 场景文件：scenarios/adaptive.yaml

## 结果汇总
| 总步骤 | PASS | FAIL | TIMEOUT | SKIP |
|--------|------|------|---------|------|
| 21     | 19   | 1    | 1       | 0    |

## 详细结果
| # | Tag  | 发送内容          | 预期           | 实际               | 结果    |
|---|------|-------------------|----------------|--------------------|---------|
| 0 | A-01 | /adaptive         | (无断言)       | Adaptive Routing...| PASS    |
| 1 | A-02 | /adaptive off     | 含 "off"       | Adaptive mode: off | PASS    |
| 5 | A-06 | /adaptive circuit | 含 "hedge"     | Unknown option...  | FAIL    |
```

---

## 8. 安全注意事项

### Session 文件保护

Telethon 的 `.session` 文件等同于账号的完整访问权限。

**必须做到**：
- `*.session` 加入 `.gitignore`
- `config.yaml`（含 api_hash）加入 `.gitignore`
- 不要将 session 文件复制到服务器或分享给他人

### Telegram 风控规避

| 风险行为 | 规避方式 |
|----------|----------|
| 短时间大量消息 | 每步之间有 settle 等待（自然间隔 5+ 秒） |
| 新注册账号 | 使用自己的主号（老账号） |
| Flood wait | 捕获 `telethon.errors.FloodWaitError`，按要求等待后重试 |

### 测试数据

- `test_files/` 中不放敏感文件
- 测试场景不包含真实用户数据
- `output/` 目录加入 `.gitignore`

---

## 9. 已知限制与未来扩展

### V1 已知限制

| 限制 | 原因 | 影响 |
|------|------|------|
| 不能点击 inline keyboard 按钮 | Telethon 支持但 V1 不实现 | `/sessions` 的按钮交互无法自动化 |
| 条件分支只支持 `contains` 文本匹配 | V1 保持简单 | 不能做正则匹配或语义判断 |
| 单线程顺序执行 | V1 保持简单 | 不能并行跑多个场景 |
| `MessageDeleted` 事件不带 from_user | Telegram API 限制 | 可能误捕获其他消息的删除事件，需用 message_id 关联 |
| Settle detection 可能误判 | 如果 bot 在 settle_timeout 内恰好暂停输出后又继续 | 可通过增大 settle_timeout 缓解 |

### 未来扩展方向（Advanced 版本）

| 方向 | 说明 |
|------|------|
| **Inline keyboard 交互** | 模拟用户点击按钮，验证回调响应 |
| **正则 / JSONPath 断言** | `expect_matches: "latency=\\d+ms"` |
| **LLM 辅助判定** | 用 LLM 评判 bot 回复质量（"回答是否正确且完整？"） |
| **并行场景执行** | 多个场景同时跑，缩短测试时间 |
| **Diff 对比** | 同一场景的两次运行结果对比（回归测试） |
| **CI 集成** | 使用 StringSession 环境变量替代文件，跑在 CI 中 |
| **多 bot 测试** | 同一场景对比不同 bot（如不同 Provider 配置） |
| **录制-回放** | 手动在 Telegram 操作一次，自动生成 YAML 场景文件 |
