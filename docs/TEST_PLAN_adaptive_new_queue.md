# 功能测试计划：/adaptive、/new、/queue

**测试方式**：通过 Telegram 终端对已运行的 crew-rs gateway 发送命令
**日期**：2026-03-14

---

## 0. 环境探测（执行测试前先跑这些）

| # | 操作 | 预期结果 | 通过 |
|---|------|----------|------|
| E-01 | 发送 `/adaptive` | 显示当前模式(off/hedge/lane)、qos 状态、当前 provider、各 provider 指标（延迟/ok/err/状态） | ☐ |
| E-02 | 发送 `/queue` | 显示当前队列模式，如 `Queue mode: Speculative` | ☐ |
| E-03 | 发送 `/sessions` | 显示当前会话列表或 "No sessions found..." | ☐ |
| E-04 | 发送一条普通消息如 `你好` | Agent 正常回复，确认系统可用 | ☐ |

> **记录**：E-01 的输出中 provider 数量（决定后续 adaptive 测试的可执行范围）：______ 个

---

## A. /adaptive 自适应路由测试

### A1. 命令解析与状态显示

| # | 操作 | 预期结果 | 通过 |
|---|------|----------|------|
| A-01 | `/adaptive` | 显示状态面板，包含 **Adaptive Routing**（mode/qos/current）和 **Providers** 列表（每行：name (model): latency=Xms ok=N err=N ✅/⛔） | ☐ |
| A-02 | `/adaptive off` | 回复 `Adaptive mode: off (static priority, failover only)` | ☐ |
| A-03 | `/adaptive hedge` | 回复 `Adaptive mode: hedge (race 2 of N providers, take winner)` | ☐ |
| A-04 | `/adaptive lane` | 回复 `Adaptive mode: lane (score-based selection across N providers)` | ☐ |
| A-05 | `/adaptive race` | 同 A-03（`race` 是 `hedge` 的别名） | ☐ |
| A-06 | `/adaptive circuit` | 同 A-03（`circuit` 是 `hedge` 的别名） | ☐ |
| A-07 | `/adaptive qos` | 显示当前 QoS 状态，如 `QoS ranking: off` | ☐ |
| A-08 | `/adaptive qos on` | 回复 `QoS ranking: on` | ☐ |
| A-09 | `/adaptive qos off` | 回复 `QoS ranking: off` | ☐ |
| A-10 | `/adaptive qos 1` | 回复 `QoS ranking: on`（`1` 等同于 `on`） | ☐ |
| A-11 | `/adaptive qos 0` | 回复 `QoS ranking: off`（`0` 等同于 `off`） | ☐ |
| A-12 | `/adaptive blahblah` | 回复 `Unknown option: blahblah` + Usage 提示 | ☐ |
| A-13 | `/adaptive qos maybe` | 回复 `Invalid value: maybe. Use: on/off` | ☐ |

### A2. 模式切换后行为验证

> 以下测试需要 **2+ Provider**。如果 E-01 只显示 1 个 Provider，记录警告信息即可。

| # | 前置 | 操作 | 预期结果 | 通过 |
|---|------|------|----------|------|
| A-14 | `/adaptive off` | 发送 `1+1等于几` | 正常回复。再看 `/adaptive`，只有一个 provider 有新增 ok 计数 | ☐ |
| A-15 | `/adaptive hedge` | 发送 `1+1等于几` | 正常回复。再看 `/adaptive`，可能有两个 provider 的 ok 计数增加（竞速） | ☐ |
| A-16 | `/adaptive lane` | 连续发送 3 条简短问题 | 正常回复。查看 `/adaptive`，current provider 可能根据评分变化 | ☐ |
| A-17 | `/adaptive hedge` | 查看 `/adaptive` | 延迟 EMA 数值应该为正数（非 0），ok 计数累增 | ☐ |

### A3. 运行时切换与状态一致性

