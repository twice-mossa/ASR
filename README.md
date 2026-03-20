# ASR Meeting Assistant

一个面向课程项目和团队协作场景的智能会议助手。当前主流程是：

`登录 / 注册 -> 上传音频 -> 语音转写 -> 会议摘要 / 关键词 / 待办生成`

项目目前采用前后端分离架构：

- 前端：`Vue 3` + `Vite` + `Element Plus`
- 后端：`FastAPI`
- 语音识别：`faster-whisper`
- 会议摘要：`MiniMax API`
- 数据存储：`MySQL`

## 1. 项目定位

本项目用于处理会议音频并输出结构化结果，帮助用户快速回顾会议内容。当前阶段的重点不是把所有功能一次做完，而是优先打通一条可演示、可联调的主流程。

当前已经覆盖的核心能力包括：

- 用户注册与登录
- 登录态保持
- 音频上传
- 语音转写
- 会议摘要生成
- 关键词提取
- 待办事项提取

## 2. 当前实现状态

已完成：

- 用户注册
- 用户登录
- 登录态查询
- 用户退出登录
- 音频上传接口
- 基于 `faster-whisper` 的语音转写
- 返回分段时间戳
- 基于 `MiniMax API` 的摘要、关键词、待办生成
- 当 `MiniMax API` 不可用时，使用本地 fallback 逻辑生成基础结果
- 前端工作台页面：上传、转写、纪要展示

未完成或仍在迭代：

- 关键词搜索
- 基于时间戳的音频回放
- 更完整的会议记录持久化
- 完整测试覆盖与异常处理打磨

## 3. 目录结构

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
│  ├─ src/
│  │  ├─ api/                  # 前端接口请求封装
│  │  ├─ components/           # 页面组件
│  │  ├─ App.vue               # 当前主页面
│  │  └─ main.js               # 前端入口
│  ├─ package.json             # 前端依赖与脚本
│  └─ vite.config.js           # 本地开发代理配置
├─ docs/                       # 协作流程、运行说明、路演文档
├─ sample-data/                # 测试音频与预期文本
├─ docker-compose.yml          # 本地 MySQL 启动配置
└─ README.md
```

## 4. 技术栈与依赖管理

### 前端

- 框架：`Vue 3`
- 构建工具：`Vite`
- UI：`Element Plus`
- HTTP 请求：`Axios`
- 依赖管理：`npm`

关键文件：

- [frontend/package.json](/Users/admin/Desktop/ai-project/ASR/frontend/package.json)
- [frontend/vite.config.js](/Users/admin/Desktop/ai-project/ASR/frontend/vite.config.js)
- [frontend/src/main.js](/Users/admin/Desktop/ai-project/ASR/frontend/src/main.js)
- [frontend/src/App.vue](/Users/admin/Desktop/ai-project/ASR/frontend/src/App.vue)

### 后端

- Web 框架：`FastAPI`
- ASGI 服务：`Uvicorn`
- 数据校验：`Pydantic`
- 配置管理：`pydantic-settings`
- 音频上传处理：`python-multipart`
- 语音识别：`faster-whisper`
- 大模型调用：`httpx`
- 数据库：`MySQL`
- 依赖管理：`pip + requirements.txt`

关键文件：

- [backend/requirements.txt](/Users/admin/Desktop/ai-project/ASR/backend/requirements.txt)
- [backend/app/main.py](/Users/admin/Desktop/ai-project/ASR/backend/app/main.py)
- [backend/app/api/routes.py](/Users/admin/Desktop/ai-project/ASR/backend/app/api/routes.py)
- [backend/app/core/database.py](/Users/admin/Desktop/ai-project/ASR/backend/app/core/database.py)
- [backend/app/services/auth_service.py](/Users/admin/Desktop/ai-project/ASR/backend/app/services/auth_service.py)

## 5. 启动方式

### 5.1 启动 MySQL

项目默认使用 `MySQL` 作为用户认证数据库。如果本机没有现成的 MySQL，可以直接用仓库里的 Docker 配置启动：

```bash
docker compose up -d mysql
docker compose ps
```

对应文件：

- [docker-compose.yml](/Users/admin/Desktop/ai-project/ASR/docker-compose.yml)

### 5.2 后端启动

在 [backend](/Users/admin/Desktop/ai-project/ASR/backend) 目录执行：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Windows PowerShell 可使用：

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

默认启动地址：

- API: `http://127.0.0.1:8000`
- 健康检查: `http://127.0.0.1:8000/health`
- Swagger 文档: `http://127.0.0.1:8000/docs`

