from lark_oapi import Client, LogLevel


class FeishuAPIClient:
    """Wrapper around lark-oapi Client for sending/replying to messages."""

    def __init__(self, app_id: str, app_secret: str):
        self._client = (
            Client.builder()
            .app_id(app_id)
            .app_secret(app_secret)
            .log_level(LogLevel.INFO)
            .build()
        )

    def reply_to_message(self, message_id: str, text: str, *, use_card: bool = True) -> bool:
        """Reply to a specific message in Feishu.

        If use_card=True, sends an interactive card with markdown rendering.
        """
        import json
        from lark_oapi.api.im.v1 import (
            ReplyMessageRequest,
            ReplyMessageRequestBody,
        )

        if use_card:
            card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": "Agent Response"},
                    "template": "blue",
                },
                "elements": [
                    {"tag": "markdown", "content": text}
                ],
            }
            content = json.dumps(card)
            msg_type = "interactive"
        else:
            content = json.dumps({"text": text})
            msg_type = "text"

        req = (
            ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .msg_type(msg_type)
                .content(content)
                .build()
            )
            .build()
        )
        resp = self._client.request(req)
        if resp.code != 0:
            raise RuntimeError(f"Failed to reply: code={resp.code}, msg={resp.msg}")
        return True

    def send_text_message(self, receive_id: str, text: str, *,
                          receive_id_type: str = "chat_id", use_card: bool = True) -> bool:
        """Send a message to a Feishu chat."""
        import json
        from lark_oapi.api.im.v1 import (
            CreateMessageRequest,
            CreateMessageRequestBody,
        )

        if use_card:
            card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": "Agent Response"},
                    "template": "blue",
                },
                "elements": [
                    {"tag": "markdown", "content": text}
                ],
            }
            content = json.dumps(card)
            msg_type = "interactive"
        else:
            content = json.dumps({"text": text})
            msg_type = "text"

        req = (
            CreateMessageRequest.builder()
            .receive_id(receive_id)
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type(msg_type)
                .content(content)
                .build()
            )
            .receive_id_type(receive_id_type)
            .build()
        )
        resp = self._client.request(req)
        if resp.code != 0:
            raise RuntimeError(f"Failed to send: code={resp.code}, msg={resp.msg}")
        return True
