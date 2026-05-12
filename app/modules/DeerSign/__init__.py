import os


MODULE_NAME = "DeerSign"
MODULE_ENABLED = True
SWITCH_NAME = "鹿管"
MODULE_DESCRIPTION = "鹿管签到模块，支持按月签到、补签、代签、日历和排行榜"

DATA_DIR = os.path.join("data", MODULE_NAME)
os.makedirs(DATA_DIR, exist_ok=True)

SIGN_COMMAND = "鹿"
MAKEUP_COMMAND = "补鹿"
CALENDAR_COMMAND = "鹿历"
RANK_COMMAND = "鹿榜"
HELP_COMMAND = "鹿帮助"
ASSIST_COMMAND = "帮鹿"
BAN_COMMAND = "禁鹿"

COMMANDS = {
    SWITCH_NAME: "群管理员开关鹿管签到模块",
    SIGN_COMMAND: "自己签到，用法：鹿；代签用法：鹿 @用户",
    MAKEUP_COMMAND: "补签本月过去日期，用法：补鹿 <日期>",
    CALENDAR_COMMAND: "查看签到日历，用法：鹿历；查看他人：鹿历 @用户",
    RANK_COMMAND: "查看本群本月签到排行榜",
    ASSIST_COMMAND: "设置代签权限，用法：帮鹿 on/off；管理员可用：帮鹿 on/off @用户",
    BAN_COMMAND: "管理员禁用签到，用法：禁鹿 @用户 <30m|1h|2d>；解除：禁鹿 @用户",
    HELP_COMMAND: "查看鹿管签到帮助",
}
