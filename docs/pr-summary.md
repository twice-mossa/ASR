# PR 总结（2026-03-16 ~ 2026-03-18）

> 统计范围：过去两天内创建或合并的 Pull Request

---

## 已合并 PR

### PR #20 · Persist meetings across backend and frontend workspace
- **作者**：g3x1n
- **合并时间**：2026-03-18
- **目标分支**：`dev`
- **变更规模**：+1204 / -408，涉及 25 个文件
- **核心内容**：
  - 新增后端会议持久化模型（会议记录、转录分段、摘要）
  - 新增认证会议 API（创建会议、列表、详情、启动转录）
  - 将上传音频持久化到本地存储，通过 `/media` 路由暴露
  - 转录与摘要结果回写至会议记录
  - 前端工作区状态改为从后端会议记录加载，不再依赖内存快照
  - 左侧历史栏改为展示真实持久化会议
  - 更新 README 和测试/运行文档

---

### PR #19 · release: merge dev into main
- **作者**：g3x1n
- **合并时间**：2026-03-18
- **目标分支**：`main`
- **变更规模**：+6815 / -151，涉及 57 个文件（34 个提交）
- **核心内容**：将 `dev` 分支的集成进展合并至 `main`，包含：
  - 聊天式前端工作台重构
  - 音频上传 / 转录 / 摘要工作流改进
  - 悬浮音频状态条与 Markdown 纪要导出
  - 历史会话恢复与工作区状态管理改进
  - 前端 `App.vue` 业务逻辑拆分至 composables

---

### PR #18 · fix(frontend): restore audio history and extract composables
- **作者**：g3x1n
- **合并时间**：2026-03-18
- **目标分支**：`dev`
- **变更规模**：+1121 / -875，涉及 6 个文件
- **核心内容**：
  - **修复**：切换历史会话时恢复音频播放上下文
  - **修复**：摘要存在但关键词或待办为空时，仍允许 Markdown 导出
  - **重构**：拆分 `App.vue`，提取四个 composables：
    - `useAuthSession`（认证逻辑）
    - `useConversationWorkspace`（会话与工作区状态）
    - `useAudioFileContext`（音频文件选择与上传上下文）
    - `useMeetingWorkflow`（转录 / 摘要 / 导出 / 提问流程）
  - 共享纯工具函数移至 `utils/workspace.js`

---

### PR #17 · feat(frontend): rebuild as chat-style audio analysis workspace
- **作者**：g3x1n
- **合并时间**：2026-03-18
- **目标分支**：`dev`
- **变更规模**：+2620 / -1232，涉及 20 个文件
- **核心内容**：
  - 将前端从表单/卡片式页面重构为聊天式音频分析工作台
  - 左侧历史会话列表 + 右侧消息流工作区
  - 登录改为按需弹窗，不再首屏强制遮挡
  - 上传后在输入区上方展示悬浮音频状态条
  - 新增 Markdown 格式会议纪要导出
  - 支持同一会话内的上传 → 转录 → 摘要 → 提问流程
  - UI 布局与密度优化，添加全局主题层与 favicon
  - RAG 问答和推理链接口仍为 UI 占位

---

## 未合并 / 已关闭 PR

### PR #16 · feat: add meeting agent demo workflow
- **作者**：twice-mossa
- **状态**：Closed（未合并，存在 merge conflict）
- **创建时间**：2026-03-16
- **核心内容**：
  - Meeting Agent 脚手架（工具注册表、路由提示词、音频检查、ASR 工具、轻量说话人轮次）
  - 新增 `/api/agent/run` 和 `/api/summary/email` 接口
  - 前端展示工具调用轨迹、说话人筛选、提示词详情，支持邮件发送摘要
- **备注**：与 dev 分支存在冲突，最终通过 PR #17/18/19 中的新版实现替代

---

### PR #15 · feat: upgrade meeting analysis from single-turn LLM to tool-calling agent
- **作者**：Copilot
- **状态**：Closed（草稿，未合并）
- **创建时间**：2026-03-16
- **核心内容**：
  - 将 `/api/summary` 的单次 LLM 调用升级为 ReAct 风格的 Tool-Calling Agent
  - 新增 `agent_service.py`，最多 10 步循环，支持 5 个工具：
    `extract_summary`、`extract_key_decisions`、`extract_action_items`、`extract_keywords`、`finish_report`
  - 新增 `POST /api/agent/analyze` 端点（不破坏现有 `/summary` 接口）
  - 前端新增"Agent 深度分析"按钮，展示决策、行动项（含负责人/截止日期）、关键词、总体评估
  - 新增 `docs/agent-architecture.md` 架构文档
- **备注**：功能设计被后续 PR #16 继承和扩展，最终未单独合并

---

## 阶段小结

| 维度 | 详情 |
|---|---|
| 合并 PR 数 | 4 个（#17、#18、#19、#20） |
| 关闭未合并 PR 数 | 2 个（#15、#16） |
| 主要推进方向 | 前端聊天式工作台重构、会议记录后端持久化 |
| 本阶段里程碑 | `dev` 集成稳定后，通过 PR #19 推送到 `main` |
| 当前待做 | RAG 问答接口、说话人区分、完整会议管理操作 |
