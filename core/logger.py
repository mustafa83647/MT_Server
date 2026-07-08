import html
import threading
from datetime import datetime
from collections import deque
from core.config import MAX_LOG_LINES, ANSI_ESCAPE
class LoggerManager:
    def __init__(self):
        self.logs = deque(maxlen=MAX_LOG_LINES)
        self.lock = threading.Lock()
    def log(self, source: str, message: str, is_safe: bool = False, color: str = "#94a3b8"):
        with self.lock:
            timestamp = datetime.now().strftime("%H:%M:%S")
            clean_msg = ANSI_ESCAPE.sub('', message.strip())
            if not clean_msg: return
            if not is_safe: clean_msg = html.escape(clean_msg)
            source_color = {
                "النظام": "#0ea5e9",
                "Minecraft": "#10b981",
                "Playit": "#f59e0b",
                "أنت": "#ec4899",
                "Watchdog": "#ef4444",
                "Backup": "#8b5cf6"
            }.get(source, color)
            formatted_msg = f"<span class='log-time'>[{timestamp}]</span> <span class='log-source' style='color:{source_color};'>[{source}]</span> <span class='log-msg'>{clean_msg}</span>"
            self.logs.append(formatted_msg)
    def get_logs(self) -> list:
        with self.lock:
            return list(self.logs)
