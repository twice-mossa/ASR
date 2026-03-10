# 测试样例数据说明

这个目录由成员 C 维护，用于放置测试音频和对应的预期结果。

## 目录说明

- `audio/`：测试音频文件
- `expected/`：预期结果说明、人工整理文本、关键词参考

## 推荐样例

至少准备以下 4 类测试音频：

1. `short-clear.wav`
   - 20 到 40 秒
   - 单人普通话
   - 环境安静

2. `meeting-multi-speaker.wav`
   - 1 到 3 分钟
   - 多人讨论
   - 模拟真实会议

3. `noisy-room.wav`
   - 带少量噪声
   - 验证识别鲁棒性

4. `keyword-demo.wav`
   - 人工包含几个明确关键词
   - 用于搜索和回放演示

## 命名建议

- 音频文件统一小写英文命名
- 预期文本文件与音频同名，例如：
  - `audio/short-clear.wav`
  - `expected/short-clear.txt`
