from logger import logger
from . import MODULE_NAME
from .handlers.handle_message import MessageHandler
from .handlers.handle_response import ResponseHandler


async def handle_events(websocket, msg):
    try:
        if msg.get("status") == "ok":
            await ResponseHandler(websocket, msg).handle()
            return

        if msg.get("post_type", "") == "message":
            await MessageHandler(websocket, msg).handle()
    except Exception as e:
        logger.error(f"[{MODULE_NAME}]处理事件失败: {e}")
