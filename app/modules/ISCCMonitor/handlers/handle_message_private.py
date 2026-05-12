"""ISCC 擂台赛监控私聊命令处理。

仅响应系统管理员在私聊中的命令，支持：
- isccm：开关模块（借用框架的私聊开关）
- isccm菜单：查看命令菜单（由菜单管理器统一生成）
- isccm帮助：查看模块帮助文本
- isccm添加 / isccm删除 / isccm列表：管理监控的 team id
- isccmsession <session>：设置监控抓取使用的 session
- isccm检测：立即触发一次监控轮询
"""

from api.message import send_private_msg
from core.menu_manager import MENU_COMMAND, MenuManager
from core.switchs import handle_module_private_switch, is_private_switch_on
from logger import logger
from utils.auth import is_system_admin
from utils.generate import generate_reply_message, generate_text_message

from .. import (
    ADD_COMMAND,
    CHECK_COMMAND,
    HELP_COMMAND,
    LIST_COMMAND,
    MODULE_NAME,
    REMOVE_COMMAND,
    SESSION_COMMAND,
    SWITCH_NAME,
)
from .data_manager import DataManager
from .monitor_service import MonitorLock, run_once


class PrivateMessageHandler:
    def __init__(self, websocket, msg):
        self.websocket = websocket
        self.msg = msg
        self.user_id = str(msg.get("user_id", ""))
        self.message_id = str(msg.get("message_id", ""))
        self.raw_message = msg.get("raw_message", "").strip()

    async def handle(self):
        try:
            if await self._handle_switch_command():
                return
            if await self._handle_menu_command():
                return
            if self.raw_message == HELP_COMMAND:
                await self._reply(self._help_text())
                return

            if not is_private_switch_on(MODULE_NAME):
                return
            if not is_system_admin(self.user_id):
                return

            if self.raw_message == LIST_COMMAND:
                await self._handle_list()
                return
            if self.raw_message.startswith(f"{ADD_COMMAND} ") or self.raw_message == ADD_COMMAND:
                await self._handle_add()
                return
            if self.raw_message.startswith(f"{REMOVE_COMMAND} ") or self.raw_message == REMOVE_COMMAND:
                await self._handle_remove()
                return
            if self.raw_message.startswith(f"{SESSION_COMMAND} ") or self.raw_message == SESSION_COMMAND:
                await self._handle_session()
                return
            if self.raw_message == CHECK_COMMAND:
                await self._handle_check()
                return
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理私聊消息失败: {e}")
            await self._reply(f"ISCC 擂台赛监控处理失败：{e}")

    # -------------------- 开关 / 菜单 --------------------

    async def _handle_switch_command(self) -> bool:
        if self.raw_message.lower() == SWITCH_NAME.lower():
            if not is_system_admin(self.user_id):
                return True
            await handle_module_private_switch(
                MODULE_NAME, self.websocket, self.user_id, self.message_id
            )
            return True
        return False

    async def _handle_menu_command(self) -> bool:
        if self.raw_message.lower() == f"{SWITCH_NAME}{MENU_COMMAND}".lower():
            await self._reply(
                MenuManager.get_module_commands_text(MODULE_NAME),
                auto_delete=True,
            )
            return True
        return False

    # -------------------- 命令：列表 --------------------

    async def _handle_list(self):
        with DataManager() as dm:
            targets = dm.list_targets()
            session = dm.get_session()

        if not targets:
            await self._reply(
                "当前没有监控任何 team id。\n"
                "可以通过 `isccm添加 <team_id> [备注]` 添加监控对象。"
            )
            return

        lines = [
            f"当前监控中的 team id 共 {len(targets)} 个：",
        ]
        for idx, t in enumerate(targets, start=1):
            remark = t.get("remark") or ""
            team_name = t.get("team_name") or ""
            total_score = t.get("total_score") or ""
            lines.append(
                f"{idx}. {t['team_id']}"
                + (f" [{remark}]" if remark else "")
                + (f" 队名：{team_name}" if team_name else "")
                + (f" {total_score}" if total_score else "")
            )
        lines.append("")
        lines.append(
            "session 状态："
            + ("已配置" if session else "未配置（如需抓取受限页面请使用 isccmsession）")
        )
        await self._reply("\n".join(lines))

    # -------------------- 命令：添加 --------------------

    async def _handle_add(self):
        parts = self.raw_message.split(maxsplit=2)
        if len(parts) < 2:
            await self._reply("用法：isccm添加 <team_id> [备注]")
            return
        team_id = parts[1].strip()
        remark = parts[2].strip() if len(parts) == 3 else ""
        if not team_id:
            await self._reply("team_id 不能为空。")
            return

        with DataManager() as dm:
            is_new = dm.add_target(team_id, remark)

        if is_new:
            await self._reply(
                f"已添加监控：{team_id}"
                + (f"（备注：{remark}）" if remark else "")
                + "\n下一次心跳会尝试拉取该队伍的擂台赛详情并建立基线。"
            )
        else:
            await self._reply(
                f"该 team id 已在监控中，已更新备注为：{remark or '(空)'}"
            )

    # -------------------- 命令：删除 --------------------

    async def _handle_remove(self):
        parts = self.raw_message.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await self._reply("用法：isccm删除 <team_id>")
            return
        team_id = parts[1].strip()
        with DataManager() as dm:
            ok = dm.remove_target(team_id)
        if ok:
            await self._reply(f"已删除监控：{team_id}，相关历史提交记录已清除。")
        else:
            await self._reply(f"未找到 team id：{team_id}")

    # -------------------- 命令：session --------------------

    async def _handle_session(self):
        parts = self.raw_message.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            # 查询当前 session
            with DataManager() as dm:
                session = dm.get_session()
            if not session:
                await self._reply(
                    "当前未配置监控 session。\n"
                    "用法：isccmsession <session 字符串>\n"
                    "如果团队主页 /teamarena/<id> 无需登录即可查看，可不配置。"
                )
                return
            await self._reply(f"当前监控 session：\n{session}")
            return

        session = parts[1].strip()
        with DataManager() as dm:
            dm.set_session(session)
        await self._reply("已更新监控 session。")

    # -------------------- 命令：立即检测 --------------------

    async def _handle_check(self):
        lock = MonitorLock.get()
        if lock.locked():
            await self._reply("已有一次监控轮询正在执行中，请稍后再试。")
            return
        async with lock:
            await self._reply("正在立即执行一次 ISCC 擂台赛监控轮询...")
            await run_once(self.websocket, self.user_id, manual_trigger=True)

    # -------------------- 工具 --------------------

    def _help_text(self) -> str:
        return (
            "ISCC 擂台赛监控帮助\n"
            f"{SWITCH_NAME}：系统管理员开关模块\n"
            f"{ADD_COMMAND} <team_id> [备注]：添加监控对象\n"
            f"{REMOVE_COMMAND} <team_id>：删除监控对象\n"
            f"{LIST_COMMAND}：查看当前监控列表\n"
            f"{SESSION_COMMAND} <session>：设置监控所用 session（可选）\n"
            f"{CHECK_COMMAND}：立即执行一次监控轮询\n"
            f"{SWITCH_NAME}{MENU_COMMAND}：查看模块菜单\n"
            "说明：开启模块后，机器人会在每次心跳（按最小 60 秒间隔节流）"
            "拉取每个被监控 team 的擂台赛解题详情，发现新通过的题目时私聊通知管理员。"
        )

    async def _reply(self, text: str, auto_delete: bool = False):
        note = "del_msg=30" if auto_delete else ""
        await send_private_msg(
            self.websocket,
            self.user_id,
            [
                generate_reply_message(self.message_id),
                generate_text_message(text),
            ],
            note=note,
        )
