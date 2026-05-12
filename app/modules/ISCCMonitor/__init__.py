import os


# 模块名称
MODULE_NAME = "ISCCMonitor"


# 模块是否启用（默认开启）
MODULE_ENABLED = True
# 模块开关名称（管理员私聊发送此命令开关模块）
SWITCH_NAME = "isccm"


# 模块描述
MODULE_DESCRIPTION = "ISCC 擂台赛提交监控：基于心跳定时抓取指定 team id 的擂台赛解题详情，有新提交时上报给管理员"

# 数据目录
DATA_DIR = os.path.join("data", MODULE_NAME)
os.makedirs(DATA_DIR, exist_ok=True)


# ISCC 平台地址
BASE_URL = "https://iscc.isclab.org.cn"


# ------------------------------------------------------------
# 模块命令定义
# ------------------------------------------------------------

# 添加监控的 team id，用法：isccm添加 <team_id> [备注]
ADD_COMMAND = "isccm添加"
# 删除监控的 team id，用法：isccm删除 <team_id>
REMOVE_COMMAND = "isccm删除"
# 查看当前监控的 team id 列表
LIST_COMMAND = "isccm列表"
# 配置监控所用 session（可选，用于访问需要登录的页面）
SESSION_COMMAND = "isccmsession"
# 手动触发一次监控轮询
CHECK_COMMAND = "isccm检测"
# 模块帮助
HELP_COMMAND = "isccm帮助"


COMMANDS = {
    SWITCH_NAME: "系统管理员开关 ISCC 擂台赛监控模块",
    ADD_COMMAND: "添加监控的 team id，用法：isccm添加 <team_id> [备注]",
    REMOVE_COMMAND: "删除监控的 team id，用法：isccm删除 <team_id>",
    LIST_COMMAND: "查看当前监控的 team id 列表",
    SESSION_COMMAND: "设置监控所用 session，用法：isccmsession <session>",
    CHECK_COMMAND: "立即手动触发一次监控轮询",
    HELP_COMMAND: "查看 ISCC 擂台赛监控模块帮助",
}
