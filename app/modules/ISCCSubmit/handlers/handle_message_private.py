import re

from api.message import send_private_msg
from core.menu_manager import MENU_COMMAND, MenuManager
from core.switchs import handle_module_private_switch, is_private_switch_on
from logger import logger
from utils.auth import is_system_admin
from utils.generate import generate_reply_message, generate_text_message

from .. import (
    CONFIG_COMMAND,
    FLAG_PATTERN,
    HELP_COMMAND,
    MODULE_NAME,
    NONCE_COMMAND,
    SESSION_COMMAND,
    SWITCH_NAME,
)
from .data_manager import DataManager
from .iscc_client import ISCCClient, ISCCClientError, SubmitResult


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

            if self.raw_message.startswith(f"{CONFIG_COMMAND} "):
                await self._handle_config()
                return
            if self.raw_message.lower() == SESSION_COMMAND.lower():
                await self._handle_query_session()
                return
            if self.raw_message.lower() == NONCE_COMMAND.lower():
                await self._handle_query_nonce()
                return
            if re.fullmatch(FLAG_PATTERN, self.raw_message):
                await self._handle_submit_flag()
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理私聊消息失败: {e}")
            await self._reply(f"ISCC 自动提交处理失败：{e}")

    async def _handle_switch_command(self) -> bool:
        if self.raw_message.lower() == SWITCH_NAME.lower():
            if not is_system_admin(self.user_id):
                return True
            await handle_module_private_switch(MODULE_NAME, self.websocket, self.user_id, self.message_id)
            return True
        return False

    async def _handle_menu_command(self) -> bool:
        if self.raw_message.lower() == f"{SWITCH_NAME}{MENU_COMMAND}".lower():
            await self._reply(MenuManager.get_module_commands_text(MODULE_NAME), auto_delete=True)
            return True
        return False

    async def _handle_config(self):
        parts = self.raw_message.split(maxsplit=2)
        if len(parts) != 3:
            await self._reply("配置格式错误，用法：iscc配置 <账号> <密码>")
            return

        username, password = parts[1], parts[2]
        client = ISCCClient()
        try:
            session = await client.login(username, password)
        except ISCCClientError as e:
            await self._reply(f"ISCC 登录失败：{e}")
            return

        with DataManager() as dm:
            dm.save_account(self.user_id, username, password, session)
        await self._reply("ISCC 登录成功，账号、密码和 session 已保存。")

    async def _handle_submit_flag(self):
        with DataManager() as dm:
            account = dm.get_account(self.user_id)
        if not account:
            await self._reply("尚未配置 ISCC 账号，请先发送：iscc配置 <账号> <密码>")
            return

        await self._reply("已开始提交 flag，请等待结果。")
        client = await self._ensure_client(account)
        results = await client.submit_flag_to_unsolved(self.raw_message)
        await self._save_session(client.session_cookie)
        await self._refresh_nonces(client, account)
        await self._reply(self._format_results(results))

    async def _handle_query_session(self):
        with DataManager() as dm:
            account = dm.get_account(self.user_id)
        if not account:
            await self._reply("尚未配置 ISCC 账号，请先发送：iscc配置 <账号> <密码>")
            return
        session = account.get("session") or ""
        if not session:
            await self._reply("当前未保存 ISCC session，请提交一次 flag 触发登录。")
            return
        await self._reply(f"当前 ISCC session：\n{session}")

    async def _handle_query_nonce(self):
        with DataManager() as dm:
            account = dm.get_account(self.user_id)
            nonce_row = dm.get_nonce(self.user_id) if account else None
        if not account:
            await self._reply("尚未配置 ISCC 账号，请先发送：iscc配置 <账号> <密码>")
            return

        if not nonce_row or (not nonce_row.get("regular_nonce") and not nonce_row.get("arena_nonce")):
            # 没有缓存的 nonce，尝试立刻拉取一次（必要时自动重登录重试）
            client = await self._ensure_client(account)
            try:
                regular_nonce, arena_nonce = await self._fetch_nonces_with_retry(client, account)
            except ISCCClientError as e:
                await self._reply(f"获取 nonce 失败：{e}")
                return
            await self._save_session(client.session_cookie)
            if regular_nonce or arena_nonce:
                with DataManager() as dm:
                    dm.update_nonce(self.user_id, regular_nonce or None, arena_nonce or None)
                # 为保证回显的 updated_at 与 DB 一致，回读一次；查询不到时退回内存值
                with DataManager() as dm:
                    refreshed = dm.get_nonce(self.user_id)
                nonce_row = refreshed or {
                    "regular_nonce": regular_nonce,
                    "arena_nonce": arena_nonce,
                    "updated_at": "刚刚",
                }
            else:
                await self._reply("获取 nonce 失败，请稍后重试。")
                return

        await self._reply(
            "当前 ISCC nonce：\n"
            f"练武题 nonce：{nonce_row.get('regular_nonce') or '（未获取）'}\n"
            f"擂台题 nonce：{nonce_row.get('arena_nonce') or '（未获取）'}\n"
            f"更新时间：{nonce_row.get('updated_at', '未知')}"
        )

    async def _ensure_client(self, account: dict) -> ISCCClient:
        client = ISCCClient(account.get("session", ""))
        if await client.verify_login():
            return client

        session = await client.login(account["username"], account["password"])
        with DataManager() as dm:
            dm.save_session(self.user_id, session)
        return client

    async def _save_session(self, session: str):
        if not session:
            return
        with DataManager() as dm:
            dm.save_session(self.user_id, session)

    async def _refresh_nonces(self, client: ISCCClient, account: dict):
        try:
            regular_nonce, arena_nonce = await self._fetch_nonces_with_retry(client, account)
        except Exception as e:
            logger.warning(f"[{MODULE_NAME}]刷新 nonce 失败: {e}")
            return
        if not regular_nonce and not arena_nonce:
            return
        # 用 update_nonce + `x or None`：某一路抓到空串时保留 DB 原值，避免被覆盖
        with DataManager() as dm:
            dm.update_nonce(self.user_id, regular_nonce or None, arena_nonce or None)

    async def _fetch_nonces_with_retry(self, client: ISCCClient, account: dict) -> tuple[str, str]:
        """优先使用当前 session 拉取 nonce；遇到登录失效或两路都空时，重登录后再试一次。"""
        try:
            regular_nonce, arena_nonce = await client.fetch_nonces()
        except ISCCClientError as e:
            # 登录失效：走重登录后重试一次
            if "登录状态失效" not in str(e):
                raise
            regular_nonce, arena_nonce = "", ""

        if regular_nonce or arena_nonce:
            return regular_nonce, arena_nonce

        # 两路都拿不到，可能是 session 已失效但页面没把登录表单露出来。
        # 强制重登录一次再试。
        session = await client.login(account["username"], account["password"])
        with DataManager() as dm:
            dm.save_session(self.user_id, session)
        return await client.fetch_nonces()

    def _format_results(self, results: list[SubmitResult]) -> str:
        if not results:
            return "ISCC 提交完成：当前没有未解决题目。"

        accepted = [item for item in results if item.status == "1"]
        already = [item for item in results if item.status == "2"]
        failed = [item for item in results if item.status not in {"1", "2"}]
        lines = [
            "ISCC 提交完成",
            f"总提交：{len(results)} 题",
            f"成功：{len(accepted)} 题",
            f"已解决：{len(already)} 题",
            f"失败或跳过：{len(failed)} 题",
        ]
        for item in results:
            lines.append(f"{item.track} #{item.challenge_id}: {item.message}")
        return "\n".join(lines)

    def _help_text(self) -> str:
        return (
            "ISCC 自动提交帮助\n"
            "iscc：系统管理员开关模块\n"
            "iscc配置 <账号> <密码>：登录并保存账号、密码、session\n"
            "ISCC{xxxxx}：提交 flag 到练武题和擂台题所有未解题目\n"
            f"{SESSION_COMMAND}：查询当前 ISCC session\n"
            f"{NONCE_COMMAND}：查询当前练武题和擂台题 nonce\n"
            f"{SWITCH_NAME}{MENU_COMMAND}：查看模块菜单"
        )

    async def _reply(self, text: str, auto_delete: bool = False):
        note = "del_msg=30" if auto_delete else ""
        await send_private_msg(self.websocket, self.user_id, [generate_reply_message(self.message_id), generate_text_message(text)], note=note)