### 5.3 前端启动

在 [frontend](/Users/admin/Desktop/ai-project/ASR/frontend) 目录执行：

```bash
npm install
npm run dev
```

默认启动地址：

- 前端开发服务: `http://127.0.0.1:5173`

本地开发时，前端会通过 Vite 代理把 `/api` 请求转发到后端 `8000` 端口。

## 6. 环境变量

参考 [backend/.env.example](/Users/admin/Desktop/ai-project/ASR/backend/.env.example)：

```env
MINIMAX_API_KEY=your_api_key_here
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
WHISPER_MODEL_SIZE=large-v3
DATABASE_URL=mysql+mysqlconnector://asr_user:asr_password@127.0.0.1:3307/asr_meeting
```

说明：

- `MINIMAX_API_KEY`：调用摘要接口时使用
- `MINIMAX_BASE_URL`：MiniMax 接口地址
- `WHISPER_MODEL_SIZE`：`faster-whisper` 模型规格
- `DATABASE_URL`：当前默认使用 MySQL

如果未配置 `MINIMAX_API_KEY`，摘要接口会退化为本地规则生成。

## 7. 核心模块说明

### 后端入口

- [backend/app/main.py](/Users/admin/Desktop/ai-project/ASR/backend/app/main.py)

负责：

- 初始化 `FastAPI` 应用
- 配置跨域
- 注册总路由
- 启动时初始化数据库

### 路由层

- [backend/app/api/routes.py](/Users/admin/Desktop/ai-project/ASR/backend/app/api/routes.py)

当前主要接口：

- `GET /api/ping`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `POST /api/transcribe`
- `POST /api/summary`

### 前端主页面

- [frontend/src/App.vue](/Users/admin/Desktop/ai-project/ASR/frontend/src/App.vue)

当前页面包含：

- 登录 / 注册区域
- 音频上传区域
- 转写结果展示
- 会议摘要、关键词、待办展示

## 8. 运行与路演文档

更多说明见：

- [docs/run-guide.md](/Users/admin/Desktop/ai-project/ASR/docs/run-guide.md)
- [docs/demo-guide.md](/Users/admin/Desktop/ai-project/ASR/docs/demo-guide.md)
- [docs/team-workflow.md](/Users/admin/Desktop/ai-project/ASR/docs/team-workflow.md)
- [docs/project-plan.md](/Users/admin/Desktop/ai-project/ASR/docs/project-plan.md)

## 9. 推荐演示流程

1. 注册一个新账号
2. 使用该账号登录
3. 上传一段短音频
4. 点击“开始转写”
5. 等待转写结果返回
6. 点击“生成纪要”
7. 展示摘要、关键词和待办事项

推荐优先使用：

- [sample-data/audio/alimeeting_candidate_near_intro.wav](/Users/admin/Desktop/ai-project/ASR/sample-data/audio/alimeeting_candidate_near_intro.wav)

## 10. 当前代码结构建议

目前前端已经开始拆分组件，但还可以继续往下整理。下一步比较合适的方向是：

1. 继续把工作台区域拆成独立组件
2. 把上传、转写、摘要状态管理从页面里再抽一层
3. 增加错误态、空态和加载态的一致处理
4. 补一轮前后端联调用例
