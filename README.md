# ASR Meeting Assistant

一个面向会议录音整理场景的智能会议助手。当前项目已经从“上传后展示结果”的 Demo，迭代成了一个可演示、可联调的 AI 工作台：

`登录 / 注册 -> 上传音频并创建会议 -> 异步转录 -> 生成摘要 / 关键词 / 待办 -> 历史会议可恢复 -> 导出会议纪要`

项目采用前后端分离架构：

- 前端：`Vue 3` + `Vite` + `Element Plus`
- 后端：`FastAPI`
- 语音识别：`Groq Whisper API (whisper-large-v3)`，本地 `faster-whisper` 作为 fallback
- 会议摘要：`MiniMax API`
- 数据存储：`MySQL`

## 1. 项目现状

### 当前已经完成的核心能力

- 用户注册、登录、退出登录
- 登录态保持与当前用户查询
- 音频上传与基础文件类型校验
- 基于异步 Job 的音频转录
- 返回完整转录文本和分段时间戳
- 基于 `MiniMax API` 生成会议摘要、关键词和待办事项
- 转录默认优先使用 `Groq whisper-large-v3`
- 摘要接口不可用时的本地 fallback
- ChatGPT 风格的前端双栏工作台
- 左侧历史会议切换
- 右侧聊天式消息流展示
- 登录弹窗按需拦截，而不是首屏强制遮挡
- 当前音频播放器悬浮条
- 会议纪要 Markdown 导出
- 会议记录、转录结果、摘要结果后端持久化
- 刷新页面后恢复历史会议
- 前端 `App.vue` 的业务逻辑已拆分到 composables

### 当前产品形态

前端已不是传统表单页，而是一个聊天式音频分析工作台：

- 左侧：历史会话列表
- 右侧：当前会话消息流
- 顶部：当前音频状态与上下文
- 底部：上传、转录、生成摘要、继续提问的统一输入区

更适合后续接入：

- 基于当前音频内容的问答
- RAG 检索引用
- 思考过程展示
- 多用户会议记录管理扩展

## 2. 当前能力边界

### 已完成

- 认证主流程可用
- 音频上传、异步转录、摘要生成主流程可用
- 前后端联调已经打通
- 可使用真实音频进行演示
- 历史会议切换时可恢复当前工作区状态
- 已支持导出 Markdown 会议纪要
- 历史会议已持久化到后端

### 仍是占位或未完成

- 真正的 RAG 问答接口
- 可追溯的引用片段与来源卡片
- 思考过程的真实后端输出
- 说话人区分与多人发言标注
- 更完整的会议管理操作（删除、重命名、搜索）
- 音频波形可视化与时间戳联动回放
- 更系统的自动化测试和异常恢复机制

## 3. 适合演示的主流程

1. 注册或登录账号
2. 上传一段会议音频
3. 点击“开始转录”
4. 等待异步转录完成
5. 查看转录全文和分段
6. 点击“生成摘要”
7. 展示摘要、关键词、待办事项
8. 下载 Markdown 会议纪要

推荐演示音频：

- [sample-data/audio/alimeeting_candidate_near_intro.wav](/Users/admin/Desktop/ai-project/ASR/sample-data/audio/alimeeting_candidate_near_intro.wav)

## 4. 目录结构

```text
ASR/
├─ backend/
│  ├─ app/
│  │  ├─ api/                  # 路由层
│  │  ├─ core/                 # 配置与数据库初始化
│  │  ├─ schemas/              # 请求/响应数据结构
│  │  ├─ services/             # 认证、转写、摘要服务
│  │  └─ models.py             # 数据模型
│  ├─ .env.example             # 后端环境变量示例
│  └─ requirements.txt         # 后端依赖
├─ frontend/
│  ├─ public/
│  ├─ src/
│  │  ├─ api/                  # 前端接口封装
│  │  ├─ components/           # UI 组件
│  │  ├─ composables/          # 页面业务逻辑拆分
│  │  ├─ styles/               # 全局主题样式
│  │  ├─ utils/                # 纯工具函数
│  │  ├─ App.vue               # 页面装配层
│  │  └─ main.js               # 前端入口
│  ├─ package.json
│  └─ vite.config.js
├─ docs/                       # 运行说明、联调和协作文档
├─ sample-data/                # 测试音频与预期文本
├─ docker-compose.yml          # 本地 MySQL 启动配置
└─ README.md
```

## 5. 技术栈

### 前端

- `Vue 3`
- `Vite`
- `Element Plus`
- `Axios`

前端关键文件：

