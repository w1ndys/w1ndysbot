from logger import logger

from . import MODULE_NAME
from .handlers.handle_message import MessageHandler
from .handlers.handle_meta_event import MetaEventHandler
from .handlers.handle_response import ResponseHandler


async def handle_events(websocket, msg):
    try:
        if msg.get("status") == "ok":
            await ResponseHandler(websocket, msg).handle()
            return

        post_type = msg.get("post_type", "")
        if post_type == "meta_event":
            await MetaEventHandler(websocket, msg).handle()
            return

        if post_type == "message":
            await MessageHandler(websocket, msg).handle()
    except Exception as e:
        logger.error(f"[{MODULE_NAME}]处理事件失败: {e}")
