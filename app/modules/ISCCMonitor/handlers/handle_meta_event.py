"""心跳元事件处理：按固定间隔触发 ISCC 擂台赛监控轮询。"""

import time
from datetime import datetime

from config import OWNER_ID
from core.switchs import is_private_switch_on
from logger import logger

from .. import MODULE_NAME
from .monitor_service import MonitorLock, run_once


# 最小轮询间隔（秒）。心跳频率较高，不希望每个心跳都请求 ISCC。
MIN_INTERVAL_SECONDS = 60


class MetaEventHandler:
    """元事件处理器/定时任务处理器。

    模块只监听心跳（heartbeat）事件，按 `MIN_INTERVAL_SECONDS` 节流后执行一次
    监控轮询。轮询通过模块级互斥锁避免并发执行。
    """

    _last_run_at: float = 0.0

    def __init__(self, websocket, msg):
        self.websocket = websocket
        self.msg = msg
        self.time = msg.get("time", "")
        self.formatted_time = (
            datetime.fromtimestamp(self.time).strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(self.time, (int, float))
            else ""
        )
        self.post_type = msg.get("post_type", "")
        self.meta_event_type = msg.get("meta_event_type", "")

    async def handle(self):
        try:
            if self.post_type != "meta_event":
                return
            if self.meta_event_type == "heartbeat":
                await self._handle_heartbeat()
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理元事件失败: {e}")

    async def _handle_heartbeat(self):
        if not is_private_switch_on(MODULE_NAME):
            return
        if not OWNER_ID:
            return

        now = time.time()
        if now - MetaEventHandler._last_run_at < MIN_INTERVAL_SECONDS:
            return
        MetaEventHandler._last_run_at = now

        lock = MonitorLock.get()
        if lock.locked():
            return
        async with lock:
            try:
                await run_once(self.websocket, str(OWNER_ID), manual_trigger=False)
            except Exception as e:
                logger.error(f"[{MODULE_NAME}]心跳触发监控轮询失败: {e}")
