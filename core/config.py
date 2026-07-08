import os
import re
# ==========================================
# CORE CONFIGURATION & CONSTANTS
# ==========================================
DATA_DIR = "/data/minecraft_data"
APP_DIR = "/app/minecraft"
PASSWORD = os.environ.get("PANEL_PASSWORD", "2938")
FLASK_SECRET = os.environ.get("FLASK_SECRET", f"enterprise-secret-{PASSWORD}")
MAX_LOG_LINES = 2000
AUTO_BACKUP_INTERVAL_HOURS = 6
WATCHDOG_CHECK_INTERVAL = 10
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
PLAYER_JOIN_REGEX = re.compile(r': ([a-zA-Z0-9_]{3,16}) joined the game')
PLAYER_LEAVE_REGEX = re.compile(r': ([a-zA-Z0-9_]{3,16}) left the game')
SERVER_PROPERTIES_SCHEMA = [
    {"key": "motd", "label": "رسالة الترحيب (MOTD)", "type": "text", "default": "A Minecraft Server"},
    {"key": "max-players", "label": "أقصى عدد لاعبين", "type": "number", "default": "20"},
    {"key": "difficulty", "label": "مستوى الصعوبة", "type": "select", "options": ["peaceful", "easy", "normal", "hard"], "default": "easy"},
    {"key": "pvp", "label": "القتال بين اللاعبين (PVP)", "type": "boolean", "default": "true"},
    {"key": "hardcore", "label": "وضع الهاردكور", "type": "boolean", "default": "false"},
    {"key": "view-distance", "label": "مسافة الرؤية", "type": "number", "default": "10"},
    {"key": "simulation-distance", "label": "مسافة المحاكاة", "type": "number", "default": "10"},
    {"key": "allow-nether", "label": "تفعيل النذر", "type": "boolean", "default": "true"},
    {"key": "allow-flight", "label": "السماح بالطيران", "type": "boolean", "default": "false"},
    {"key": "enable-command-block", "label": "تفعيل الكوماند بلوك", "type": "boolean", "default": "false"},
    {"key": "white-list", "label": "تفعيل القائمة البيضاء", "type": "boolean", "default": "false"},
    {"key": "enforce-secure-profile", "label": "تشفير الشات", "type": "boolean", "default": "false"},
    {"key": "online-mode", "label": "حسابات أصلية فقط", "type": "boolean", "default": "false"}
]
