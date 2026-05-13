import os


# 模块名称
MODULE_NAME = "qfnukjs"


# 模块是否启用（默认开启）
MODULE_ENABLED = True
# 模块开关名称
SWITCH_NAME = "qfnukjs"

# 模块描述
MODULE_DESCRIPTION = "曲阜师范大学空教室查询模块，群消息包含“空教室”时自动调用 AI 查询接口"

# 数据目录
DATA_DIR = os.path.join("data", MODULE_NAME)
os.makedirs(DATA_DIR, exist_ok=True)

# 模块命令说明
# ------------------------------------------------------------
COMMANDS = {
    "消息包含空教室": "自动调用曲阜师范大学空教室 AI 查询接口并返回查询结果",
    "qfnukjs定时空教室教学楼": "查看本群每日定时推送的教学楼列表",
    "qfnukjs定时空教室教学楼 教学楼1 教学楼2": "配置本群每日 7:30 定时推送的教学楼列表，仅系统管理员可用",
    "qfnukjs定时空教室状态": "查看本群定时空教室推送开关、教学楼配置和今日提醒状态",
}
# ------------------------------------------------------------
