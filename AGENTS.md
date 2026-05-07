# AGENTS.md

## NapCat WebSocket 响应处理约定

本项目通过 WebSocket 长连接与 NapCat 通信。发送请求后，调用方无法像普通 HTTP 调用一样同步拿到该请求的响应结果；NapCat 的响应会作为后续 WebSocket 消息异步返回。

因此，所有依赖 NapCat 响应数据的功能设计都必须遵循以下约定：

- 在发送请求时，通过 `echo` 添加可识别的特殊标记。
- 特殊标记应包含模块名、功能名和必要的业务关联 ID，避免与其他模块或请求冲突。
- 在模块的 `ResponseHandler` 中解析 `echo`，只处理属于当前模块和当前功能的响应。
- 需要从响应中读取的数据，例如 `data.message_id`，必须在 `ResponseHandler` 中捕获。
- 如果后续流程依赖响应数据，应使用模块级状态表、持久化记录或等价机制保存请求标记与业务上下文的映射。
- 不要假设 `send_group_msg`、`send_private_msg`、`get_msg` 等 API 调用会同步返回 NapCat 响应结果。

推荐 echo 格式：

```text
<action>-<module>_<feature>=<request_id>
```

示例：

```text
send_group_msg-qfnukjs_empty_classroom_pending=abc123
```

对应处理方式：

```python
marker = "send_group_msg-qfnukjs_empty_classroom_pending="
if echo.startswith(marker):
    request_id = echo[len(marker):]
    message_id = data.get("message_id")
```

设计异步响应流程时，应同时考虑响应先于业务完成、业务先于响应完成、响应缺失或响应失败等情况。
