# 用户指令记忆

本文件记录了用户的指令、偏好和教导，用于在未来的交互中提供参考。

## 格式

### 用户指令条目
用户指令条目应遵循以下格式：

[用户指令摘要]
- Date: [YYYY-MM-DD]
- Context: [提及的场景或时间]
- Instructions:
  - [用户教导或指示的内容，逐行描述]

### 项目知识条目
Agent 在任务执行过程中发现的条目应遵循以下格式：

[项目知识摘要]
- Date: [YYYY-MM-DD]
- Context: Agent 在执行 [具体任务描述] 时发现
- Category: [代码结构|代码模式|代码生成|构建方法|测试方法|依赖关系|环境配置]
- Instructions:
  - [具体的知识点，逐行描述]

## 去重策略
- 添加新条目前，检查是否存在相似或相同的指令
- 若发现重复，跳过新条目或与已有条目合并
- 合并时，更新上下文或日期信息
- 这有助于避免冗余条目，保持记忆文件整洁

## 条目

[NapCat WebSocket 响应 echo 捕获约定]
- Date: 2026-05-07
- Context: 用户要求将 echo 处理逻辑固化到根目录 AGENTS.md
- Instructions:
  - WebSocket 长连接无法实时获取请求响应；对于依赖 NapCat 响应的功能设计，需要在请求 `echo` 中添加模块化特殊标记。
  - 模块的 `ResponseHandler` 应根据特殊 `echo` 标记捕获对应响应，并从响应 `data` 中读取需要的字段，例如 `message_id`。
  - 依赖响应结果的异步流程应使用本地状态表或等价机制关联请求标记和后续处理，避免假设发送 API 会同步返回结果。

[模块动态加载与模块模板约定]
- Date: 2026-05-06
- Context: Agent 在执行新增 qfnukjs 空教室查询模块任务时发现
- Category: 代码结构
- Instructions:
  - `app/handle_events.py` 会动态加载 `app/modules/*/main.py`，模块需要在 `__init__.py` 中声明 `MODULE_ENABLED`、`MODULE_NAME`、`SWITCH_NAME` 等元信息。
  - 群开关命令通常在模块的 `handlers/handle_message_group.py` 内处理，使用 `handle_module_group_switch` 和 `is_group_switch_on` 控制模块是否响应群消息。
  - 模块菜单命令通过 `SWITCH_NAME + MENU_COMMAND` 触发，并由 `MenuManager.get_module_commands_text(MODULE_NAME)` 生成说明文本。
