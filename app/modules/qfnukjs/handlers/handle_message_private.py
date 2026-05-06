from logger import logger
from .. import MODULE_NAME


class PrivateMessageHandler:
    """私聊消息处理器"""

    def __init__(self, websocket, msg):
        self.websocket = websocket
        self.msg = msg

    async def handle(self):
        try:
            pass
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理私聊消息失败: {e}")
