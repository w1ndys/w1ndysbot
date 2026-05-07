import json
import os
import uuid
from datetime import datetime

import aiohttp
from dotenv import load_dotenv

from .. import MODULE_NAME, SWITCH_NAME
from api.message import delete_msg, send_group_msg
from core.menu_manager import MENU_COMMAND, MenuManager
from core.switchs import handle_module_group_switch, is_group_switch_on
from logger import logger
from utils.auth import is_system_admin
from utils.generate import generate_reply_message, generate_text_message


MODULE_DIR = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(MODULE_DIR, ".env"))

BASE_URL = os.getenv("QFNUKJS_BASE_URL", "https://kjs.easy-qfnu.top").rstrip("/")
API_KEY = os.getenv("QFNUKJS_API_KEY", "")
QUERY_TIMEOUT_SECONDS = 30
TRIGGER_KEYWORD = "空教室"
PENDING_NOTE_PREFIX = f"{MODULE_NAME}_empty_classroom_pending"
PENDING_MESSAGES = {}


class GroupMessageHandler:
    """群消息处理器"""

    def __init__(self, websocket, msg):
        self.websocket = websocket
        self.msg = msg
        self.time = msg.get("time", "")
        self.formatted_time = datetime.fromtimestamp(self.time).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self.sub_type = msg.get("sub_type", "")
        self.group_id = str(msg.get("group_id", ""))
        self.message_id = str(msg.get("message_id", ""))
        self.user_id = str(msg.get("user_id", ""))
        self.message = msg.get("message", {})
        self.raw_message = msg.get("raw_message", "")
        self.sender = msg.get("sender", {})
        self.nickname = self.sender.get("nickname", "")
        self.card = self.sender.get("card", "")
        self.role = self.sender.get("role", "")

    async def _handle_switch_command(self):
        """处理群聊开关命令"""
        if self.raw_message.lower() == SWITCH_NAME.lower():
            if not is_system_admin(self.user_id):
                logger.error(f"[{MODULE_NAME}]{self.user_id}无权限切换群聊开关")
                return True
            await handle_module_group_switch(
                MODULE_NAME,
                self.websocket,
                self.group_id,
                self.message_id,
            )
            return True
        return False

    async def _handle_menu_command(self):
        """处理菜单命令（无视开关状态）"""
        if self.raw_message.lower() == f"{SWITCH_NAME}{MENU_COMMAND}".lower():
            menu_text = MenuManager.get_module_commands_text(MODULE_NAME)
            await send_group_msg(
                self.websocket,
                self.group_id,
                [
                    generate_reply_message(self.message_id),
                    generate_text_message(menu_text),
                ],
                note="del_msg=30",
            )
            return True
        return False

    def _is_text_only_message(self):
        if not self.message:
            return False
        return all(segment.get("type") == "text" for segment in self.message)

    async def _query_empty_classroom(self, text):
        if not API_KEY:
            return "qfnukjs 未配置 API Key，请在模块目录 .env 中配置 QFNUKJS_API_KEY。"

        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json",
        }
        payload = {"text": text}
        timeout = aiohttp.ClientTimeout(total=QUERY_TIMEOUT_SECONDS)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{BASE_URL}/api/v1/open/ai-query",
                json=payload,
                headers=headers,
            ) as response:
                response_text = await response.text()
                if response.status >= 400:
                    logger.error(
                        f"[{MODULE_NAME}]空教室查询接口返回异常: "
                        f"status={response.status}, body={response_text[:500]}"
                    )
                    return "空教室查询失败，请稍后再试。"

                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError:
                    return self._format_json_string(response_text)

        return self._format_query_result(data)

    def _format_json_string(self, text):
        text = text.strip()
        if not text:
            return "空教室查询结果为空。"

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return text

        if isinstance(data, (dict, list)):
            return json.dumps(data, ensure_ascii=False, indent=2)
        return str(data).strip() or "空教室查询结果为空。"

    def _format_query_result(self, data):
        if isinstance(data, dict):
            for key in ("message", "result", "data", "answer", "text"):
                value = data.get(key)
                if isinstance(value, (dict, list)) and value:
                    return json.dumps(value, ensure_ascii=False, indent=2)
                if isinstance(value, str) and value.strip():
                    return self._format_json_string(value)
            return json.dumps(data, ensure_ascii=False, indent=2)

        if isinstance(data, list):
            if not data:
                return "未查询到空教室信息。"
            return json.dumps(data, ensure_ascii=False, indent=2)

        return str(data).strip() or "空教室查询结果为空。"

    async def _send_pending_message(self):
        pending_id = uuid.uuid4().hex
        PENDING_MESSAGES[pending_id] = {"message_id": None, "done": False}
        await send_group_msg(
            self.websocket,
            self.group_id,
            [
                generate_reply_message(self.message_id),
                generate_text_message("空教室查询处理中，请稍候..."),
            ],
            note=f"{PENDING_NOTE_PREFIX}={pending_id}",
        )
        return pending_id

    async def _finish_pending_message(self, pending_id):
        pending = PENDING_MESSAGES.get(pending_id)
        if not pending:
            return

        pending["done"] = True
        message_id = pending.get("message_id")
        if not message_id:
            return

        await delete_msg(self.websocket, message_id)
        PENDING_MESSAGES.pop(pending_id, None)

    async def _handle_empty_classroom_query(self):
        if not self._is_text_only_message():
            return False

        query_text = self.raw_message.strip()
        if TRIGGER_KEYWORD not in query_text:
            return False

        pending_id = await self._send_pending_message()
        try:
            result_text = await self._query_empty_classroom(query_text)
            await send_group_msg(
                self.websocket,
                self.group_id,
                [
                    generate_reply_message(self.message_id),
                    generate_text_message(result_text),
                ],
            )
        finally:
            await self._finish_pending_message(pending_id)
        logger.info(
            f"[{MODULE_NAME}]群{self.group_id}用户{self.user_id}查询空教室: {query_text}"
        )
        return True

    async def handle(self):
        """处理群消息"""
        try:
            if await self._handle_switch_command():
                return

            if await self._handle_menu_command():
                return

            if not is_group_switch_on(self.group_id, MODULE_NAME):
                return

            await self._handle_empty_classroom_query()

        except aiohttp.ClientError as e:
            logger.error(f"[{MODULE_NAME}]请求空教室查询接口失败: {e}")
            await send_group_msg(
                self.websocket,
                self.group_id,
                [
                    generate_reply_message(self.message_id),
                    generate_text_message("空教室查询服务暂时不可用，请稍后再试。"),
                ],
            )
        except TimeoutError as e:
            logger.error(f"[{MODULE_NAME}]请求空教室查询接口超时: {e}")
            await send_group_msg(
                self.websocket,
                self.group_id,
                [
                    generate_reply_message(self.message_id),
                    generate_text_message("空教室查询超时，请稍后再试。"),
                ],
            )
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理群消息失败: {e}")