| # | 操作 | 预期结果 | 通过 |
|---|------|----------|------|
| A-18 | 依次执行：`/adaptive off` → `/adaptive hedge` → `/adaptive lane` → `/adaptive off` | 每次切换后 `/adaptive` 显示的 mode 与最后设置一致 | ☐ |
| A-19 | `/adaptive hedge` → `/adaptive qos on` → `/adaptive` | 同时显示 `mode: hedge` 和 `qos ranking: on`（两者独立） | ☐ |

### A4. 单 Provider 降级提示

> 如果配置了 2+ Provider，可跳过此项。此项测试记录系统在只有 1 个 Provider 时是否给出合适的警告。

| # | 前置条件 | 操作 | 预期结果 | 通过 |
|---|----------|------|----------|------|
| A-20 | 仅 1 个 Provider 的部署 | `/adaptive hedge` | 回复含 `⚠️ Only 1 provider configured — hedge needs ≥2 to race` | ☐ |
| A-21 | 仅 1 个 Provider 的部署 | `/adaptive lane` | 回复含 `⚠️ Only 1 provider configured — lane needs ≥2 to compare` | ☐ |

---

## N. /new 会话管理测试

### N1. 基本会话操作

| # | 操作 | 预期结果 | 通过 |
|---|------|----------|------|
| N-01 | `/new` | 回复 `Session cleared.`（清除当前会话历史） | ☐ |
| N-02 | 清除后发送 `我之前问了什么？` | Agent 应该不知道之前的对话内容（历史已清空） | ☐ |
| N-03 | `/new research` | 回复 `Switched to session: research` | ☐ |
| N-04 | 在 research 会话中发送 `记住关键词：苹果` | Agent 正常回复 | ☐ |
| N-05 | `/new coding` | 回复 `Switched to session: coding` | ☐ |
| N-06 | 在 coding 会话中发送 `我之前说的关键词是什么？` | Agent 不应该知道"苹果"（不同会话隔离） | ☐ |

### N2. 会话切换与上下文保持

| # | 操作 | 预期结果 | 通过 |
|---|------|----------|------|
| N-07 | `/s research` | 回复 `Switched to session: research` + 最近 2 条消息预览（[user] 和 [assistant]，各截取前 100 字符） | ☐ |
| N-08 | 发送 `我之前说的关键词是什么？` | Agent 应该记得"苹果"（research 会话上下文恢复） | ☐ |
| N-09 | `/s` (无参数) | 回复 `Switched to default session.` | ☐ |

### N3. 会话列表与导航

| # | 操作 | 预期结果 | 通过 |
|---|------|----------|------|
| N-10 | `/sessions` | 显示会话列表，至少包含 research 和 coding。当前活跃会话有标记。Telegram 上可能显示为 inline keyboard | ☐ |
| N-11 | `/back` | 回复 `Switched back to session: <上一个会话名>`（切换到前一个会话） | ☐ |
| N-12 | 再次 `/back` | 回复切换到更前一个，或 `No previous session to switch to.` | ☐ |

### N4. 会话删除

| # | 操作 | 预期结果 | 通过 |
|---|------|----------|------|
| N-13 | `/delete coding` | 回复 `Deleted session: coding` | ☐ |
| N-14 | `/sessions` | coding 不再出现在列表中 | ☐ |
| N-15 | `/delete` (无参数) | 回复 `Usage: /delete <session-name>` | ☐ |

### N5. 输入验证

| # | 操作 | 预期结果 | 通过 |
|---|------|----------|------|
| N-16 | `/new a#b` | 回复 `Invalid session name: topic name cannot contain #, :, or /` | ☐ |
| N-17 | `/new a:b` | 同上，拒绝含 `:` 的名称 | ☐ |
| N-18 | `/new a/b` | 同上，拒绝含 `/` 的名称 | ☐ |
| N-19 | `/new aaaaaa...`（超过 50 字符） | 回复 `Invalid session name: topic name too long (max 50 characters)` | ☐ |
| N-20 | `/new 测试中文` | 回复 `Switched to session: 测试中文`（中文名称应被接受） | ☐ |

