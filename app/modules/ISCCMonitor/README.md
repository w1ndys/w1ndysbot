# ISCCMonitor 功能模块

基于 NapCat 心跳事件定时抓取 ISCC 擂台赛指定参赛者的解题详情，发现新通过题目时私聊通知管理员。

## 功能概览

- 支持新增、删除、查看监控的 `team_id`（对应 ISCC 平台 `/teamarena/<team_id>` 页面）。
- 每次心跳触发一次（最小 60 秒间隔节流、同一时刻最多一个轮询）。
- 目前只监控**擂台题**，练武题暂不包含。
- 新提交会通过系统管理员私聊发送：监控对象、当前队名、新通过的题目名 / 分类 / 得分 / 通过时间。
- 可选配置 `session`，用于访问需要登录的 ISCC 页面。

## 命令

所有命令仅在**系统管理员**（`OWNER_ID`）的私聊中生效。

| 命令 | 说明 |
| --- | --- |
| `isccm` | 开关模块（私聊模式） |
| `isccm菜单` | 查看模块命令菜单 |
| `isccm帮助` | 查看模块帮助 |
| `isccm添加 <team_id> [备注]` | 新增监控目标 |
| `isccm删除 <team_id>` | 删除监控目标，并清除其历史提交记录 |
| `isccm列表` | 查看当前监控的 team 列表与 session 状态 |
| `isccmsession <session>` | 设置（或查询）抓取时使用的 session |
| `isccm检测` | 立即触发一次监控轮询，并返回统计结果 |

## 数据

- 数据目录：`data/ISCCMonitor/`
- SQLite 表：
  - `iscc_monitor_target`：监控目标
  - `iscc_monitor_submit`：已知的通过记录（`team_id` + 赛道 + 题目名 唯一）
  - `iscc_monitor_meta`：模块级 k/v 配置（例如 session）

## 注意事项

- 模块默认开启，但需要管理员私聊发送 `isccm` 打开私聊开关后才会执行心跳轮询。
- 第一次抓取新 `team_id` 时会将当前页面所有通过记录当作基线，不会额外推送历史数据。
- 页面解析基于 `/teamarena/<team_id>` 返回的 HTML；若 ISCC 后续页面结构变化，需要同步调整 `iscc_monitor_client.py`。
