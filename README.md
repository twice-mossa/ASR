# ASR Meeting Assistant

三人协作开发的智能会议助手项目骨架。

## 技术选型

- 语音识别：`faster-whisper`
- 文本摘要与关键词提取：`MiniMax API`
- 后端：`FastAPI`
- 前端：`Vue 3`
- 存储：`SQLite`

## 目录结构

```text
ASR/
├─ backend/              # FastAPI 后端
├─ frontend/             # Vue 前端
├─ docs/                 # 协作规范、开发计划、接口说明
├─ .gitignore
└─ README.md
```

## 快速开始

### 1. 初始化 Git 仓库

```powershell
git init
git branch -M main
```

### 2. 后端

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 3. 前端

```powershell
cd frontend
npm install
npm run dev
```

## 当前阶段目标

第一阶段先完成四个核心功能：

1. 上传或录入会议音频
2. 语音转文字
3. 调用 MiniMax 生成会议纪要和关键词
4. 关键词搜索与时间戳回放

详细协作流程见 [docs/team-workflow.md](/D:/ASR/docs/team-workflow.md)。
