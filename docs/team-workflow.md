# 三人协作开发流程

## 一、推荐分工

### 成员 A：后端与模型接入

- 搭建 FastAPI
- 接入 `faster-whisper`
- 接入 `MiniMax API`
- 维护接口文档

### 成员 B：前端与交互

- 搭建 Vue 页面
- 实现上传、结果展示、搜索和回放界面
- 对接后端接口

### 成员 C：测试、数据与集成

- 准备测试音频
- 验证识别效果和摘要结果
- 负责联调、Bug 记录和演示材料

## 二、Git 分支规范

- `main`：稳定可演示版本
- `dev`：日常集成分支
- `feature/backend-transcription`
- `feature/frontend-upload`
- `feature/integration-summary`

每个人都不要直接改 `main`，平时从 `dev` 拉自己的 `feature/*` 分支开发。

## 三、每日协作流程

1. 上班前先拉最新代码

```powershell
git checkout dev
git pull origin dev
```

2. 创建自己的功能分支

```powershell
git checkout -b feature/your-task-name
```

3. 完成功能后提交

```powershell
git add .
git commit -m "feat: add transcription api"
git push -u origin feature/your-task-name
```

4. 到 GitHub 发起 Pull Request 合并到 `dev`

5. 另外两人至少一人看过再合并

## 四、提交信息规范

- `feat:` 新功能
- `fix:` 修复问题
- `docs:` 文档更新
- `refactor:` 重构
- `test:` 测试相关

示例：

```text
feat: add meeting summary api
fix: handle empty upload file
docs: add team workflow
```

## 五、三周建议节奏

### 第 1 周

- 搭好前后端骨架
- 跑通音频上传和假数据展示
- 确定接口格式

### 第 2 周

- 接入 `faster-whisper`
- 接入 `MiniMax API`
- 完成前后端联调

### 第 3 周

- 完成关键词搜索和音频回放
- 修复 Bug
- 准备答辩演示和文档

## 六、避免冲突的建议

- 一个人一个功能分支
- 同一个文件不要三个人同时大改
- 改公共接口前先在群里确认
- 每天晚上一轮同步：今天做了什么，明天做什么，卡在哪里
