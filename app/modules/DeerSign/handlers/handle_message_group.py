import calendar
import re
import time
from datetime import datetime

from api.message import send_group_msg
from core.menu_manager import MENU_COMMAND, MenuManager
from core.switchs import handle_module_group_switch, is_group_switch_on
from logger import logger
from utils.auth import is_group_admin, is_system_admin
from utils.generate import generate_at_message, generate_image_message, generate_reply_message, generate_text_message

from .. import (
    ASSIST_COMMAND,
    BAN_COMMAND,
    CALENDAR_COMMAND,
    HELP_COMMAND,
    MAKEUP_COMMAND,
    MODULE_NAME,
    RANK_COMMAND,
    SIGN_COMMAND,
    SWITCH_NAME,
)
from .data_manager import DataManager
from .render import render_calendar, render_rank


MAX_BAN_SECONDS = 30 * 24 * 60 * 60


class GroupMessageHandler:
    def __init__(self, websocket, msg):
        self.websocket = websocket
        self.msg = msg
        self.group_id = str(msg.get("group_id", ""))
        self.message_id = str(msg.get("message_id", ""))
        self.user_id = str(msg.get("user_id", ""))
        self.message = msg.get("message", [])
        self.raw_message = msg.get("raw_message", "").strip()
        self.sender = msg.get("sender", {})
        self.nickname = self.sender.get("card") or self.sender.get("nickname") or self.user_id
        self.role = self.sender.get("role", "")

    async def handle(self):
        try:
            if await self._handle_switch_command():
                return
            if await self._handle_menu_command():
                return
            if self.raw_message == HELP_COMMAND:
                await self._reply(self._help_text())
                return
            if not self._is_business_command():
                return
            if not is_group_switch_on(self.group_id, MODULE_NAME):
                return

            if self._matches_command(SIGN_COMMAND):
                await self._handle_sign()
            elif self._matches_command(MAKEUP_COMMAND):
                await self._handle_makeup()
            elif self._matches_command(CALENDAR_COMMAND):
                await self._handle_calendar()
            elif self._matches_command(RANK_COMMAND):
                await self._handle_rank()
            elif self._matches_command(ASSIST_COMMAND):
                await self._handle_assist_permission()
            elif self._matches_command(BAN_COMMAND):
                await self._handle_ban()
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理群消息失败: {e}")
            await self._reply("鹿管签到处理失败，请稍后再试。")

    async def _handle_switch_command(self) -> bool:
        if self.raw_message.lower() == SWITCH_NAME.lower():
            if not is_group_admin(self.role) and not is_system_admin(self.user_id):
                return True
            await handle_module_group_switch(MODULE_NAME, self.websocket, self.group_id, self.message_id)
            return True
        return False

    async def _handle_menu_command(self) -> bool:
        if self.raw_message.lower() == f"{SWITCH_NAME}{MENU_COMMAND}".lower():
            await self._reply(MenuManager.get_module_commands_text(MODULE_NAME), auto_delete=True)
            return True
        return False

    def _is_business_command(self) -> bool:
        commands = (SIGN_COMMAND, MAKEUP_COMMAND, CALENDAR_COMMAND, RANK_COMMAND, ASSIST_COMMAND, BAN_COMMAND)
        return any(self._matches_command(command) for command in commands)

    def _matches_command(self, command: str) -> bool:
        return self.raw_message == command or self.raw_message.startswith(f"{command} ")

    async def _handle_sign(self):
        target_id = self._first_at_user() or self.user_id
        is_assist = target_id != self.user_id
        today = datetime.now()
        with DataManager() as dm:
            state = dm.get_user_state(self.group_id, target_id)
            banned_message = self._banned_message(state)
            if banned_message:
                await self._reply(banned_message)
                return
            if is_assist and not state["allow_assist"]:
                await self._reply("该用户已关闭代签权限。")
                return
            count = dm.add_sign(self.group_id, target_id, today.strftime("%Y-%m"), today.day)
            records = dm.get_month_records(self.group_id, target_id, today.strftime("%Y-%m"))

        label = self._label_for_user(target_id)
        image_base64 = render_calendar(today.year, today.month, label, records, today.day)
        text = f"已帮 {label} 签到成功，今天累计 {count} 次。" if is_assist else f"签到成功，今天累计 {count} 次。"
        await self._reply_with_image(text, image_base64)

    async def _handle_makeup(self):
        parts = self.raw_message.split(maxsplit=1)
        if len(parts) != 2 or not parts[1].isdigit():
            await self._reply("补签日期格式错误，用法：补鹿 <日期>。")
            return
        today = datetime.now()
        day = int(parts[1])
        _, month_days = calendar.monthrange(today.year, today.month)
        if day < 1 or day > month_days:
            await self._reply("补签日期超出本月范围。")
            return
        if day >= today.day:
            await self._reply("只能补签本月今天之前的日期。")
            return

        year_month = today.strftime("%Y-%m")
        with DataManager() as dm:
            state = dm.get_user_state(self.group_id, self.user_id)
            banned_message = self._banned_message(state)
            if banned_message:
                await self._reply(banned_message)
                return
            if dm.has_sign(self.group_id, self.user_id, year_month, day):
                await self._reply("该日期已经签到过。")
                return
            dm.add_sign(self.group_id, self.user_id, year_month, day, increment=False)
            records = dm.get_month_records(self.group_id, self.user_id, year_month)

        image_base64 = render_calendar(today.year, today.month, self.nickname, records, today.day)
        await self._reply_with_image(f"补签 {day} 号成功。", image_base64)

    async def _handle_calendar(self):
        target_id = self._first_at_user() or self.user_id
        today = datetime.now()
        with DataManager() as dm:
            records = dm.get_month_records(self.group_id, target_id, today.strftime("%Y-%m"))
        image_base64 = render_calendar(today.year, today.month, self._label_for_user(target_id), records, today.day)
        await self._reply_with_image("本月鹿管签到日历：", image_base64)

    async def _handle_rank(self):
        today = datetime.now()
        with DataManager() as dm:
            rankings = dm.get_rankings(self.group_id, today.strftime("%Y-%m"), 10)
        labels = {str(item["user_id"]): self._label_for_user(str(item["user_id"])) for item in rankings}
        image_base64 = render_rank(today.year, today.month, rankings, labels)
        await self._reply_with_image("本群本月鹿管签到榜：", image_base64)

    async def _handle_assist_permission(self):
        parts = self.raw_message.split()
        if len(parts) < 2 or parts[1].lower() not in {"on", "off"}:
            await self._reply("代签权限用法：帮鹿 on/off，管理员可追加 @用户。")
            return
        target_id = self._first_at_user() or self.user_id
        if target_id != self.user_id and not self._is_admin():
            await self._reply("普通成员只能修改自己的代签权限。")
            return
        allow = parts[1].lower() == "on"
        with DataManager() as dm:
            dm.set_allow_assist(self.group_id, target_id, allow)
        if target_id == self.user_id:
            await self._reply("已允许别人帮你签到。" if allow else "已禁止别人帮你签到。")
        else:
            action = "允许" if allow else "禁止"
            await self._reply_segments([generate_text_message(f"已{action}别人帮 "), generate_at_message(target_id), generate_text_message(" 签到。")])

    async def _handle_ban(self):
        if not self._is_admin():
            await self._reply("只有群管理员可以管理签到禁用。")
            return
        target_id = self._first_at_user()
        if not target_id:
            await self._reply("禁用签到用法：禁鹿 @用户 <30m|1h|2d>；解除：禁鹿 @用户。")
            return
        duration_text = self._remove_at_text(self.raw_message[len(BAN_COMMAND):]).strip()
        with DataManager() as dm:
            if not duration_text:
                dm.set_banned_until(self.group_id, target_id, 0)
                await self._reply_segments([generate_text_message("已解除 "), generate_at_message(target_id), generate_text_message(" 的签到禁用。")])
                return
            seconds = self._parse_duration(duration_text)
            if seconds is None:
                await self._reply("禁用时长格式错误，支持 30m、1h、2d。")
                return
            if seconds > MAX_BAN_SECONDS:
                await self._reply("禁用时长最长为 30 天。")
                return
            banned_until = int(time.time()) + seconds
            dm.set_banned_until(self.group_id, target_id, banned_until)
        until_text = datetime.fromtimestamp(banned_until).strftime("%Y-%m-%d %H:%M:%S")
        await self._reply_segments([generate_text_message("已禁止 "), generate_at_message(target_id), generate_text_message(f" 签到至 {until_text}。")])

    def _first_at_user(self) -> str | None:
        if isinstance(self.message, list):
            for segment in self.message:
                if segment.get("type") == "at":
                    qq = str(segment.get("data", {}).get("qq", ""))
                    if qq and qq != "all":
                        return qq
        match = re.search(r"\[CQ:at,qq=(\d+)\]", self.raw_message)
        return match.group(1) if match else None

    def _remove_at_text(self, text: str) -> str:
        text = re.sub(r"\[CQ:at,qq=\d+\]", "", text)
        if isinstance(self.message, list):
            for segment in self.message:
                if segment.get("type") == "at":
                    qq = str(segment.get("data", {}).get("qq", ""))
                    text = text.replace(f"@{qq}", "")
        return text

    def _label_for_user(self, user_id: str) -> str:
        return self.nickname if user_id == self.user_id else f"QQ {user_id}"

    def _is_admin(self) -> bool:
        return is_group_admin(self.role) or is_system_admin(self.user_id)

    def _banned_message(self, state: dict) -> str | None:
        banned_until = int(state.get("banned_until") or 0)
        if banned_until > int(time.time()):
            until_text = datetime.fromtimestamp(banned_until).strftime("%Y-%m-%d %H:%M:%S")
            return f"该用户签到已被禁用至 {until_text}。"
        return None

    def _parse_duration(self, text: str) -> int | None:
        match = re.fullmatch(r"(\d+)([mhd])", text.strip().lower())
        if not match:
            return None
        value = int(match.group(1))
        unit = match.group(2)
        multipliers = {"m": 60, "h": 3600, "d": 86400}
        return value * multipliers[unit]

    def _help_text(self) -> str:
        return (
            "鹿管签到帮助\n"
            "鹿：自己签到\n"
            "鹿 @用户：帮别人签到\n"
            "补鹿 <日期>：补签本月过去日期\n"
            "鹿历 / 鹿历 @用户：查看本月签到日历\n"
            "鹿榜：查看本群本月排行榜\n"
            "帮鹿 on/off：允许或禁止别人帮自己签到\n"
            "帮鹿 on/off @用户：管理员设置指定用户代签权限\n"
            "禁鹿 @用户 <30m|1h|2d>：管理员禁用用户签到\n"
            "禁鹿 @用户：管理员解除用户签到禁用\n"
            f"{SWITCH_NAME}：群管理员开关模块"
        )

    async def _reply(self, text: str, auto_delete: bool = False):
        note = "del_msg=30" if auto_delete else ""
        await send_group_msg(self.websocket, self.group_id, [generate_reply_message(self.message_id), generate_text_message(text)], note=note)

    async def _reply_segments(self, segments: list[dict]):
        await send_group_msg(self.websocket, self.group_id, [generate_reply_message(self.message_id), *segments])

    async def _reply_with_image(self, text: str, image_base64: str):
        try:
            await send_group_msg(
                self.websocket,
                self.group_id,
                [generate_reply_message(self.message_id), generate_text_message(f"{text}\n"), generate_image_message(image_base64, type="base64")],
            )
        except Exception:
            await self._reply(text)
