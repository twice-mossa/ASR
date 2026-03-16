# 3月13日 Pull Request 汇总

本文档汇总了 2026 年 3 月 13 日当天提交的所有 Pull Request，共 9 个，涵盖前端重设计、音频上传体验优化、大文件分片转写、Prompt 泄漏修复、渐进式转写展示以及里程碑推进等方面。

---

## PR #6 — feat: polish homepage ui

- **作者**：g3x1n  
- **目标分支**：dev  
- **状态**：已合并  
- **时间**：01:28

**主要内容：**
- 重设计首页 Hero 区域，更贴近产品化落地风格
- 移除了对真实用户无意义的展示性内容
- 优化了 Auth 面板的视觉层次、文案和节奏
- 统一首页与登录后工作区的视觉语言
- 改善了排版、间距、背景图层、卡片样式和交互反馈

**涉及文件：** `frontend/src/App.vue`、`frontend/src/components/PageHero.vue`、`frontend/src/components/AuthPanel.vue`

---

## PR #7 — feat: improve audio upload and transcription UX

- **作者**：twice-mossa  
- **目标分支**：dev  
- **状态**：已合并  
- **时间**：02:34

**主要内容：**
- 新增本地音频预览功能
- 新增拖拽上传支持
- 将横幅提示改为右上角通知，移除转写超时限制
- 长时间转写任务增加清晰的处理遮罩层
- 修复了 `near_later` 示例音频/文本不匹配的问题

---

## PR #8 — docs: update usage guide for groq transcription workflow

- **作者**：twice-mossa  
- **目标分支**：dev  
- **状态**：已合并  
- **时间**：03:12

**主要内容：**
- 更新运行指南，反映当前生产路径：Groq whisper-large-v3 转写 + MiniMax 摘要 + MySQL 认证
- 更新演示指南，与当前演示流程和措辞保持一致

---

## PR #9 — feat: chunk large wav uploads for groq transcription

- **作者**：twice-mossa  
- **目标分支**：dev  
- **状态**：已合并  
- **时间**：03:21

**主要内容：**
- 上传前检测 Groq 文件大小限制
- 超限时自动将 wav 文件分片，并将转写结果的时间偏移量校正后合并
- 文档说明新增 Groq 上传大小配置项及大文件处理行为

---

## PR #10 — fix: remove prompt leakage from transcripts

- **作者**：twice-mossa  
- **目标分支**：dev  
- **状态**：已合并  
- **时间**：03:45

**主要内容：**
- 修复向 Groq 语音转写请求中意外携带指令 Prompt 的问题
- 过滤转写文本和分段中已知的 Prompt 泄漏内容及广告噪音
- 必要时从清理后的分段重建完整转写文本

---

## PR #11 — feat: show progressive transcription results while chunking

- **作者**：twice-mossa  
- **目标分支**：dev  
- **状态**：已合并  
- **时间**：03:58

**主要内容：**
- 新增后台转写任务及状态轮询接口
- 前端改为启动转写任务并轮询进度
- 在长 wav 文件仍在处理时，按时间顺序将已完成的分片结果追加到转写视图，实现渐进式展示

---

## PR #12 — milestone: promote March 13 demo build to main

- **作者**：twice-mossa  
- **目标分支**：main  
- **状态**：开放中（未合并）  
- **时间**：05:35

**主要内容：**
- 将当前演示就绪的里程碑构建从 dev 分支推进到 main
- 包含以下已通过 dev 合并的功能（PR #7 至 #11）：MySQL 认证、Groq Whisper 转写、MiniMax 摘要、长 wav 分片、转写内容清理、音频预览/拖拽上传、渐进式转写展示

---

## PR #13 — feat: second milestone apple-inspired frontend redesign（→ main）

- **作者**：twice-mossa  
- **目标分支**：main  
- **状态**：开放中（未合并）  
- **时间**：07:02

**主要内容：**
- 以 Apple 视觉风格全面重设计前端界面
- 重新设计 Hero、Auth 和工作区页面，保留现有业务流程不变
- 里程碑功能保持完整可用

---

## PR #14 — feat: second milestone apple-inspired frontend redesign（→ dev）

- **作者**：twice-mossa  
- **目标分支**：dev  
- **状态**：已合并  
- **时间**：07:02

**主要内容：**
- 与 PR #13 内容相同，目标分支为 dev
- Apple 风格前端重设计，已合并入 dev 分支

---

## 总结

| PR  | 类型  | 主要变更           | 状态   |
|-----|-------|--------------------|--------|
| #6  | feat  | 首页 UI 精磨       | 已合并 |
| #7  | feat  | 音频上传与转写体验优化 | 已合并 |
| #8  | docs  | Groq 转写工作流文档更新 | 已合并 |
| #9  | feat  | 大 wav 文件分片转写 | 已合并 |
| #10 | fix   | 修复转写 Prompt 泄漏 | 已合并 |
| #11 | feat  | 渐进式转写进度展示 | 已合并 |
| #12 | milestone | 里程碑推进至 main | 开放中 |
| #13 | feat  | Apple 风格前端重设计（→ main） | 开放中 |
| #14 | feat  | Apple 风格前端重设计（→ dev） | 已合并 |
