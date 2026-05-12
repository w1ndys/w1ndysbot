import time

from api.message import send_private_msg
from core.switchs import is_private_switch_on
from logger import logger
from utils.generate import generate_text_message

from .. import MODULE_NAME
from .data_manager import DataManager
from .iscc_client import ISCCClient


class MetaEventHandler:
    _last_run_at = 0
    _running = False

    def __init__(self, websocket, msg):
        self.websocket = websocket
        self.msg = msg
        self.post_type = msg.get("post_type", "")
        self.meta_event_type = msg.get("meta_event_type", "")

    async def handle(self):
        try:
            if self.post_type == "meta_event" and self.meta_event_type == "heartbeat":
                await self.handle_heartbeat()
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理元事件失败: {e}")

    async def handle_heartbeat(self):
        if not is_private_switch_on(MODULE_NAME):
            return
        if self.__class__._running:
            return

        now = int(time.time())
        if now - self.__class__._last_run_at < 60:
            return
        self.__class__._last_run_at = now
        self.__class__._running = True

        try:
            with DataManager() as dm:
                accounts = dm.get_all_accounts()
            for account in accounts:
                await self._keep_account_alive(account)
        finally:
            self.__class__._running = False

    async def _keep_account_alive(self, account: dict):
        user_id = str(account["user_id"])
        client = ISCCClient(account.get("session", ""))
        try:
            await client.keep_alive_arena_score()
            return
        except Exception as e:
            logger.warning(f"[{MODULE_NAME}]ISCC session 保活失败，准备重新登录: {e}")

        try:
            session = await client.login(account["username"], account["password"])
            with DataManager() as dm:
                dm.save_session(user_id, session)
            await send_private_msg(self.websocket, user_id, [generate_text_message("ISCC 登录状态已过期，机器人已自动重新登录并刷新 session。")])
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]ISCC 自动重新登录失败: {e}")
            await send_private_msg(self.websocket, user_id, [generate_text_message(f"ISCC 登录状态已过期，自动重新登录失败：{e}")])
