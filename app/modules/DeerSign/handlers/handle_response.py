from logger import logger
from .. import MODULE_NAME


class ResponseHandler:
    def __init__(self, websocket, msg):
        self.websocket = websocket
        self.msg = msg

    async def handle(self):
        try:
            return
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理响应失败: {e}")
