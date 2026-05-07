from logger import logger
from .. import MODULE_NAME
from api.message import delete_msg
from .handle_message_group import PENDING_MESSAGES, PENDING_NOTE_PREFIX


class ResponseHandler:
    """响应处理器"""

    def __init__(self, websocket, msg):
        self.websocket = websocket
        self.msg = msg
        self.data = msg.get("data", {})
        self.echo = msg.get("echo", "")

    async def handle(self):
        try:
            if not isinstance(self.echo, str):
                return

            marker = f"send_group_msg-{PENDING_NOTE_PREFIX}="
            if not self.echo.startswith(marker):
                return

            pending_id = self.echo[len(marker) :]
            pending = PENDING_MESSAGES.get(pending_id)
            if not pending:
                return

            message_id = self.data.get("message_id")
            if not message_id:
                return

            if pending.get("done"):
                await delete_msg(self.websocket, message_id)
                PENDING_MESSAGES.pop(pending_id, None)
                return

            pending["message_id"] = message_id
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理响应失败: {e}")