### N6. 清理

| # | 操作 | 预期结果 | 通过 |
|---|------|----------|------|
| N-21 | `/delete research` | `Deleted session: research` | ☐ |
| N-22 | `/delete 测试中文` | `Deleted session: 测试中文` | ☐ |
| N-23 | `/s` | 切换回默认会话 | ☐ |

---

## Q. /queue 队列模式测试

### Q1. 命令解析

| # | 操作 | 预期结果 | 通过 |
|---|------|----------|------|
| Q-01 | `/queue` | 显示当前模式，如 `Queue mode: Speculative` | ☐ |
| Q-02 | `/queue followup` | 回复 `Queue mode set to: Followup` | ☐ |
| Q-03 | `/queue collect` | 回复 `Queue mode set to: Collect` | ☐ |
| Q-04 | `/queue steer` | 回复 `Queue mode set to: Steer` | ☐ |
| Q-05 | `/queue interrupt` | 回复 `Queue mode set to: Interrupt` | ☐ |
| Q-06 | `/queue spec` | 回复 `Queue mode set to: Speculative`（`spec` 是缩写） | ☐ |
| Q-07 | `/queue speculative` | 回复 `Queue mode set to: Speculative` | ☐ |
| Q-08 | `/queue banana` | 回复 `Unknown mode: banana. Use: followup, collect, steer, interrupt, spec` | ☐ |

### Q2. Followup 模式行为

| # | 前置 | 操作 | 预期结果 | 通过 |
|---|------|------|----------|------|
| Q-09 | `/queue followup` | 快速连续发送 3 条消息：`问题A`、`问题B`、`问题C` | 收到 3 条独立回复，顺序对应 A→B→C。每条分别处理，无合并 | ☐ |

### Q3. Collect 模式行为

| # | 前置 | 操作 | 预期结果 | 通过 |
|---|------|------|----------|------|
| Q-10 | `/queue collect`，然后发送一条需要较长处理时间的问题（如 `请详细解释量子计算的基本原理`） | 在 Agent 处理期间，快速追加发送 `补充：特别是量子纠缠` 和 `还有量子叠加` | 第一条正常回复。后续 2 条消息被合并成一条处理，回复内容同时涵盖"量子纠缠"和"量子叠加"。合并格式为 `内容\n---\nQueued #1: 内容` | ☐ |

### Q4. Steer 模式行为

| # | 前置 | 操作 | 预期结果 | 通过 |
|---|------|------|----------|------|
| Q-11 | `/queue steer`，然后发送一条较长处理的问题 | 在 Agent 处理期间，快速追加发送 `不对，换一个话题` 和 `讲讲Rust的所有权机制` | 第一条正常回复。Agent 空闲后只处理最后一条 `讲讲Rust的所有权机制`，中间的 `不对，换一个话题` 被丢弃 | ☐ |

### Q5. Interrupt 模式行为

| # | 前置 | 操作 | 预期结果 | 通过 |
|---|------|------|----------|------|
| Q-12 | `/queue interrupt`，然后发送一条需要长时间处理的任务 | 在 Agent 处理期间发送 `停！换一个话题：什么是Rust` | 当前任务被取消，Agent 转而回答"什么是Rust"。可能看到第一条任务的部分输出被截断 | ☐ |

### Q6. Speculative 模式行为

| # | 前置 | 操作 | 预期结果 | 通过 |
|---|------|------|----------|------|
| Q-13 | `/queue spec`，然后发送一条较长任务 | 在 Agent 处理期间发送第二条独立问题 | 两条消息被并行处理，各自独立回复。可能看到第二条的回复先于第一条到达（如果第二条更快） | ☐ |
| Q-14 | 紧接 Q-13 | 观察回复消息 | 每条回复是独立的消息气泡，不互相干扰。第二条的回复可能带有 `⬆️ Earlier task completed` 标记（如果 primary 还在运行时完成） | ☐ |

