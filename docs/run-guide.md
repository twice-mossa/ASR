# 项目使用说明

## 一、当前系统实际使用的能力

- 用户认证：`MySQL`
- 语音转录：`Groq API + whisper-large-v3`
- 会议摘要：`MiniMax API`
- 前端：`Vue 3 + Vite`
- 后端：`FastAPI`

说明：

- 现在转录默认优先走 `Groq`，不再依赖本地 `faster-whisper` 的推理速度
- 如果 `GROQ_API_KEY` 为空，后端才会回退到本地 `faster-whisper`
- 如果 `MINIMAX_API_KEY` 为空，摘要接口会回退到兜底逻辑

## 二、启动前准备

必需项：

- 已安装 `Python 3.10+`
- 已安装 `Node.js`
- 已安装 `Docker Desktop`

## 三、先启动 MySQL

如果你本机不想直接连已有 MySQL，就按项目默认方式启动 Docker 容器：

```powershell
cd D:\ASR
docker compose up -d mysql
docker compose ps
```

如果命令报错 `dockerDesktopLinuxEngine` 不存在，说明 `Docker Desktop` 没启动。

## 四、检查后端环境变量

配置文件位置：

- [backend/.env](D:/ASR/backend/.env)

至少要确认这些值存在：

```env
MINIMAX_API_KEY=你的 MiniMax Key
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
GROQ_API_KEY=你的 Groq Key
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_TRANSCRIPTION_MODEL=whisper-large-v3
DATABASE_URL=mysql+mysqlconnector://asr_user:asr_password@127.0.0.1:3307/asr_meeting
```

说明：

- `GROQ_TRANSCRIPTION_MODEL` 推荐保持 `whisper-large-v3`
- 现在网页端长音频转写不会再被前端 2 分钟超时提前中断

## 五、启动后端

```powershell
cd D:\ASR\backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

启动成功后访问：

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

如果你刚改过 `.env`，一定要重启后端。

## 六、启动前端

```powershell
cd D:\ASR\frontend
npm install
npm run dev
```

启动成功后访问：

- [http://127.0.0.1:5173](http://127.0.0.1:5173)

## 七、页面使用流程

1. 注册账号
2. 登录进入工作区
3. 选择音频文件，或者直接拖拽音频到上传区域
4. 可先在页面内播放音频，确认内容正确
5. 点击“开始转写”
6. 等待 Groq 返回转写结果
7. 点击“生成纪要”
8. 查看摘要、关键词和待办事项

## 八、推荐演示音频

样例文件位置：

- [alimeeting_candidate_near_intro.wav](D:/ASR/sample-data/audio/alimeeting_candidate_near_intro.wav)
- [alimeeting_candidate_near_mid.wav](D:/ASR/sample-data/audio/alimeeting_candidate_near_mid.wav)
- [alimeeting_candidate_near_later.wav](D:/ASR/sample-data/audio/alimeeting_candidate_near_later.wav)

最稳的是：

- `alimeeting_candidate_near_intro.wav`

原因：

- 时长短
- 中文清晰
- 返回速度快

## 九、常见问题

### 1. 前端能开，后端接口报错

先检查后端是否已经重启，并确认 [backend/.env](D:/ASR/backend/.env) 里的 `GROQ_API_KEY` 和 `MINIMAX_API_KEY` 有效。

### 2. Docker 起不来

先确认 `Docker Desktop` 是否启动。

### 3. 转写很久没返回

长音频本身就需要更多时间。现在转录走的是在线 `Groq whisper-large-v3`，前端不会再因为 2 分钟超时直接报错。

### 4. 页面显示在转写中

这是正常状态。现在页面允许你在转写过程中继续操作音频播放器，但不要重复提交同一个文件。
