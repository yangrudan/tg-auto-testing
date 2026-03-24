"# discord-bot-tester User Manual

Discord Bot 自动化功能测试工具 — 以真实用户身份向 Discord bot 发送消息，捕获完整响应生命周期，执行断言，生成测试报告。

---

## 目录

1. [前置条件](#1-前置条件)
2. [安装](#2-安装)
3. [配置](#3-配置)
4. [快速验证：hello.py](#4-快速验证hellopy)
5. [运行测试场景：tester.py](#5-运行测试场景testerpy)
6. [YAML 场景格式](#6-yaml-场景格式)
7. [输出格式](#7-输出格式)
8. [安全注意事项](#8-安全注意事项)

---

## 1. 前置条件

| 项目 | 说明 |
|------|------|
| Python 3.10+ | 系统已安装 |
| Discord 账号 | 用你自己的账号 |
| Discord Bot | 已创建并邀请到服务器 |
| Bot Token | 从 Discord Developer Portal 获取 |

### 获取 Discord Bot Token

1. 打开 https://discord.com/developers/applications
2. 点击 **New Application**，填写名称后创建
3. 左侧菜单选择 **Bot**
4. 点击 **Reset Token**，复制并保存 Token（**只显示一次！**）
5. 启用 **Message Content Intent** 和 **Server Members Intent**
6. 左侧菜单选择 **OAuth2 → URL Generator**
7. 选择 **scopes**: `bot`
8. 选择 **bot permissions**: 
   - Send Messages
   - Read Message History
   - Manage Messages
   - Message Content Intent
9. 复制生成的 URL，在浏览器打开，邀请 Bot 到你的服务器

---

## 2. 安装

```bash
cd discord-bot-tester
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 3. 配置

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`：

```yaml
discord:
  token: "YOUR_BOT_TOKEN_HERE"   # 替换为你的 Bot Token
  bot: "your_bot_name"           # 替换为目标 Bot 的用户名（不含 #0000）
  guild_id: 123456789012345678   # 可选，目标服务器 ID
  channel_name: "test-channel"   # 可选，目标频道名称
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `token` | 是 | Discord Bot Token |
| `bot` | 是 | 目标 Bot 的用户名 |
| `guild_id` | 否 | 目标服务器 ID（默认使用第一个服务器） |
| `channel_name` | 否 | 目标频道名称（默认使用第一个文本频道） |

### 获取 Server ID 和 Channel ID

1. 在 Discord 中启用 **Developer Mode**（设置 → 高级 → 开发者模式）
2. 右键点击服务器/频道 → **复制 ID**

---

## 4. 快速验证：hello.py

首次使用前，先用 `hello.py` 验证连接是否正常。

```bash
source venv/bin/activate
python3 hello.py
```

### 预期输出

```
Logged in as your_bot#1234
Found bot: target_bot in Your Server
Using channel: #test-channel in Your Server

>>> Test Hello World
  [2026-03-14T12:00:02.500Z] NEW  id=1234567890123456789  Hello! How can I help you?
  [2026-03-14T12:00:10.500Z] EDIT id=1234567890123456789  Hello! How can I help you today?

============================================================
Done. Captured 2 events in 12s.
============================================================

Bot final reply:
  [msg 1234567890123456789] Hello! How can I help you today?
```

事件类型说明：

| 事件 | 含义 |
|------|------|
| `NEW` | bot 发送了新消息 |
| `EDIT` | bot 编辑了消息（流式输出或状态更新） |
| `DEL` | bot 删除了消息 |

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
2. 每步：发送消息 → 等待 bot 回复稳定 → 执行断言
3. 实时在终端打印事件流和每步结果
4. 结束后生成 `timeline.jsonl` 和 `report.md`

终端输出示例：

```
Logged in as tester_bot#5678
Using channel: #test in Test Server

Running scenario: Hello World Test
Bot: your_bot  |  Steps: 1
============================================================

>>> Hello
  [2026-03-14T21:30:01.000Z] NEW  id=9876543210987654321  Hello there!
  [H-01] ✅ PASS

============================================================
Scenario: Hello World Test
Results:  1 PASS / 0 FAIL / 0 TIMEOUT / 1 total
============================================================
  Timeline: output/2026-03-14T21-30-00_Hello_World_Test/timeline.jsonl
  Report:   output/2026-03-14T21-30-00_Hello_World_Test/report.md
```

### Settle Detection（等待策略）

tester.py 不使用固定等待时间。发送消息后启动一个滑动窗口计时器：

- 每收到 bot 的事件（NEW/EDIT/DEL），计时器归零
- 连续 `settle_timeout` 秒无事件 → 判定回复完成，进入下一步
- 超过 `max_wait` 秒 → 强制进入下一步，标记 TIMEOUT

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `settle_timeout` | 5 秒 | Discord 流式编辑间隔建议 1 秒以上 |
| `max_wait` | 120 秒 | 最大等待时间 |

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
| `send` | string | 发送文本消息 |

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

"最终回复"= 本步期间 bot 发送的所有未被删除的消息，取各消息最后编辑版本，拼接而成。

#### 条件分支

```yaml
- send: "问一个问题"
  on_response:
    - contains: "预期回答 A"
      steps:
        - send: "继续 A 路线"
          tag: "BRANCH-A"
    - contains: "预期回答 B"
      steps:
        - send: "继续 B 路线"
          tag: "BRANCH-B"
    - default:
        steps:
          - tag: "BRANCH-FAIL"
```

匹配规则：从上到下，**第一个命中的 `contains`** 执行其 `steps`，不再继续。都不命中则执行 `default`。

---

## 7. 输出格式

每次运行在 `output/` 下生成带时间戳的目录：

```
output/2026-03-14T21-30-00_Hello_World_Test/
├── timeline.jsonl    # 完整事件时间线（机器可读）
└── report.md         # 测试报告（人类可读）
```

### timeline.jsonl

每行一个 JSON 对象，三种 `dir`：

```jsonl
{"ts":"...","dir":"out","type":"send","text":"Hello","step":0,"tag":"H-01"}
{"ts":"...","dir":"in","type":"new","msg_id":123,"text":"Hello there!"}
{"ts":"...","dir":"sys","type":"result","step":0,"tag":"H-01","result":"PASS","detail":null}
```

| dir | 含义 |
|-----|------|
| `out` | 我们发出的消息 |
| `in` | bot 的事件（new/edit/delete） |
| `sys` | 系统判定（result: PASS/FAIL/TIMEOUT/SKIP） |

### report.md

Markdown 格式的测试报告，包含汇总表和逐步详情。

---

## 8. 安全注意事项

| 项目 | 说明 |
|------|------|
| `config.yaml` | 包含 Bot Token，**已加入 .gitignore，不要分享或上传** |
| Bot Token | 等同于账号完整访问权限，泄露后立即在 Developer Portal 重置 |
| Discord 风控 | settle 等待自然形成 5+ 秒间隔，低频操作不会触发风控 |
| 权限最小化 | 只授予 Bot 必要的权限 |

---

## 故障排除

| 问题 | 解决 |
|------|------|
| `ModuleNotFoundError: No module named 'discord'` | 确认已激活 venv：`source venv/bin/activate`，然后 `pip install -r requirements.txt` |
| `FileNotFoundError: config.yaml` | 运行 `cp config.example.yaml config.yaml` 并编辑 |
| `LoginFailed` | 检查 config.yaml 中的 token 是否正确 |
| `No target channel found` | 确认 Bot 已邀请到服务器，且有访问频道的权限 |
| 所有步骤 TIMEOUT | 确认 Bot 正在运行且可正常响应 |
| `Forbidden` | 检查 Bot 权限和 Intents 是否启用 |

---

## 与 Telegram 版本的区别

| 特性 | Telegram | Discord |
|------|----------|---------|
| 认证方式 | API ID + Hash + 手机验证码 | Bot Token |
| 主要库 | Telethon | discord.py |
| 消息编辑 | 无限制 | 有 rate limit |
| 事件监听 | 自动启用 | 需要启用 Intents |
| 文件发送 | 支持 | 支持（未实现） |
| 频道选择 | DM 对话 | 需要指定服务器和频道 |

---

## 项目结构

```
discord-bot-tester/
├── config.example.yaml    # 配置模板
├── config.yaml            # 实际配置（.gitignore）
├── hello.py               # Hello World 验证
├── tester.py              # 主测试器
├── requirements.txt       # 依赖
├── README.md              # 本文件
├── scenarios/             # 测试场景
│   └── hello.yaml
└── output/                # 测试输出（.gitignore）
    └── {timestamp}_{scenario}/
        ├── timeline.jsonl
        └── report.md
```