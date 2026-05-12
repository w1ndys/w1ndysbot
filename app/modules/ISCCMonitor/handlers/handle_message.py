from .handle_message_private import PrivateMessageHandler


class MessageHandler:
    """消息处理器：本模块只处理私聊消息，用于管理员管理监控列表。"""

    def __init__(self, websocket, msg):
        self.websocket = websocket
        self.msg = msg
        self.message_type = msg.get("message_type", "")

    async def handle(self):
        if self.message_type == "private":
            await PrivateMessageHandler(self.websocket, self.msg).handle()