### Q7. 模式切换一致性

| # | 操作 | 预期结果 | 通过 |
|---|------|----------|------|
| Q-15 | `/queue followup` → `/queue` | 显示 `Queue mode: Followup` | ☐ |
| Q-16 | `/queue collect` → `/queue` | 显示 `Queue mode: Collect` | ☐ |
| Q-17 | `/queue spec` → `/queue` | 显示 `Queue mode: Speculative` | ☐ |

### Q8. 各模式排斥性验证

| # | 前置 | 操作 | 预期结果 | 通过 |
|---|------|------|----------|------|
| Q-18 | `/queue followup` | 连续发送 2 条消息 | **不合并**（每条独立回复），**不丢弃**（都有回复），**不并行**（按序处理） | ☐ |
| Q-19 | `/queue steer` | 连续发送 3 条消息 | 第一条正常。剩余只处理最新一条，中间的被丢弃。**不合并** | ☐ |
| Q-20 | `/queue collect` | Agent 空闲时发送 1 条消息 | 只有这一条，不等待合并，直接处理（没有排队就不需要合并） | ☐ |

---

## X. 跨功能联动测试

| # | 操作步骤 | 预期结果 | 通过 |
|---|----------|----------|------|
| X-01 | 1. `/new test-cross` 创建新会话<br>2. `/queue collect` 设置队列模式<br>3. `/queue` 查看 | 新会话中队列模式为 Collect（/queue 的设置作用于当前 session actor） | ☐ |
| X-02 | 1. `/adaptive hedge`<br>2. `/queue spec`<br>3. 发送一个长任务，期间发送第二条 | Speculative 并发 + Hedge 竞速同时工作。两条消息都得到回复。`/adaptive` 显示 provider 指标有更新 | ☐ |
| X-03 | 1. `/queue spec`<br>2. 发送一个长任务<br>3. 在 Agent 处理期间发送 `/adaptive` | `/adaptive` 正常返回状态（斜杠命令在 Speculative 模式下不应被当作 overflow 任务） | ☐ |
| X-04 | 1. `/queue spec`<br>2. 发送一个长任务<br>3. 在 Agent 处理期间发送 `/queue` | `/queue` 正常返回状态（同上，斜杠命令不当作溢出） | ☐ |
| X-05 | 1. `/new session-a`，发送 `关键词：橘子`<br>2. `/new session-b`，发送 `关键词：西瓜`<br>3. `/s session-a`<br>4. 发送 `我的关键词是什么？` | 回复"橘子"（会话隔离 + 上下文恢复）。不应回复"西瓜" | ☐ |

---

## 已知限制（不测范围）

以下行为是已知设计限制，不作为缺陷：

1. **Speculative 交互提示断裂**：如果 Agent 在 overflow 中反问用户后返回 EndTurn，用户的回复会被当作新的独立查询而非续答
2. **短消息误路由**：Speculative 模式下用户发送 `是`、`2` 等短回复可能被当作新任务而非对当前对话的回应
3. **队列模式不持久化**：`/queue` 的设置在 gateway 重启后恢复为配置文件默认值
4. **Adaptive 指标不跨重启**：Provider 指标（延迟/成功/失败计数）存储在内存中，重启后重置
5. **自动升降级**：ResponsivenessObserver 需要连续 5 次 baseline 采样 + 3 次慢请求（>3× baseline）才会自动升级到 Speculative + Hedge。实际触发需要特定的网络/Provider 延迟条件，难以手动复现

---

## 测试结果汇总

| 分类 | 总数 | 通过 | 失败 | 跳过 |
|------|------|------|------|------|
| 环境探测 (E) | 4 | | | |
| /adaptive (A) | 21 | | | |
| /new (N) | 23 | | | |
| /queue (Q) | 20 | | | |
| 跨功能 (X) | 5 | | | |
| **合计** | **73** | | | |

**测试人**：_________
**测试日期**：_________
**gateway 版本/commit**：_________
**Provider 配置**：_________
