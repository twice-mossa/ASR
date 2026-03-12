# 项目使用说明

## 一、今晚启动前你们需要准备什么

### 必需项

- 已安装 `Python 3.10+`
- 已安装 `Node.js`
- 已安装 `Docker Desktop`

### 启动 MySQL 前的提醒

本项目现在默认使用 `MySQL` 作为用户认证数据库。

如果你本机没有 MySQL 服务，也没关系，直接使用仓库根目录的 `docker-compose.yml` 启动即可。

## 二、先启动 Docker Desktop

如果命令行执行 `docker compose up -d mysql` 报错，通常不是代码问题，而是 `Docker Desktop` 没有打开。

请先手动打开 `Docker Desktop`，等待它完全启动后再执行下面命令。

## 三、启动 MySQL

在项目根目录执行：

```powershell
cd D:\ASR
docker compose up -d mysql
docker compose ps
```

正常情况下你会看到 `mysql` 服务正在运行。

## 四、后端配置

后端环境变量文件位置：

- `D:\ASR\backend\.env`

当前默认配置：

```env
MINIMAX_API_KEY=
MINIMAX_BASE_URL=https://api.minimax.chat
WHISPER_MODEL_SIZE=tiny
DATABASE_URL=mysql+pymysql://asr_user:asr_password@127.0.0.1:3306/asr_meeting
```

说明：

- `WHISPER_MODEL_SIZE=tiny` 是为了明天路演更快启动
- `MINIMAX_API_KEY` 为空时，摘要接口会自动走兜底逻辑，项目仍然能演示

## 五、启动后端

```powershell
cd D:\ASR\backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

启动成功后访问：

- `http://127.0.0.1:8000/docs`

## 六、启动前端

```powershell
cd D:\ASR\frontend
npm install
npm run dev
```

启动成功后访问：

- `http://127.0.0.1:5173`

## 七、推荐演示流程

1. 注册一个新账号
2. 使用该账号登录
3. 上传一个短音频
4. 点击“开始转写”
5. 等待转写结果返回
6. 点击“生成纪要”
7. 展示摘要、关键词、待办事项

## 八、推荐演示音频

仓库里已经有可以直接使用的样例：

- `D:\ASR\sample-data\audio\alimeeting_candidate_near_intro.wav`
- `D:\ASR\sample-data\audio\alimeeting_candidate_near_mid.wav`
- `D:\ASR\sample-data\audio\alimeeting_candidate_near_later.wav`

最推荐先用：

- `alimeeting_candidate_near_intro.wav`

因为它短，容易稳定演示。

## 九、常见问题

### 1. Docker 起不来

先确认 `Docker Desktop` 是否真的已启动。

### 2. 没有 MiniMax Key

没关系，摘要功能会自动走兜底逻辑，仍然能演示完整流程。

### 3. Whisper 第一次比较慢

第一次运行会下载模型，这是正常现象。建议今晚先跑一遍，明天再演示就会更稳。
