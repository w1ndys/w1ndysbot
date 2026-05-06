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

[模块动态加载与模块模板约定]
- Date: 2026-05-06
- Context: Agent 在执行新增 qfnukjs 空教室查询模块任务时发现
- Category: 代码结构
- Instructions:
  - `app/handle_events.py` 会动态加载 `app/modules/*/main.py`，模块需要在 `__init__.py` 中声明 `MODULE_ENABLED`、`MODULE_NAME`、`SWITCH_NAME` 等元信息。
  - 群开关命令通常在模块的 `handlers/handle_message_group.py` 内处理，使用 `handle_module_group_switch` 和 `is_group_switch_on` 控制模块是否响应群消息。
  - 模块菜单命令通过 `SWITCH_NAME + MENU_COMMAND` 触发，并由 `MenuManager.get_module_commands_text(MODULE_NAME)` 生成说明文本。
