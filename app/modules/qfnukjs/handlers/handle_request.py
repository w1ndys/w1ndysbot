from logger import logger
from .. import MODULE_NAME


class RequestHandler:
    """请求处理器"""

    def __init__(self, websocket, msg):
        self.websocket = websocket
        self.msg = msg

    async def handle(self):
        try:
            pass
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理请求失败: {e}")
