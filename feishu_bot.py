import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Lock

from config import settings
from session_manager import SessionManager

logger = logging.getLogger(__name__)

FEISHU_MAX_TEXT_LENGTH = 30_000
PROGRESS_UPDATE_INTERVAL = 5


class FeishuBot:
    """Orchestrates Feishu message reception, agent execution, and reply sending.

    Uses the lark-oapi SDK for WebSocket connection and REST API calls.
    Agent execution runs in a ThreadPoolExecutor to not block the SDK's event loop.
    """

    def __init__(self, api_client, allowed_users: set[str] | None = None,
                 workspace_dir: str = ".", max_steps: int = 30):
        self.api_client = api_client
        self.allowed_users = allowed_users or set()
        self.workspace_dir = workspace_dir
        self.max_steps = max_steps
        self._agent_sessions: dict[str, "CodingAgent"] = {}
        self._agent_locks: dict[str, Lock] = {}
        self._lock_mutex = Lock()
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._last_progress: dict[str, float] = {}
        self._session_mgr = SessionManager()
        self._current_session_date: str | None = None
        self._start_session()

    def _start_session(self):
        """Start a new session file for today (daily rotation)."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._current_session_date != today:
            self._session_mgr.start_session(self.workspace_dir)
            self._current_session_date = today

    def _check_session_rotation(self):
        """Rotate session file if the date changed."""
        self._start_session()

    def _get_agent(self, chat_id: str) -> "CodingAgent":
        if chat_id not in self._agent_sessions:
            from agent import CodingAgent
            self._agent_sessions[chat_id] = CodingAgent(workspace_dir=self.workspace_dir)
        return self._agent_sessions[chat_id]

    def _get_lock(self, chat_id: str) -> Lock:
        with self._lock_mutex:
            if chat_id not in self._agent_locks:
                self._agent_locks[chat_id] = Lock()
            return self._agent_locks[chat_id]

    def _is_user_allowed(self, sender_id: str) -> bool:
        if not self.allowed_users:
            return True
        return sender_id in self.allowed_users

    def on_message(self, data):
        """Event handler called by the SDK when a message is received."""
        try:
            event = data.event
            if not event or not event.message:
                return

            msg = event.message
            sender = event.sender
            message_id = msg.message_id
            chat_id = msg.chat_id
            msg_type = msg.message_type

            sender_id = ""
            if sender and sender.sender_id:
                sender_id = getattr(sender.sender_id, "open_id", "") or ""

            if not self._is_user_allowed(sender_id):
                logger.info(f"Blocked message from non-allowed user: {sender_id}")
                self.api_client.reply_to_message(message_id, "Sorry, you are not authorized to use this bot.", use_card=False)
                return

            if msg_type != "text":
                return

            # Parse content (JSON string)
            try:
                content_obj = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            except (json.JSONDecodeError, TypeError):
                content_obj = {}
            text = content_obj.get("text", "").strip()

            if not text:
                return

            # Handle /clear command
            if text.lower() == "/clear":
                self._handle_clear(chat_id, message_id)
                return

            logger.info(f"Received from {sender_id} in {chat_id}: {text[:100]}")

            # Rotate session file if date changed
            self._check_session_rotation()

            lock = self._get_lock(chat_id)
            self._executor.submit(self._run_agent_task, lock, chat_id, message_id, text)
        except Exception as e:
            logger.error(f"Error in on_message handler: {e}", exc_info=True)

    def _handle_clear(self, chat_id: str, message_id: str):
        """Clear the conversation history for a chat."""
        if chat_id in self._agent_sessions:
            self._agent_sessions[chat_id].clear_history()
        self._session_mgr.save_input("/clear", prefix="Feishu Command")
        self.api_client.reply_to_message(message_id, "Conversation history cleared.", use_card=False)
        logger.info(f"Cleared history for chat {chat_id}")

    def _run_agent_task(self, lock, chat_id: str, message_id: str, user_input: str):
        with lock:
            agent = self._get_agent(chat_id)
            progress_chunks: list[str] = []

            def progress_callback(step_info: str):
                progress_chunks.append(step_info)
                now = time.time()
                last = self._last_progress.get(chat_id, 0)
                if now - last < PROGRESS_UPDATE_INTERVAL:
                    return
                self._last_progress[chat_id] = now
                combined = "\n".join(progress_chunks[-5:])[:2000]
                try:
                    self.api_client.reply_to_message(message_id, f"Working on it...\n\n{combined}", use_card=False)
                except Exception as e:
                    logger.warning(f"Failed to send progress: {e}")

            try:
                self._session_mgr.save_input(user_input, prefix="Feishu User Input")
                final_result = self._execute_agent(agent, user_input, progress_callback)
                self._session_mgr.save_summary(final_result)
                self._send_final_response(chat_id, message_id, final_result)
            except Exception as e:
                logger.error(f"Agent execution failed: {e}", exc_info=True)
                try:
                    self.api_client.reply_to_message(message_id, f"Error: Agent execution failed - {str(e)}", use_card=False)
                except Exception:
                    pass

    def _execute_agent(self, agent, user_input: str, progress_callback) -> str:
        if agent.provider == "openai":
            agent.history.append({"role": "user", "content": user_input})
        else:
            agent.history.append({
                "role": "user",
                "content": [{"type": "text", "text": user_input}],
            })

        step = 0
        while True:
            step += 1
            if self.max_steps > 0 and step > self.max_steps:
                progress_callback(f"[System] Reached max steps ({self.max_steps}). Stopping.")
                break

            try:
                if agent.provider == "openai":
                    continue_loop = self._step_openai_with_progress(agent, progress_callback, step)
                else:
                    continue_loop = self._step_anthropic_with_progress(agent, progress_callback, step)
            except Exception as e:
                progress_callback(f"[Error] Step {step} failed: {e}")
                break

            if not continue_loop:
                break

        return agent._get_summary()

    def _step_openai_with_progress(self, agent, callback, step_num) -> bool:
        response = agent.client.chat.completions.create(
            model=agent.model,
            messages=agent.history,
            tools=agent.tools.get_openai_tools(),
            tool_choice="auto",
        )

        if not hasattr(response, "choices"):
            callback("[Error] API returned non-standard response")
            return False

        msg = response.choices[0].message
        agent.history.append(msg)

        if msg.content:
            callback(f"[Thought] {msg.content[:500]}")

        if not msg.tool_calls:
            return False

        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            callback(f"[Tool] Calling {name}({{...}})")

            try:
                func = getattr(agent.tools, name)
                observation = func(**args)
            except TypeError as te:
                observation = f"Error: Invalid arguments for '{name}'. {te}"
            except Exception as e:
                observation = f"Error executing '{name}': {e}"

            callback(f"[Result] {observation[:500]}")

            agent.history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": name,
                "content": observation,
            })

        return True

    def _step_anthropic_with_progress(self, agent, callback, step_num) -> bool:
        response = agent.client.messages.create(
            model=agent.model,
            max_tokens=4000,
            system=agent.system_prompt,
            messages=agent.history,
            tools=agent.tools.get_anthropic_tools(),
        )

        agent.history.append({"role": "assistant", "content": response.content})

        has_tool_use = False
        for block in response.content:
            if block.type == "text":
                callback(f"[Thought] {block.text[:500]}")
            elif block.type == "tool_use":
                has_tool_use = True
                name = block.name
                callback(f"[Tool] Calling {name}({{...}})")

                try:
                    func = getattr(agent.tools, name)
                    observation = func(**block.input)
                except TypeError as te:
                    observation = f"Error: Invalid arguments for '{name}'. {te}"
                except Exception as e:
                    observation = f"Error executing '{name}': {e}"

                callback(f"[Result] {observation[:500]}")

                agent.history.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": observation,
                })

        return has_tool_use

    def _send_final_response(self, chat_id: str, message_id: str, text: str):
        if len(text) <= FEISHU_MAX_TEXT_LENGTH:
            try:
                self.api_client.reply_to_message(message_id, text, use_card=True)
            except Exception as e:
                logger.error(f"Failed to send final response: {e}")
        else:
            chunks = self._split_text(text, FEISHU_MAX_TEXT_LENGTH)
            for i, chunk in enumerate(chunks):
                header = f"[Part {i+1}/{len(chunks)}]\n" if len(chunks) > 1 else ""
                try:
                    if i == 0:
                        self.api_client.reply_to_message(message_id, header + chunk, use_card=True)
                    else:
                        self.api_client.send_text_message(chat_id, header + chunk, use_card=True)
                except Exception as e:
                    logger.error(f"Failed to send chunk {i+1}: {e}")

    @staticmethod
    def _split_text(text: str, max_length: int) -> list[str]:
        if len(text) <= max_length:
            return [text]
        chunks = []
        current = ""
        for line in text.split("\n"):
            if len(current) + len(line) + 1 > max_length:
                if current:
                    chunks.append(current)
                current = line
            else:
                current = current + "\n" + line if current else line
        if current:
            chunks.append(current)
        return chunks


def main():
    import signal
    import sys

    from lark_oapi import EventDispatcherHandler, LogLevel
    from lark_oapi.ws import Client as WSClient

    from feishu_api_client import FeishuAPIClient

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not settings.feishu_app_id or not settings.feishu_app_secret:
        logger.error("FEISHU_APP_ID and FEISHU_APP_SECRET must be set in .env")
        sys.exit(1)

    allowed_users = set()
    if settings.feishu_allowed_users:
        allowed_users = set(
            u.strip() for u in settings.feishu_allowed_users.split(",") if u.strip()
        )

    api_client = FeishuAPIClient(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
    )

    bot = FeishuBot(
        api_client=api_client,
        allowed_users=allowed_users,
        workspace_dir=settings.feishu_workspace_dir or ".",
        max_steps=settings.feishu_max_steps or 30,
    )

    event_handler = (
        EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(bot.on_message)
        .build()
    )

    ws_client = WSClient(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        log_level=LogLevel.INFO,
        event_handler=event_handler,
    )

    def handle_sigint(sig, frame):
        logger.info("Shutting down Feishu bot...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    logger.info(f"Starting Feishu bot (allowed users: {allowed_users or 'all'})")
    ws_client.start()


if __name__ == "__main__":
    main()
