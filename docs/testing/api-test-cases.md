# API 测试用例

由成员 C 维护，随着后端接口完善逐步补充。

## 1. 健康检查

- 接口：`GET /health`
- 预期：返回 `status=ok`

## 2. Ping

- 接口：`GET /api/ping`
- 预期：返回 `message=pong`

## 3. 转写接口

- 接口：`POST /api/transcribe`
- 输入：音频文件
- 预期：
  - 返回文件名
  - 返回文本
  - 返回 `segments`
  - `segments` 中包含 `start`、`end`、`text`

### 异常情况

- 不上传文件
- 上传空文件
- 上传非音频文件

## 4. 摘要接口

- 接口：`POST /api/summary`
- 输入：转写结果 JSON
- 预期：
  - 返回 `summary`
  - 返回 `keywords`
  - 返回 `todos`

## 5. 会议记录接口

- 接口：`POST /api/meetings`
- 输入：认证信息 + 音频文件 + 文件名 + 时长
- 预期：
  - 返回 `id`
  - 返回 `status=draft`
  - 返回 `audio_url`

## 6. 历史会议列表

- 接口：`GET /api/meetings`
- 预期：
  - 仅返回当前登录用户自己的会议
  - 返回 `id`、`title`、`status`、`preview`、`updated_at`

## 7. 会议详情

- 接口：`GET /api/meetings/{meeting_id}`
- 预期：
  - 返回会议基本信息
  - 返回转录结果和摘要结果
  - 未授权或跨用户访问时不能读到他人会议
