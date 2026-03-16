# Agent 架构升级方案

## 背景

当前系统的摘要生成模块（`minimax_service.py`）采用单轮 LLM 调用模式：
系统提示词 + 会议文本 → 要求模型直接输出固定 JSON → 解析三个字段。

这种方式存在以下局限：

| 问题 | 说明 |
|------|------|
| 输出固定 | 只能得到 summary / keywords / todos 三个字段 |
| 无推理过程 | 模型一次性完成所有分析，容错能力弱 |
| 不可扩展 | 增加分析维度需要改 Prompt，容易引入 JSON 格式错误 |
| 无法调用外部能力 | 无法搜索、计算、查询外部系统 |

## 升级目标

将大模型从"单轮问答"升级为**工具调用 Agent（Tool-Calling Agent）**，使模型能够：

1. 主动决策：推理应该调用哪个工具、以什么顺序调用
2. 多步执行：每次只做一件事，结果反馈给模型后继续下一步
3. 结构化输出：每个工具返回明确 schema，避免自由格式 JSON 解析失败
4. 可横向扩展：未来可接入搜索、日历、邮件等真实外部工具

---

## 实现方式：ReAct 风格工具调用循环

```
用户输入（会议转写）
        │
        ▼
┌──────────────────┐
│  系统 Prompt     │  告知 Agent 拥有的工具及调用顺序
│  + 会议文本      │
└────────┬─────────┘
         │ 第 1 轮
         ▼
┌──────────────────┐        ┌─────────────────────┐
│  MiniMax LLM     │ ──────►│  tool_call:          │
│  (MiniMax-M2.5)  │        │  extract_summary(…)  │
└──────────────────┘        └──────────┬──────────┘
                                        │ 执行工具（本地捕获结构化输出）
                                        │ 返回 { status: "ok" }
         ▲                              │
         └──────────── 消息历史追加 ◄───┘
         │ 第 2 轮 … 第 N 轮
         ▼
  (extract_key_decisions → extract_action_items
   → extract_keywords → finish_report)
         │
         ▼
┌──────────────────┐
│  AgentMeetingReport │  汇总所有工具调用结果
└──────────────────┘
```

---

## 当前已实现的工具集

| 工具名 | 作用 | 输出字段 |
|--------|------|----------|
| `extract_summary` | 提取会议摘要（≤300字） | `summary: str` |
| `extract_key_decisions` | 提取正式决议 | `decisions: list[str]` |
| `extract_action_items` | 提取行动项，含负责人和截止时间 | `action_items: list[{task, owner, deadline}]` |
| `extract_keywords` | 提取关键词（5-10个） | `keywords: list[str]` |
| `finish_report` | 汇总整体会议评估，终止 Agent 循环 | `overall_assessment: str` |

---

## 新旧接口对比

### 旧接口 `POST /api/summary`

```json
// 请求
{ "transcribed_text": "…" }

// 响应
{
  "summary": "…",
  "keywords": ["…"],
  "todos": ["完成A", "跟进B"]
}
```

### 新接口 `POST /api/agent/analyze`

```json
// 请求
{ "transcribed_text": "…" }

// 响应
{
  "summary": "…",
  "key_decisions": ["决定采用方案A", "推迟下次会议至下周"],
  "action_items": [
    { "task": "输出设计稿", "owner": "李明", "deadline": "本周五" },
    { "task": "更新接口文档", "owner": "", "deadline": "" }
  ],
  "keywords": ["API设计", "数据库", "上线时间"],
  "overall_assessment": "本次会议议题明确，决策效率较高，建议后续落实行动项负责人。"
}
```

---

## 文件变更清单

```
backend/
  app/
    schemas/meeting.py          ← 新增 ActionItem / AgentMeetingReport / AgentAnalyzeRequest
    services/agent_service.py   ← 新建：工具定义 + Agent 循环 + fallback
    api/routes.py               ← 新增 POST /api/agent/analyze 路由

frontend/
  src/
    api/meeting.js              ← 新增 analyzeWithAgent(text)
    App.vue                     ← 新增"3. Agent 深度分析"按钮 + 深度报告卡片
```

---

## 未来可扩展的工具方向

以下工具可在后续迭代中接入，**无需改动 Agent 循环本身**，只需在 `_AGENT_TOOLS` 列表中追加工具定义，并在 `_execute_tool` 中实现对应逻辑：

| 工具 | 能力 |
|------|------|
| `search_transcript(query)` | 在转写文本中检索特定内容（支持关键词跳转） |
| `identify_speakers(text)` | 基于语气/称呼推断发言人 |
| `web_search(query)` | 搜索会议中提到的技术术语或外部信息 |
| `create_calendar_event(title, time)` | 将行动项自动转为日历提醒 |
| `send_email_draft(recipients, body)` | 生成会议纪要邮件草稿 |
| `save_to_database(report)` | 将报告持久化到 MySQL |
| `translate_summary(lang)` | 将摘要翻译为其他语言 |

---

## 与 LangChain / LangGraph 的关系

本实现采用**直接调用 MiniMax 原生 tool-calling API** 的方式，无需引入 LangChain 等额外框架。
优点：依赖轻、可控性强、与现有 httpx 生态一致。

如果后续工具数量增加到 10+ 个、或需要并发工具调用、分支推理等复杂能力，可考虑引入：
- **LangGraph**：显式状态机管理多 Agent 工作流
- **LlamaIndex**：文档检索 + 问答混合场景
- **AutoGen**：多 Agent 协作（如一个 Agent 负责转写分析，另一个负责生成报告）

---

## 安全与成本考虑

- 每次 Agent 分析最多执行 `_MAX_AGENT_STEPS = 10` 轮，防止无限循环
- 所有工具调用的 token 消耗高于单轮调用；建议在 UI 上区分"快速摘要"（`/summary`）和"深度分析"（`/agent/analyze`）
- API Key 通过 `.env` 注入，不暴露在前端
