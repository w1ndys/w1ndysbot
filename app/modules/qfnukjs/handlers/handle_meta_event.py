from logger import logger
from .. import MODULE_NAME


class MetaEventHandler:
    """元事件处理器"""

    def __init__(self, websocket, msg):
        self.websocket = websocket
        self.msg = msg

    async def handle(self):
        try:
            pass
        except Exception as e:
            logger.error(f"[{MODULE_NAME}]处理元事件失败: {e}")
