# 五人协作开发流程

## 角色构成

- 项目经理 1 人
- 产品经理 1 人
- 开发成员 3 人

## 一、推荐分工

### 项目经理：进度推进与协作管理

- 制定三周排期和每日目标
- 主持每日 10 分钟站会
- 跟踪每个人任务进度和风险
- 维护 GitHub Issue、看板和里程碑
- 负责答辩时间安排、材料汇总和最终版本把控

### 产品经理：需求设计与验收

- 明确核心功能范围，防止项目做散
- 产出页面草图、功能流程和字段说明
- 定义“什么叫完成”，负责功能验收
- 整理用户视角的使用流程和演示脚本
- 配合准备项目介绍、创新点和展示文案

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

## 三、GitHub 初始化步骤

1. 由队长在 GitHub 上新建一个空仓库，例如 `asr-meeting-assistant`
2. 不要勾选自动生成 `README`、`.gitignore` 或 license，保持空仓库
3. 在本地项目根目录执行：

```powershell
git checkout main
git remote add origin https://github.com/你的用户名/asr-meeting-assistant.git
git push -u origin main
git checkout dev
git push -u origin dev
```

4. 到 GitHub 仓库页面，把默认分支改成 `dev`
5. 在 GitHub 仓库 `Settings -> Collaborators` 中邀请另外两名队员
6. 仓库保护建议：
   - `main` 设为保护分支，不允许直接 push
   - `dev` 尽量通过 Pull Request 合并
   - 合并前至少一人查看代码

## 四、每日协作流程

每天建议由项目经理主持一次 10 分钟同步，按这个顺序：

1. 产品经理确认今天优先级
2. 三位开发分别汇报昨天完成内容、今天计划、当前阻塞
3. 项目经理更新任务状态和风险
4. 晚上统一决定是否可以合并到 `dev`

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

## 五、提交信息规范

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

## 六、三周建议节奏

### 第 1 周

- 搭好前后端骨架
- 跑通音频上传和假数据展示
- 确定接口格式
- 产品经理完成页面流程和核心需求冻结
- 项目经理搭建任务看板并拆分 Issue

### 第 2 周

- 接入 `faster-whisper`
- 接入 `MiniMax API`
- 完成前后端联调
- 产品经理进行第一轮功能验收
- 项目经理跟踪延期风险和联调安排

### 第 3 周

- 完成关键词搜索和音频回放
- 修复 Bug
- 准备答辩演示和文档
- 产品经理整理演示脚本和项目卖点
- 项目经理汇总最终材料并组织彩排

## 七、避免冲突的建议

- 一个人一个功能分支
- 同一个文件不要三个人同时大改
- 改公共接口前先在群里确认
- 每天晚上一轮同步：今天做了什么，明天做什么，卡在哪里

## 八、五人第一天就按这个做

### 队长

- 创建 GitHub 仓库
- 推送 `main` 和 `dev`
- 邀请成员
- 建立一个项目群，统一同步任务

### 项目经理

- 建一个 GitHub Projects 看板
- 建立三周里程碑
- 把任务拆成 Issue 并分配负责人
- 每天固定一个同步时间

### 产品经理

- 先写一页功能清单，只保留四个核心功能
- 画出最小页面流程：上传 -> 转写 -> 摘要 -> 搜索/回放
- 给出每个页面要显示什么内容
- 明确验收标准，避免后期反复改需求

### 成员 A

- 从 `dev` 拉 `feature/backend-transcription`
- 先把 `/api/transcribe` 接成真实逻辑

### 成员 B

- 从 `dev` 拉 `feature/frontend-upload`
- 先做上传页面和结果展示页面

### 成员 C

- 从 `dev` 拉 `feature/testing-docs`
- 准备测试音频、记录接口格式、维护联调文档

## 九、项目经理和产品经理不要空转

### 项目经理每天必须产出

- 一个更新后的任务面板
- 一个风险列表
- 一个第二天安排

### 产品经理每天必须产出

- 一个功能确认结果
- 一个页面或流程说明
- 一个验收记录或修改建议
