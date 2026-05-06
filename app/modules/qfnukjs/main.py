from logger import logger
from . import MODULE_NAME
from .handlers.handle_meta_event import MetaEventHandler
from .handlers.handle_message import MessageHandler
from .handlers.handle_notice import NoticeHandler
from .handlers.handle_request import RequestHandler
from .handlers.handle_response import ResponseHandler


async def handle_events(websocket, msg):
    """统一事件处理入口"""
    try:
        if msg.get("status") == "ok":
            await ResponseHandler(websocket, msg).handle()
            return

        post_type = msg.get("post_type", "")

        if post_type == "meta_event":
            await MetaEventHandler(websocket, msg).handle()
        elif post_type == "message":
            await MessageHandler(websocket, msg).handle()
        elif post_type == "notice":
            await NoticeHandler(websocket, msg).handle()
        elif post_type == "request":
            await RequestHandler(websocket, msg).handle()

    except Exception as e:
        logger.error(f"[{MODULE_NAME}]处理{MODULE_NAME}事件失败: {e}")
