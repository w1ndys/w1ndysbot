from logger import logger
from api.message import send_private_msg
from utils.auth import is_system_admin
from utils.generate import generate_reply_message, generate_text_message
from .. import MODULE_NAME
from .scheduled_config import (
    get_api_key,
    get_forward_announcement,
    set_api_key,
    set_forward_announcement,
)


API_KEY_CONFIG_COMMAND = "qfnukjs配置apikey"
API_KEY_STATUS_COMMAND = "qfnukjs apikey状态"
FORWARD_ANNOUNCEMENT_CONFIG_COMMAND = "qfnukjs配置转发公告"
FORWARD_ANNOUNCEMENT_STATUS_COMMAND = "qfnukjs转发公告状态"
FORWARD_ANNOUNCEMENT_CLEAR_COMMAND = "qfnukjs清空转发公告"


class PrivateMessageHandler:
    """私聊消息处理器"""

    def __init__(self, websocket, msg):
        self.websocket = websocket
        self.msg = msg
        self.user_id = str(msg.get("user_id", ""))
        self.message_id = str(msg.get("message_id", ""))
        self.raw_message = msg.get("raw_message", "").strip()

    async def handle(self):
        try:
            if not is_system_admin(self.user_id):
                return

            if self.raw_message.startswith(f"{API_KEY_CONFIG_COMMAND} "):
                await self._handle_api_key_config()
                return
            if self.raw_message.lower() == API_KEY_STATUS_COMMAND.lower():
                text = "qfnukjs API Key 已配置。"
                if not get_api_key():
                    text = "qfnukjs API Key 未配置。"
                await self._reply(text)
                return
            if self.raw_message.startswith(f"{FORWARD_ANNOUNCEMENT_CONFIG_COMMAND} "):
                await self._handle_forward_announcement_config()
                return
            if self.raw_message.lower() == FORWARD_ANNOUNCEMENT_STATUS_COMMAND.lower():
                await self._handle_forward_announcement_status()
                return
            if self.raw_message.lower() == FORWARD_ANNOUNCEMENT_CLEAR_COMMAND.lower():
                set_forward_announcement("")
                await self._reply("qfnukjs 合并转发公告已清空。")
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理私聊消息失败: {e}")

    async def _handle_api_key_config(self):
        api_key = self.raw_message[len(API_KEY_CONFIG_COMMAND) :].strip()
        if not api_key:
            await self._reply(f"配置格式错误，用法：{API_KEY_CONFIG_COMMAND} <API Key>")
            return

        set_api_key(api_key)
        await self._reply("qfnukjs API Key 已保存。")

    async def _handle_forward_announcement_config(self):
        announcement = self.raw_message[len(FORWARD_ANNOUNCEMENT_CONFIG_COMMAND) :].strip()
        if not announcement:
            await self._reply(
                f"配置格式错误，用法：{FORWARD_ANNOUNCEMENT_CONFIG_COMMAND} <公告内容>"
            )
            return

        set_forward_announcement(announcement)
        await self._reply("qfnukjs 合并转发公告已保存。")

    async def _handle_forward_announcement_status(self):
        announcement = get_forward_announcement()
        if announcement:
            await self._reply(f"当前 qfnukjs 合并转发公告：\n{announcement}")
            return
        await self._reply("当前未配置 qfnukjs 合并转发公告。")

    async def _reply(self, text):
        await send_private_msg(
            self.websocket,
            self.user_id,
            [generate_reply_message(self.message_id), generate_text_message(text)],
        )
