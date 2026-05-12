from .handle_message_group import GroupMessageHandler


class MessageHandler:
    def __init__(self, websocket, msg):
        self.websocket = websocket
        self.msg = msg
        self.message_type = msg.get("message_type", "")

    async def handle(self):
        if self.message_type == "group":
            await GroupMessageHandler(self.websocket, self.msg).handle()
