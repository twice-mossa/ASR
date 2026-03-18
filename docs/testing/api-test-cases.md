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
  - 返回 `action_items`