- [frontend/src/App.vue](/Users/admin/Desktop/ai-project/ASR/frontend/src/App.vue)
- [frontend/src/composables/useAuthSession.js](/Users/admin/Desktop/ai-project/ASR/frontend/src/composables/useAuthSession.js)
- [frontend/src/composables/useConversationWorkspace.js](/Users/admin/Desktop/ai-project/ASR/frontend/src/composables/useConversationWorkspace.js)
- [frontend/src/composables/useAudioFileContext.js](/Users/admin/Desktop/ai-project/ASR/frontend/src/composables/useAudioFileContext.js)
- [frontend/src/composables/useMeetingWorkflow.js](/Users/admin/Desktop/ai-project/ASR/frontend/src/composables/useMeetingWorkflow.js)

### 后端

- `FastAPI`
- `Uvicorn`
- `Pydantic`
- `Groq Whisper API`
- `faster-whisper` fallback
- `httpx`
- `MySQL`

后端关键文件：

- [backend/app/main.py](/Users/admin/Desktop/ai-project/ASR/backend/app/main.py)
- [backend/app/api/routes.py](/Users/admin/Desktop/ai-project/ASR/backend/app/api/routes.py)
- [backend/app/services/transcription_service.py](/Users/admin/Desktop/ai-project/ASR/backend/app/services/transcription_service.py)
- [backend/app/services/minimax_service.py](/Users/admin/Desktop/ai-project/ASR/backend/app/services/minimax_service.py)
- [backend/app/services/auth_service.py](/Users/admin/Desktop/ai-project/ASR/backend/app/services/auth_service.py)

## 6. 已有接口

当前已经可用的核心接口：

- `GET /api/ping`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `POST /api/meetings`
- `GET /api/meetings`
- `GET /api/meetings/{meeting_id}`
- `POST /api/transcribe`
- `POST /api/transcribe/jobs`
- `POST /api/meetings/{meeting_id}/transcribe`
- `GET /api/transcribe/jobs/{job_id}`
- `POST /api/summary`

前端目前实际对接的是：

- [frontend/src/api/auth.js](/Users/admin/Desktop/ai-project/ASR/frontend/src/api/auth.js)
- [frontend/src/api/meeting.js](/Users/admin/Desktop/ai-project/ASR/frontend/src/api/meeting.js)

## 7. 本地启动

### 7.1 启动 MySQL

```bash
docker compose up -d mysql
docker compose ps
```

对应文件：

- [docker-compose.yml](/Users/admin/Desktop/ai-project/ASR/docker-compose.yml)

### 7.2 启动后端

推荐使用 `conda` 的 `py310` 环境：

在 [backend](/Users/admin/Desktop/ai-project/ASR/backend) 目录执行：

```bash
conda activate py310
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

默认地址：

- API: `http://127.0.0.1:8000`
- 健康检查: `http://127.0.0.1:8000/health`
- Swagger: `http://127.0.0.1:8000/docs`

### 7.3 启动前端

前提：本机已安装 `Node.js`。

在 [frontend](/Users/admin/Desktop/ai-project/ASR/frontend) 目录执行：

```bash
npm install
npm run dev
```

默认地址：

- 前端开发服务: `http://127.0.0.1:5173`

本地开发时，Vite 会通过代理将 `/api` 转发到后端 `8000` 端口。

## 8. 环境变量

参考 [backend/.env.example](/Users/admin/Desktop/ai-project/ASR/backend/.env.example)：

```env
MINIMAX_API_KEY=your_api_key_here
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
GROQ_API_KEY=your_groq_api_key_here
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_TRANSCRIPTION_MODEL=whisper-large-v3
GROQ_MAX_UPLOAD_MB=24
WHISPER_MODEL_SIZE=large-v3
DATABASE_URL=mysql+mysqlconnector://asr_user:asr_password@127.0.0.1:3307/asr_meeting
UPLOAD_DIR=./data/uploads
```

说明：

- `MINIMAX_API_KEY`：摘要、关键词、待办生成使用
- `GROQ_API_KEY`：Groq 转录接口使用
- `GROQ_BASE_URL`：Groq 接口地址
- `GROQ_TRANSCRIPTION_MODEL`：当前默认推荐 `whisper-large-v3`
- `GROQ_MAX_UPLOAD_MB`：单次上传大小阈值，超过后端会按策略处理
- `MINIMAX_BASE_URL`：MiniMax 接口地址
- `WHISPER_MODEL_SIZE`：本地 fallback 的 `faster-whisper` 模型大小
- `DATABASE_URL`：用户和会议记录数据库连接
- `UPLOAD_DIR`：本地音频持久化目录

如果未配置 `GROQ_API_KEY`，转录会退化为本地 `faster-whisper`。

如果未配置 `MINIMAX_API_KEY`，摘要接口会退化为本地 fallback 逻辑。

## 9. 接下来最值得继续做的功能

这一部分建议按“先打通可用性，再做高级能力”的顺序推进。

