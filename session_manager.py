import os
from datetime import datetime


class SessionManager:
    def __init__(self, sessions_dir: str = None):
        if sessions_dir is None:
            sessions_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
        self.sessions_dir = os.path.abspath(sessions_dir)
        os.makedirs(self.sessions_dir, exist_ok=True)
        self.current_session_path = None

    def start_session(self, workspace_dir: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{timestamp}.md"
        self.current_session_path = os.path.join(self.sessions_dir, filename)
        workspace_dir = os.path.abspath(workspace_dir)

        with open(self.current_session_path, "w", encoding="utf-8") as f:
            f.write(f"# Session: {timestamp}\n\n")
            f.write(f"**Working Directory:** `{workspace_dir}`\n\n")
            f.write("---\n\n")
        return self.current_session_path

    def save_input(self, text: str, prefix: str = "User"):
        if not self.current_session_path:
            return
        with open(self.current_session_path, "a", encoding="utf-8") as f:
            f.write(f"## {prefix}\n\n{text}\n\n")

    def save_summary(self, summary: str):
        if not self.current_session_path:
            return
        with open(self.current_session_path, "a", encoding="utf-8") as f:
            f.write(f"## Agent Summary\n\n{summary}\n\n")
            f.write("---\n\n")
