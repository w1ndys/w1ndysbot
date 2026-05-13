import asyncio
from datetime import datetime, time

from .. import MODULE_NAME
from api.message import send_forward_msg, send_group_msg
from core.switchs import get_all_enabled_groups
from logger import logger
from utils.generate import generate_node_message, generate_text_message
from .empty_classroom_service import extract_classrooms, query_empty_classroom_direct
from .scheduled_config import (
    get_group_buildings,
    get_last_run_date,
    set_last_run_date,
)


BOT_USER_ID = "2854196310"
BOT_NICKNAME = "空教室助手"
DAILY_PUSH_TIME = time(7, 30)
SCHEDULE_LOCK = asyncio.Lock()
PERIOD_QUERIES = (
    ("1-4节", (("1-4节", "01", "04"),)),
    ("5-8节", (("5-8节", "05", "08"),)),
    ("9-11节、全天", (("9-11节", "09", "11"), ("全天", "01", "11"))),
)


class MetaEventHandler:
    """元事件处理器"""

    def __init__(self, websocket, msg):
        self.websocket = websocket
        self.msg = msg
        self.time = msg.get("time", "")
        self.post_type = msg.get("post_type", "")
        self.meta_event_type = msg.get("meta_event_type", "")

    async def handle(self):
        try:
            if self.post_type == "meta_event" and self.meta_event_type == "heartbeat":
                await self.handle_heartbeat()
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理元事件失败: {e}")

    async def handle_heartbeat(self):
        now = self._get_event_datetime()
        if now.time() < DAILY_PUSH_TIME:
            return

        today = now.strftime("%Y-%m-%d")
        if get_last_run_date() == today:
            return

        async with SCHEDULE_LOCK:
            if get_last_run_date() == today:
                return
            await self._run_daily_push(today)
            set_last_run_date(today)

    def _get_event_datetime(self):
        try:
            return datetime.fromtimestamp(int(self.time))
        except (TypeError, ValueError, OSError):
            return datetime.now()

    async def _run_daily_push(self, today):
        group_ids = sorted(str(group_id) for group_id in get_all_enabled_groups(MODULE_NAME))
        for group_id in group_ids:
            buildings = get_group_buildings(group_id)
            if not buildings:
                continue

            logger.info(
                f"[{MODULE_NAME}]开始推送群{group_id}每日空教室，教学楼: {buildings}"
            )
            await self._send_group_daily_push(group_id, buildings, today)

    async def _send_group_daily_push(self, group_id, buildings, today):
        summary_lines = [f"{today} 定时空教室数量汇总"]
        for building in buildings:
            period_results = []
            for period_label, ranges in PERIOD_QUERIES:
                classrooms = await self._query_period_classrooms(building, ranges)
                period_results.append((period_label, classrooms))

            await self._send_building_forward_message(group_id, building, period_results)
            summary_lines.append(self._format_building_summary(building, period_results))

        await send_group_msg(
            self.websocket,
            group_id,
            [generate_text_message("\n".join(summary_lines))],
        )

    async def _query_period_classrooms(self, building, ranges):
        results = []
        for label, start_node, end_node in ranges:
            classrooms = await self._query_node_range_classrooms(
                building, label, start_node, end_node
            )
            results.append((label, classrooms))
        return results

    async def _query_node_range_classrooms(self, building, label, start_node, end_node):
        try:
            data = await query_empty_classroom_direct(building, start_node, end_node)
            return extract_classrooms(data)
        except Exception as e:
            logger.error(
                f"[{MODULE_NAME}]定时查询{building}{label}空教室失败: {e}"
            )
            return []

    async def _send_building_forward_message(self, group_id, building, period_results):
        messages = []
        for period_label, range_results in period_results:
            text = self._format_period_classrooms(building, period_label, range_results)
            messages.append(
                generate_node_message(
                    user_id=BOT_USER_ID,
                    nickname=BOT_NICKNAME,
                    content=[generate_text_message(text)],
                )
            )

        title = f"{building}今日无课教室"
        await send_forward_msg(
            self.websocket,
            group_id=group_id,
            message=messages,
            news=title,
            prompt=title,
            summary=f"共 {len(messages)} 条时段消息",
            source=MODULE_NAME,
        )

    def _format_period_classrooms(self, building, period_label, range_results):
        lines = [f"{building}，{period_label}无课教室"]
        for label, classrooms in range_results:
            lines.append(f"{label}：{len(classrooms)} 间")
            lines.append("、".join(classrooms) if classrooms else "暂无无课教室。")
        return "\n".join(lines)

    def _format_building_summary(self, building, period_results):
        parts = []
        for _period_label, range_results in period_results:
            for label, classrooms in range_results:
                parts.append(f"{label}{len(classrooms)}间")
        return f"{building}，" + "。".join(parts)