### 第一优先级：把持久化数据用起来

- 基于已保存的会议记录接入真正的多轮问答接口
- 给回答补上引用片段与时间戳来源
- 增加会议重命名、删除、搜索和筛选

### 第二优先级：补齐 AI 产品能力

- 基于当前音频内容的多轮问答接口
- RAG 检索与引用片段返回
- 回答中展示引用来源和时间戳
- 思考过程接口或阶段化推理输出
- 说话人区分能力，支持一段音频中的不同发言人标注
- 在摘要、待办和问答中引用“谁说了什么”

### 第三优先级：提升交付感

- 音频波形展示
- 时间戳点击回放
- 纪要导出增加 `PDF` 或 `DOCX`
- 更完善的错误提示、空态和加载态
- 会话重命名、删除、搜索

### 第四优先级：工程质量

- 后端接口测试
- 前端组件测试与关键流程测试
- 联调用例文档和验收清单持续更新
- 更明确的错误码和前后端异常约定

## 10. 前后端如何继续协作开发

这一块很关键。后续如果前后端同时推进，建议统一按“先接口契约，再并行开发”的方式做。

### 协作原则

- 前端先提出页面交互和需要的数据结构
- 后端确认接口路径、字段、状态流和错误码
- 双方先冻结最小接口协议，再开始编码
- 不要在联调阶段临时随意改字段名

### 推荐协作顺序

1. 产品或前端先定义用户流程
2. 前后端一起确定接口输入输出
3. 后端先给 Swagger 或接口样例
4. 前端先用 mock 数据把页面跑通
5. 后端实现真实接口
6. 双方联调并记录差异
7. 用测试音频做验收

### 对下一阶段最重要的接口建议

如果下一步要做音频问答，建议优先新增这几类接口：

- `POST /api/meetings/{meeting_id}/ask`
- `GET /api/meetings/{meeting_id}/messages`
- `GET /api/meetings/{meeting_id}/sources`

建议返回结构至少包含：

- 会话基本信息：`id`、`title`、`created_at`、`updated_at`
- 当前音频信息：`file_name`、`duration`、`language`
- 转录结果：`text`、`segments`
- 说话人信息：`speaker_id`、`speaker_label`
- 摘要结果：`summary`、`keywords`、`todos`
- 问答消息流：`role`、`kind`、`text`、`sources`

### 建议前端负责的内容

- 工作台交互和页面状态管理
- 组件层抽象和消息流渲染
- 上传、转录、摘要、问答的用户路径
- 空态、错误态、加载态体验

### 建议后端负责的内容

- 认证和会话权限
- 音频文件存储与会话持久化
- 转录任务调度和状态管理
- 说话人分离或 diarization 能力
- 摘要、关键词、待办生成
- RAG 检索、问答和引用结果

### 联调时要提前说清的点

- 异步任务状态字段叫什么
- Job 轮询频率是否有限制
- 转录和问答失败时返回什么错误格式
- 说话人字段是在 `segments` 上返回，还是单独返回 speaker timeline
- 音频文件是本地路径、数据库记录还是对象存储 URL
- 会话删除后是否同时清理音频和中间结果

## 11. 分支与合并建议

当前仓库适合使用：

- `dev`：日常集成分支
- `main`：稳定版本或对外展示版本
- `feature/*` 或 `codex/*`：单次功能开发分支

推荐流程：

1. 从 `dev` 拉功能分支
2. 功能开发完成后提交 PR 到 `dev`
3. `dev` 验证稳定后，再发 PR 合并到 `main`

如果团队决定继续采用“`dev` 作为默认分支”的模式，这是合理的，前提是：

- `dev` 承担日常开发集成
- `main` 只承担稳定发布

## 12. 相关文档

更多说明见：

- [docs/run-guide.md](/Users/admin/Desktop/ai-project/ASR/docs/run-guide.md)
- [docs/demo-guide.md](/Users/admin/Desktop/ai-project/ASR/docs/demo-guide.md)
- [docs/team-workflow.md](/Users/admin/Desktop/ai-project/ASR/docs/team-workflow.md)
- [docs/project-plan.md](/Users/admin/Desktop/ai-project/ASR/docs/project-plan.md)
- [docs/testing/api-test-cases.md](/Users/admin/Desktop/ai-project/ASR/docs/testing/api-test-cases.md)
- [docs/testing/acceptance-checklist.md](/Users/admin/Desktop/ai-project/ASR/docs/testing/acceptance-checklist.md)

## 13. 一句话总结

当前项目已经完成“认证 + 音频上传 + 异步转录 + 结构化纪要生成 + 聊天式工作台展示”的主流程，下一阶段最值得投入的是“历史会话持久化 + 基于音频内容的问答能力 + 说话人区分 + 更规范的前后端协作接口”。
