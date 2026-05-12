import os


MODULE_NAME = "ISCCSubmit"
MODULE_ENABLED = True
SWITCH_NAME = "iscc"
MODULE_DESCRIPTION = "ISCC 平台自动提交 flag 模块，支持私聊配置账号和并发提交未解题目"

DATA_DIR = os.path.join("data", MODULE_NAME)
os.makedirs(DATA_DIR, exist_ok=True)

BASE_URL = "https://iscc.isclab.org.cn"
CONFIG_COMMAND = "iscc配置"
HELP_COMMAND = "iscc帮助"
SESSION_COMMAND = "isccsession"
NONCE_COMMAND = "isccnonce"
FLAG_PATTERN = r"^ISCC\{.+\}$"

# 每日自动刷新 session 的北京时间（24 小时制）
DAILY_REFRESH_HOUR = 7
DAILY_REFRESH_MINUTE = 50

COMMANDS = {
    SWITCH_NAME: "系统管理员开关 ISCC 自动提交模块",
    CONFIG_COMMAND: "配置 ISCC 账号，用法：iscc配置 <账号> <密码>",
    "ISCC{xxxxx}": "提交 flag 到 ISCC 平台未解题目",
    SESSION_COMMAND: "查询当前 ISCC session",
    NONCE_COMMAND: "查询当前 ISCC 练武题和擂台题 nonce",
    HELP_COMMAND: "查看 ISCC 自动提交帮助",
}
