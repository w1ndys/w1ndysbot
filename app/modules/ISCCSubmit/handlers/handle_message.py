from .handle_message_private import PrivateMessageHandler


class MessageHandler:
    def __init__(self, websocket, msg):
        self.websocket = websocket
        self.msg = msg
        self.message_type = msg.get("message_type", "")

    async def handle(self):
        if self.message_type == "private":
            await PrivateMessageHandler(self.websocket, self.msg).handle()
