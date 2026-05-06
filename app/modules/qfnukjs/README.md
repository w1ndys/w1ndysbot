# qfnukjs 功能模块

qfnukjs 是曲阜师范大学空教室查询模块。开启模块群开关后，群消息中包含“空教室”时，会调用空教室 AI 查询接口并将结果回复到群内。

## 使用方式

1. 在模块目录下创建 `.env` 文件。
2. 配置 `QFNUKJS_API_KEY`。
3. 在群内发送 `qfnukjs` 开启或关闭群开关。
4. 群友发送包含“空教室”的自然语言查询，例如：`今天老文史楼第一二节有哪些空教室`。

## 环境变量

参考 `.env.example`：

```bash
QFNUKJS_API_KEY=your-api-key
QFNUKJS_BASE_URL=https://kjs.easy-qfnu.top
```
