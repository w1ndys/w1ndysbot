import time
from datetime import datetime, timezone, timedelta

from api.message import send_private_msg
from core.switchs import is_private_switch_on
from logger import logger
from utils.generate import generate_text_message

from .. import DAILY_REFRESH_HOUR, DAILY_REFRESH_MINUTE, MODULE_NAME
from .data_manager import DataManager
from .iscc_client import ISCCClient


BEIJING_TZ = timezone(timedelta(hours=8))

# DB meta 表中记录"最近一次每日刷新日期（北京时间 YYYY-MM-DD）"使用的 key
DAILY_REFRESH_META_KEY = "daily_refresh_last_date"


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
                last_refresh_date = dm.get_meta(DAILY_REFRESH_META_KEY)

            beijing_now = datetime.now(BEIJING_TZ)
            should_daily_refresh = self._should_daily_refresh(beijing_now, last_refresh_date)

            if should_daily_refresh:
                # 先落库标记，避免刷新过程中进程崩溃、重启后又触发一轮
                today = beijing_now.strftime("%Y-%m-%d")
                with DataManager() as dm:
                    dm.set_meta(DAILY_REFRESH_META_KEY, today)

            for account in accounts:
                if should_daily_refresh:
                    await self._daily_refresh_account(account, beijing_now)
                else:
                    await self._keep_account_alive(account)
        finally:
            self.__class__._running = False

    def _should_daily_refresh(self, beijing_now: datetime, last_refresh_date: str) -> bool:
        today = beijing_now.strftime("%Y-%m-%d")
        if last_refresh_date == today:
            return False
        # 到达或超过 07:50 即触发。心跳最小间隔 60s，能保证当日被触发。
        if beijing_now.hour > DAILY_REFRESH_HOUR:
            return True
        if beijing_now.hour == DAILY_REFRESH_HOUR and beijing_now.minute >= DAILY_REFRESH_MINUTE:
            return True
        return False

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
            await send_private_msg(
                self.websocket,
                user_id,
                [generate_text_message(
                    "ISCC 登录状态已过期，机器人已自动重新登录并刷新 session。\n"
                    f"新的 session：{session}"
                )],
            )
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]ISCC 自动重新登录失败: {e}")
            await send_private_msg(
                self.websocket,
                user_id,
                [generate_text_message(f"ISCC 登录状态已过期，自动重新登录失败：{e}")],
            )

    async def _daily_refresh_account(self, account: dict, beijing_now: datetime):
        user_id = str(account["user_id"])
        username = account.get("username", "")
        password = account.get("password", "")
        client = ISCCClient(account.get("session", ""))
        timestamp = beijing_now.strftime("%Y-%m-%d %H:%M:%S")

        try:
            session = await client.login(username, password)
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]ISCC 每日定时登录失败: {e}")
            await send_private_msg(
                self.websocket,
                user_id,
                [generate_text_message(
                    f"[ISCC 每日定时刷新] 北京时间 {timestamp} 自动登录失败：{e}"
                )],
            )
            return

        with DataManager() as dm:
            dm.save_session(user_id, session)

        # 登录成功后顺带刷新 nonce 缓存
        regular_nonce = ""
        arena_nonce = ""
        try:
            regular_nonce, arena_nonce = await client.fetch_nonces()
            if regular_nonce or arena_nonce:
                # 用 update_nonce + `x or None`：抓到空串视为"这次没拿到"，保留 DB 原值
                with DataManager() as dm:
                    dm.update_nonce(user_id, regular_nonce or None, arena_nonce or None)
        except Exception as e:
            logger.warning(f"[{MODULE_NAME}]ISCC 每日定时刷新 nonce 失败: {e}")

        lines = [
            f"[ISCC 每日定时刷新] 北京时间 {timestamp}",
            "自动重新登录成功，session 已更新。",
            f"新的 session：{session}",
        ]
        if regular_nonce or arena_nonce:
            lines.append(f"练武题 nonce：{regular_nonce or '（未获取）'}")
            lines.append(f"擂台题 nonce：{arena_nonce or '（未获取）'}")
        await send_private_msg(
            self.websocket,
            user_id,
            [generate_text_message("\n".join(lines))],
        )
