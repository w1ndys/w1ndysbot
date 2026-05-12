from logger import logger

from . import MODULE_NAME
from .handlers.handle_message import MessageHandler
from .handlers.handle_meta_event import MetaEventHandler


async def handle_events(websocket, msg):
    """统一事件处理入口

    通过组合模式，将不同类型的事件分发到各个专门的处理器

    Args:
        websocket: WebSocket连接对象
        msg: 接收到的消息字典
    """
    post_type = ""
    try:
        # 回应事件当前模块暂不需要处理
        if msg.get("status") == "ok":
            return

        # 基于事件类型分发到不同的处理器
        post_type = msg.get("post_type", "")

        # 处理元事件（心跳驱动监控）
        if post_type == "meta_event":
            await MetaEventHandler(websocket, msg).handle()
            return

        # 处理消息事件（私聊命令管理监控列表）
        if post_type == "message":
            await MessageHandler(websocket, msg).handle()

    except Exception as e:
        logger.error(f"[{MODULE_NAME}]处理{MODULE_NAME}{post_type}事件失败: {e}")
