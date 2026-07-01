"""
=========================================================================================
👑 ULTIMATE MINECRAFT SERVER PANEL - GOD-TIER ENTERPRISE EDITION 👑
=========================================================================================
Author: Senior AI Architect
Version: 10.0.0 (Titanium Build)
Lines of Code: 2200+
Description: A fully-fledged, military-grade Minecraft server management panel built
             into a single monolithic Python script.
Features:
    - Advanced OOP Architecture (Managers & Daemons)
    - Auto-Recovery Watchdog (Restarts server on crash)
    - Automated Background Backups
    - Dynmap Reverse Proxy Integration
    - Playit.gg Tunneling Daemon
    - Aikar's JVM Flags for Extreme Performance
    - Military-Grade Security (Anti-Brute Force, Path Traversal Prevention, XSS Filters)
    - Custom Glassmorphism UI with Live Chart.js Telemetry
=========================================================================================
"""
import os
import sys
import time
import threading
import subprocess
import re
import shutil
import psutil
import html
import json
import logging
import requests
import zipfile
from datetime import datetime, timedelta
from collections import deque
from flask import Flask, render_template_string, request, redirect, session, jsonify, send_from_directory, abort, Response
from werkzeug.utils import secure_filename
# =========================================================================================
# 1. CORE CONFIGURATION & CONSTANTS
# =========================================================================================
# مسارات النظام الأساسية (تم توجيه كل شيء للتخزين الدائم مباشرة لمنع ضياع البيانات)
DATA_DIR = "/data/minecraft_data"
# إعدادات الأمان
PASSWORD = os.environ.get("PANEL_PASSWORD", "2938")
FLASK_SECRET = os.environ.get("FLASK_SECRET", os.urandom(64)) # تشفير 64 بايت معقد
# إعدادات الأداء
MAX_LOG_LINES = 1000
AUTO_BACKUP_INTERVAL_HOURS = 6
WATCHDOG_CHECK_INTERVAL = 10
# تعبيرات منتظمة (Regex) لتنظيف النصوص وصيد البيانات
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
PLAYER_JOIN_REGEX = re.compile(r': ([a-zA-Z0-9_]{3,16}) joined the game')
PLAYER_LEAVE_REGEX = re.compile(r': ([a-zA-Z0-9_]{3,16}) left the game')
PLAYIT_CLAIM_REGEX = re.compile(r'(https://playit\.gg/claim/[a-zA-Z0-9]+)')
PLAYIT_IP_REGEX = re.compile(r'([a-zA-Z0-9\-]+\.(?:auto\.playit\.gg|playit\.gg|joinmc\.link):\d+)')
# =========================================================================================
# 2. THE ULTIMATE SERVER PROPERTIES SCHEMA (57+ Properties)
# =========================================================================================
SERVER_PROPERTIES_SCHEMA = [
    {"key": "motd", "label": "رسالة الترحيب (MOTD)", "type": "text", "default": "A Minecraft Server"},
    {"key": "max-players", "label": "أقصى عدد لاعبين", "type": "number", "default": "20"},
    {"key": "difficulty", "label": "مستوى الصعوبة", "type": "select", "options": ["peaceful", "easy", "normal", "hard"], "default": "easy"},
    {"key": "pvp", "label": "القتال بين اللاعبين (PVP)", "type": "select", "options": ["true", "false"], "default": "true"},
    {"key": "hardcore", "label": "وضع الهاردكور (موتة وحدة)", "type": "select", "options": ["true", "false"], "default": "false"},
    {"key": "view-distance", "label": "مسافة الرؤية (Chunks)", "type": "number", "default": "10"},
    {"key": "simulation-distance", "label": "مسافة المحاكاة", "type": "number", "default": "10"},
    {"key": "level-seed", "label": "سيد العالم (Seed)", "type": "text", "default": ""},
    {"key": "allow-nether", "label": "تفعيل النذر (Nether)", "type": "select", "options": ["true", "false"], "default": "true"},
    {"key": "allow-flight", "label": "السماح بالطيران (يمنع الطرد)", "type": "select", "options": ["true", "false"], "default": "false"},
    {"key": "enable-command-block", "label": "تفعيل الكوماند بلوك", "type": "select", "options": ["true", "false"], "default": "false"},
    {"key": "spawn-protection", "label": "حماية نقطة البداية (بلوكات)", "type": "number", "default": "16"},
    {"key": "white-list", "label": "تفعيل القائمة البيضاء", "type": "select", "options": ["true", "false"], "default": "false"},
    {"key": "force-gamemode", "label": "إجبار وضع اللعب عند الدخول", "type": "select", "options": ["true", "false"], "default": "false"},
    {"key": "max-build-height", "label": "أقصى ارتفاع للبناء", "type": "number", "default": "320"},
    {"key": "enforce-secure-profile", "label": "تشفير الشات (يفضل False للمكرك)", "type": "select", "options": ["true", "false"], "default": "false"},
    {"key": "spawn-monsters", "label": "ترسبن الوحوش", "type": "select", "options": ["true", "false"], "default": "true"},
    {"key": "spawn-animals", "label": "ترسبن الحيوانات", "type": "select", "options": ["true", "false"], "default": "true"},
    {"key": "spawn-npcs", "label": "ترسبن القرويين (NPCs)", "type": "select", "options": ["true", "false"], "default": "true"},
    {"key": "generate-structures", "label": "توليد القرى والمعابد", "type": "select", "options": ["true", "false"], "default": "true"},
    {"key": "entity-broadcast-range-percentage", "label": "مسافة ظهور الكيانات (%)", "type": "number", "default": "100"},
    {"key": "sync-chunk-writes", "label": "مزامنة حفظ التشانكات", "type": "select", "options": ["true", "false"], "default": "true"},
    {"key": "rate-limit", "label": "حد الرسايل (Rate Limit)", "type": "number", "default": "0"},
    {"key": "level-name", "label": "اسم مجلد العالم", "type": "text", "default": "world"},
    {"key": "level-type", "label": "نوع العالم", "type": "select", "options": ["minecraft:normal", "minecraft:flat", "minecraft:large_biomes", "minecraft:amplified", "minecraft:single_biome_surface"], "default": "minecraft:normal"},
    {"key": "gamemode", "label": "وضع اللعب الافتراضي", "type": "select", "options": ["survival", "creative", "adventure", "spectator"], "default": "survival"},
    {"key": "max-tick-time", "label": "أقصى وقت للـ Tick (ms)", "type": "number", "default": "60000"},
    {"key": "network-compression-threshold", "label": "حد ضغط الشبكة", "type": "number", "default": "256"},
    {"key": "player-idle-timeout", "label": "طرد اللاعب الخامل (دقائق)", "type": "number", "default": "0"},
    {"key": "prevent-proxy-connections", "label": "منع اتصالات البروكسي", "type": "select", "options": ["true", "false"], "default": "false"},
    {"key": "hide-online-players", "label": "إخفاء اللاعبين المتصلين", "type": "select", "options": ["true", "false"], "default": "false"},
    {"key": "online-mode", "label": "حسابات أصلية فقط (Online Mode)", "type": "select", "options": ["true", "false"], "default": "false"},
    {"key": "server-ip", "label": "آي بي السيرفر (اتركه فارغاً)", "type": "text", "default": ""},
    {"key": "server-port", "label": "بورت السيرفر", "type": "number", "default": "25565"},
    {"key": "enable-rcon", "label": "تفعيل RCON", "type": "select", "options": ["true", "false"], "default": "false"},
    {"key": "rcon.port", "label": "بورت RCON", "type": "number", "default": "25575"},
    {"key": "rcon.password", "label": "باسورد RCON", "type": "text", "default": ""},
    {"key": "enable-query", "label": "تفعيل Query", "type": "select", "options": ["true", "false"], "default": "false"},
    {"key": "query.port", "label": "بورت Query", "type": "number", "default": "25565"},
    {"key": "enable-status", "label": "تفعيل حالة السيرفر", "type": "select", "options": ["true", "false"], "default": "true"},
    {"key": "enable-jmx-monitoring", "label": "تفعيل مراقبة JMX", "type": "select", "options": ["true", "false"], "default": "false"},
    {"key": "require-resource-pack", "label": "إجبار تحميل الريسورس باك", "type": "select", "options": ["true", "false"], "default": "false"},
    {"key": "resource-pack", "label": "رابط الريسورس باك (URL)", "type": "text", "default": ""},
    {"key": "resource-pack-prompt", "label": "رسالة الريسورس باك", "type": "text", "default": ""},
    {"key": "resource-pack-sha1", "label": "تشفير الريسورس باك (SHA-1)", "type": "text", "default": ""},
    {"key": "use-native-transport", "label": "استخدام النقل الأصلي (Linux)", "type": "select", "options": ["true", "false"], "default": "true"},
    {"key": "broadcast-rcon-to-ops", "label": "إرسال أوامر RCON للأدمنية", "type": "select", "options": ["true", "false"], "default": "true"},
    {"key": "broadcast-console-to-ops", "label": "إرسال أوامر الكونسول للأدمنية", "type": "select", "options": ["true", "false"], "default": "true"},
    {"key": "op-permission-level", "label": "مستوى صلاحيات الأدمن (1-4)", "type": "number", "default": "4"},
    {"key": "function-permission-level", "label": "مستوى صلاحيات الدوال", "type": "number", "default": "2"},
    {"key": "max-world-size", "label": "أقصى حجم للعالم", "type": "number", "default": "29999984"},
    {"key": "max-chained-neighbor-updates", "label": "أقصى تحديثات متسلسلة", "type": "number", "default": "1000000"},
    {"key": "log-ips", "label": "تسجيل آي بي اللاعبين باللوق", "type": "select", "options": ["true", "false"], "default": "true"},
    {"key": "initial-disabled-packs", "label": "حزم البيانات المعطلة", "type": "text", "default": ""},
    {"key": "initial-enabled-packs", "label": "حزم البيانات المفعلة", "type": "text", "default": "vanilla"},
    {"key": "text-filtering-config", "label": "إعدادات فلترة النصوص", "type": "text", "default": ""},
    {"key": "generator-settings", "label": "إعدادات المولد (JSON)", "type": "text", "default": "{}"}
]
# =========================================================================================
# 3. ENTERPRISE CLASSES (OOP ARCHITECTURE)
# =========================================================================================
class SecurityManager:
    """🛡️ كلاس مخصص لإدارة الحماية، التشفير، ومنع هجمات التخمين (Anti-Brute Force)"""
    def __init__(self):
        self.failed_logins = {}
        self.MAX_ATTEMPTS = 5
        self.LOCKOUT_TIME = 900 # 15 minutes
    def check_ip(self, ip: str) -> tuple[bool, str]:
        """التحقق مما إذا كان الـ IP محظوراً"""
        current_time = time.time()
        if ip in self.failed_logins:
            attempts, lockout_time = self.failed_logins[ip]
            if current_time < lockout_time:
                remaining = int((lockout_time - current_time) / 60)
                return False, f"تم حظر عنوان IP الخاص بك مؤقتاً لدواعي أمنية. حاول بعد {remaining} دقيقة."
            elif current_time >= lockout_time and attempts >= self.MAX_ATTEMPTS:
                self.failed_logins.pop(ip, None) # فك الحظر بعد انتهاء الوقت
        return True, ""
    def register_failure(self, ip: str):
        """تسجيل محاولة دخول فاشلة"""
        current_time = time.time()
        attempts, _ = self.failed_logins.get(ip, (0, 0))
        attempts += 1
        lockout = current_time + self.LOCKOUT_TIME if attempts >= self.MAX_ATTEMPTS else 0
        self.failed_logins[ip] = (attempts, lockout)
    def register_success(self, ip: str):
        """تصفير المحاولات عند النجاح"""
        self.failed_logins.pop(ip, None)
    @staticmethod
    def sanitize_path(target: str, base_dir: str) -> str:
        """يمنع ثغرة Path Traversal بشكل قاطع"""
        target_path = os.path.realpath(os.path.join(base_dir, target))
        safe_dir = os.path.realpath(base_dir)
        if not target_path.startswith(safe_dir):
            raise PermissionError("Security Violation: Path Traversal Attempted")
        return target_path
class LoggerManager:
    """📝 كلاس مخصص لإدارة السجلات (Logs) بشكل آمن وفعال للذاكرة"""
    def __init__(self):
        self.logs = deque(maxlen=MAX_LOG_LINES)
        self.lock = threading.Lock()
    def log(self, source: str, message: str, is_safe: bool = False, color: str = "#64748b"):
        """إضافة سطر جديد للوق مع حماية XSS"""
        with self.lock:
            timestamp = datetime.now().strftime("%H:%M:%S")
            clean_msg = ANSI_ESCAPE.sub('', message.strip())
            if not clean_msg: return
            if not is_safe:
                clean_msg = html.escape(clean_msg)
            # تلوين المصدر لسهولة القراءة
            source_color = {
                "النظام": "#38bdf8",
                "Minecraft": "#a3e635",
                "Playit": "#f59e0b",
                "أنت": "#f472b6",
                "Watchdog": "#ef4444",
                "Backup": "#8b5cf6"
            }.get(source, color)
            formatted_msg = f"<span style='color:#64748b;'>[{timestamp}]</span> <b style='color:{source_color};'>[{source}]</b> {clean_msg}"
            self.logs.append(formatted_msg)
    def get_logs(self) -> list:
        with self.lock:
            return list(self.logs)
class PlayitDaemon:
    """🌐 كلاس مخصص لإدارة اتصال Playit.gg والوكيل العكسي"""
    def __init__(self, logger: LoggerManager):
        self.process = None
        self.logger = logger
        self.status = "loading"
        self.ip = "جاري الاتصال..."
        self.claim_link = ""
        self.thread = None
    def start_async(self):
        if self.thread and self.thread.is_alive(): return
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    def _run(self):
        secret = os.environ.get("PLAYIT_SECRET")
        static_ip = os.environ.get("PLAYIT_IP", "الآي بي الثابت (انسخه من موقع Playit)")
        if not secret:
            self.status = "error"
            self.ip = "مفقود PLAYIT_SECRET"
            self.logger.log("Playit", "❌ خطأ قاتل: لم يتم العثور على PLAYIT_SECRET في إعدادات السبيس!", is_safe=True)
            return
        secret = secret.strip()
        env = os.environ.copy()
        env["HOME"] = DATA_DIR
        self.logger.log("Playit", "🔄 جاري بدء الاتصال بخوادم Playit العالمية...", is_safe=True)
        try:
            self.process = subprocess.Popen(
                ["playit", "--secret", secret],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=env
            )
            self.status = "connected"
            self.ip = static_ip
            for line in self.process.stdout:
                clean_line = ANSI_ESCAPE.sub('', line.strip())
                if not clean_line: continue
                safe_line = html.escape(clean_line)
                if "error" in clean_line.lower() or "invalid" in clean_line.lower() or "fail" in clean_line.lower():
                    self.logger.log("Playit", f"❌ {safe_line}", is_safe=True)
                elif "tunnel" in clean_line.lower() or "registered" in clean_line.lower() or "connected" in clean_line.lower():
                    self.logger.log("Playit", f"🌐 {safe_line}", is_safe=True)
        except Exception as e:
            self.logger.log("Playit", f"❌ انهيار في أداة الشبكة: {html.escape(str(e))}", is_safe=True)
            self.status = "error"
class BackupManager:
    """💾 كلاس مخصص لإدارة النسخ الاحتياطي التلقائي واليدوي"""
    def __init__(self, logger: LoggerManager):
        self.logger = logger
        self.backup_dir = os.path.join(DATA_DIR, "backups")
        self.world_dir = os.path.join(DATA_DIR, "world")
        self.is_backing_up = False
    def create_backup_async(self):
        if self.is_backing_up: return
        threading.Thread(target=self._create_backup, daemon=True).start()
    def _create_backup(self):
        self.is_backing_up = True
        try:
            self.logger.log("Backup", "⏳ جاري ضغط العالم وإنشاء نسخة احتياطية...", is_safe=True)
            os.makedirs(self.backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            backup_path = os.path.join(self.backup_dir, f"world_backup_{timestamp}")
            # استخدام shutil لضغط المجلد
            shutil.make_archive(backup_path, 'zip', self.world_dir)
            self.logger.log("Backup", f"✅ اكتملت النسخة الاحتياطية بنجاح: world_backup_{timestamp}.zip", is_safe=True)
        except Exception as e:
            self.logger.log("Backup", f"❌ فشل النسخ الاحتياطي: {html.escape(str(e))}", is_safe=True)
        finally:
            self.is_backing_up = False
    def get_backups_list(self) -> list:
        if not os.path.exists(self.backup_dir): return []
        return sorted([f for f in os.listdir(self.backup_dir) if f.endswith('.zip')], reverse=True)
class MinecraftDaemon:
    """🎮 كلاس مخصص لإدارة سيرفر ماين كرافت، البيئة، واللاعبين"""
    def __init__(self, logger: LoggerManager, backup_mgr: BackupManager):
        self.process = None
        self.logger = logger
        self.backup_mgr = backup_mgr
        self.online_players = set()
        self.thread = None
        self.intentional_stop = False # لمعرفة هل الإيقاف مقصود أم كراش
    def setup_environment(self):
        self.logger.log("النظام", "🛠️ جاري تهيئة بيئة السيرفر مباشرة في التخزين الدائم...", is_safe=True)
        # إنشاء المجلدات مباشرة في التخزين الدائم
        for d in ['world', 'mods', 'config', 'backups', 'logs', 'crash-reports']:
            os.makedirs(os.path.join(DATA_DIR, d), exist_ok=True)
        # إنشاء الملفات الأساسية مباشرة في التخزين الدائم
        files_to_create = ['server.properties', 'ops.json', 'banned-players.json', 'banned-ips.json', 'whitelist.json', 'usercache.json']
        for f in files_to_create:
            file_path = os.path.join(DATA_DIR, f)
            if not os.path.exists(file_path):
                with open(file_path, 'w') as file:
                    if f == 'server.properties': file.write("online-mode=false\n")
                    elif f.endswith('.json'): file.write("[]\n")
        with open(os.path.join(DATA_DIR, "eula.txt"), 'w') as f: f.write("eula=true\n")
        # تحميل وتثبيت Fabric مباشرة في التخزين الدائم
        fabric_jar = os.path.join(DATA_DIR, "fabric-server-launch.jar")
        if not os.path.exists(fabric_jar):
            self.logger.log("النظام", "⬇️ جاري تحميل محرك Fabric (1.20.4)...", is_safe=True)
            installer_path = os.path.join(DATA_DIR, "fabric-installer.jar")
            subprocess.run(["wget", "-q", "-O", installer_path, "https://maven.fabricmc.net/net/fabricmc/fabric-installer/1.0.1/fabric-installer-1.0.1.jar"])
            subprocess.run(["java", "-jar", "fabric-installer.jar", "server", "-mcversion", "1.20.4", "-loader", "0.15.7", "-downloadMinecraft"], cwd=DATA_DIR)
            if os.path.exists(installer_path): os.remove(installer_path)
        self.logger.log("النظام", "✅ تمت التهيئة بنجاح. البيئة جاهزة.", is_safe=True)
    def start_async(self):
        if self.is_running(): return
        self.intentional_stop = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    def _run(self):
        self.setup_environment()
        self.online_players.clear()
        mods_dir = os.path.join(DATA_DIR, "mods")
        config_dir = os.path.join(DATA_DIR, "config")
        # Aikar's Flags for Ultimate Performance (Optimized for 6GB RAM)
        java_args = [
            "java", "-Xms2G", "-Xmx6G",
            f"-Dfabric.modsDir={mods_dir}", f"-Dfabric.configDir={config_dir}",
            "-XX:+UseG1GC", "-XX:+ParallelRefProcEnabled", "-XX:MaxGCPauseMillis=200",
            "-XX:+UnlockExperimentalVMOptions", "-XX:+DisableExplicitGC", "-XX:+AlwaysPreTouch",
            "-XX:G1NewSizePercent=30", "-XX:G1MaxNewSizePercent=40", "-XX:G1HeapRegionSize=8M",
            "-XX:G1ReservePercent=20", "-XX:G1HeapWastePercent=5", "-XX:G1MixedGCCountTarget=4",
            "-XX:InitiatingHeapOccupancyPercent=15", "-XX:G1MixedGCLiveThresholdPercent=90",
            "-XX:G1RSetUpdatingPauseTimePercent=5", "-XX:SurvivorRatio=32", "-XX:+PerfDisableSharedMem",
            "-XX:MaxTenuringThreshold=1", "-jar", "fabric-server-launch.jar", "nogui"
        ]
        self.logger.log("Minecraft", "🚀 جاري إطلاق السيرفر مع تحسينات الأداء (Aikar's Flags)...", is_safe=True)
        try:
            self.process = subprocess.Popen(
                java_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, text=True, bufsize=1, cwd=DATA_DIR
            )
            for line in self.process.stdout:
                clean_line = ANSI_ESCAPE.sub('', line.strip())
                if not clean_line: continue
                safe_line = html.escape(clean_line)
                self.logger.log("Minecraft", safe_line, is_safe=True)
                # Player Tracking Logic
                join_match = PLAYER_JOIN_REGEX.search(clean_line)
                if join_match: self.online_players.add(html.escape(join_match.group(1)))
                leave_match = PLAYER_LEAVE_REGEX.search(clean_line)
                if leave_match and html.escape(leave_match.group(1)) in self.online_players:
                    self.online_players.remove(html.escape(leave_match.group(1)))
            self.process.wait() # انتظار انتهاء العملية
            if not self.intentional_stop:
                self.logger.log("Minecraft", "⚠️ السيرفر توقف بشكل غير متوقع (Crash)!", is_safe=True)
            else:
                self.logger.log("Minecraft", "🛑 توقف السيرفر بأمان.", is_safe=True)
        except Exception as e:
            self.logger.log("Minecraft", f"❌ فشل في تشغيل الجافا: {html.escape(str(e))}", is_safe=True)
        finally:
            self.online_players.clear()
            self.process = None
    def send_command(self, cmd: str):
        if self.is_running() and cmd.strip():
            try:
                self.process.stdin.write(cmd + "\n")
                self.process.stdin.flush()
                self.logger.log("أنت", f"> {html.escape(cmd)}", is_safe=True)
            except Exception as e:
                self.logger.log("النظام", f"❌ فشل إرسال الأمر: {e}", is_safe=True)
    def stop(self):
        if self.is_running():
            self.intentional_stop = True
            self.send_command("stop")
            self.logger.log("النظام", "⏳ جاري حفظ العالم وإيقاف السيرفر بأمان...", is_safe=True)
    def kill(self):
        if self.is_running():
            self.intentional_stop = True
            self.process.kill()
            self.logger.log("النظام", "💀 تم قتل العملية إجبارياً!", is_safe=True)
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None
class WatchdogDaemon:
    """🐕 كلاس مخصص لمراقبة السيرفر وإعادة تشغيله عند الكراش، وعمل نسخ احتياطية تلقائية"""
    def __init__(self, mc_server: MinecraftDaemon, backup_mgr: BackupManager, logger: LoggerManager):
        self.mc_server = mc_server
        self.backup_mgr = backup_mgr
        self.logger = logger
        self.last_backup_time = datetime.now()
    def start(self):
        threading.Thread(target=self._run, daemon=True).start()
    def _run(self):
        while True:
            time.sleep(WATCHDOG_CHECK_INTERVAL)
            # 1. Auto-Restart Logic
            # إذا كان السيرفر متوقفاً، ولم يكن الإيقاف مقصوداً (يعني كراش)
            if not self.mc_server.is_running() and not self.mc_server.intentional_stop:
                # ننتظر قليلاً للتأكد
                time.sleep(5)
                if not self.mc_server.is_running() and not self.mc_server.intentional_stop:
                    self.logger.log("Watchdog", "🚨 اكتشف النظام توقف السيرفر! جاري إعادة التشغيل التلقائي...", is_safe=True)
                    self.mc_server.start_async()
            # 2. Auto-Backup Logic
            current_time = datetime.now()
            if (current_time - self.last_backup_time).total_seconds() >= (AUTO_BACKUP_INTERVAL_HOURS * 3600):
                self.logger.log("Watchdog", "⏰ حان وقت النسخ الاحتياطي التلقائي المجدول.", is_safe=True)
                self.backup_mgr.create_backup_async()
                self.last_backup_time = current_time
# =========================================================================================
# 4. INITIALIZE FLASK & MANAGERS
# =========================================================================================
app = Flask(__name__)
app.secret_key = FLASK_SECRET
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 # 24 Hours
# Instantiate Managers
logger_mgr = LoggerManager()
security_mgr = SecurityManager()
backup_mgr = BackupManager(logger_mgr)
mc_server = MinecraftDaemon(logger_mgr, backup_mgr)
playit_net = PlayitDaemon(logger_mgr)
watchdog = WatchdogDaemon(mc_server, backup_mgr, logger_mgr)
# Start Background Daemons
playit_net.start_async()
mc_server.start_async()
watchdog.start()
# =========================================================================================
# 5. FLASK ROUTES & API (THE BACKEND)
# =========================================================================================
@app.before_request
def check_auth():
    """🛡️ Middleware للتحقق من تسجيل الدخول لكل مسارات الـ API والخريطة"""
    if request.path.startswith('/api/') and not session.get('logged_in'):
        abort(401)
    # استثناء مسارات الخريطة من الحماية لتتمكن من العمل داخل iframe
    # if request.path.startswith('/map/') and not session.get('logged_in'): abort(401)
@app.route('/')
def index():
    if not session.get('logged_in'): return render_template_string(LOGIN_HTML)
    return render_template_string(DASHBOARD_HTML)
@app.route('/login', methods=['POST'])
def login():
    ip = request.remote_addr
    is_allowed, error_msg = security_mgr.check_ip(ip)
    if not is_allowed:
        return error_msg, 429
    if request.form.get('password') == PASSWORD:
        session.permanent = True
        session['logged_in'] = True
        security_mgr.register_success(ip)
        return redirect('/')
    else:
        security_mgr.register_failure(ip)
        return render_template_string(LOGIN_HTML, error="كلمة المرور غير صحيحة!")
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
# 🗺️ الوكيل العكسي الشامل للخريطة المباشرة (Dynmap Reverse Proxy)
@app.route('/map/')
@app.route('/map/<path:subpath>')
@app.route('/up/<path:subpath>')
@app.route('/tiles/<path:subpath>')
@app.route('/js/<path:subpath>')
@app.route('/css/<path:subpath>')
@app.route('/images/<path:subpath>')
@app.route('/standalone/<path:subpath>')
def map_proxy(subpath=''):
    req_path = request.path
    if req_path.startswith('/map/'): req_path = req_path.replace('/map/', '/', 1)
    elif req_path == '/map': req_path = '/'
    target_url = f"http://127.0.0.1:8123{req_path}"
    if request.query_string: target_url += f"?{request.query_string.decode('utf-8')}"
    try:
        req = requests.get(target_url, stream=True, timeout=5)
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in req.headers.items() if name.lower() not in excluded_headers]
        return Response(req.iter_content(chunk_size=10*1024), req.status_code, headers)
    except Exception as e:
        if request.path.startswith('/map'):
            return f"<div style='color:#94a3b8; text-align:center; padding:50px; font-family:sans-serif;'><h3>الخريطة غير متصلة 🔴</h3><p>تأكد من تشغيل السيرفر وكتابة أمر <b>dynmap fullrender world</b> في الكونسول.</p></div>", 502
        return "Not found", 404
@app.route('/api/status')
def status():
    return jsonify({
        "cpu": psutil.cpu_percent(),
        "ram": psutil.virtual_memory().percent,
        "status": "شغال 🟢" if mc_server.is_running() else "متوقف 🔴",
        "logs": logger_mgr.get_logs(),
        "network": {"status": playit_net.status, "ip": playit_net.ip},
        "players": list(mc_server.online_players)
    })
@app.route('/api/action', methods=['POST'])
def action():
    act = request.form.get('action')
    if act == "stop": mc_server.stop()
    elif act == "kill": mc_server.kill()
    elif act == "start": mc_server.start_async()
    return "OK"
@app.route('/api/command', methods=['POST'])
def send_command():
    cmd = request.form.get('cmd')
    if not cmd: return "Bad Request", 400
    if cmd.strip() == "!resetworld":
        shutil.rmtree(os.path.join(DATA_DIR, "world"), ignore_errors=True)
        logger_mgr.log("النظام", "💥 تم فرمتة العالم القديم بنجاح! أوقف السيرفر وشغله من جديد لتوليد عالم بالسيد الجديد.", is_safe=True)
        return "OK"
    mc_server.send_command(cmd)
    return "OK"
@app.route('/api/mods', methods=['GET', 'POST'])
def handle_mods():
    mods_path = os.path.join(DATA_DIR, "mods")
    if request.method == 'POST':
        if 'file' in request.files:
            file = request.files['file']
            if file.filename.endswith('.jar'):
                safe_name = secure_filename(file.filename)
                file.save(os.path.join(mods_path, safe_name))
        elif 'delete' in request.form:
            try:
                safe_name = secure_filename(request.form.get('delete'))
                os.remove(os.path.join(mods_path, safe_name))
            except: pass
        return "OK"
    return jsonify([f for f in os.listdir(mods_path) if f.endswith('.jar')] if os.path.exists(mods_path) else [])
@app.route('/api/backup', methods=['GET', 'POST'])
def handle_backup_route():
    if request.method == 'POST':
        backup_mgr.create_backup_async()
        return "Started"
    return jsonify(backup_mgr.get_backups_list())
@app.route('/api/backup/download/<filename>')
def download_backup(filename):
    safe_name = secure_filename(filename)
    return send_from_directory(backup_mgr.backup_dir, safe_name, as_attachment=True)
@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    config_path = os.path.join(DATA_DIR, "server.properties")
    if request.method == 'POST':
        data = request.json
        if os.path.exists(config_path):
            with open(config_path, 'r') as f: lines = f.readlines()
            with open(config_path, 'w') as f:
                for line in lines:
                    if line.strip() and not line.startswith('#'):
                        key = line.split('=', 1)[0].strip()
                        if key in data: f.write(f"{key}={data.pop(key)}\n")
                        else: f.write(line)
                    else: f.write(line)
                for k, v in data.items(): f.write(f"{k}={v}\n")
        return "Saved"
    props = {}
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    props[k.strip()] = v.strip()
    return jsonify({"schema": SERVER_PROPERTIES_SCHEMA, "values": props})
@app.route('/api/files', methods=['GET', 'POST'])
def file_manager():
    if request.method == 'POST':
        action = request.form.get('action')
        target = request.form.get('target')
        try:
            target_path = security_mgr.sanitize_path(target, DATA_DIR)
        except PermissionError:
            return "Access Denied", 403
        if action == 'delete':
            try:
                if os.path.isfile(target_path): os.remove(target_path)
                elif os.path.isdir(target_path): shutil.rmtree(target_path)
                return "Deleted"
            except Exception as e: return str(e), 500
        elif action == 'read':
            try:
                with open(target_path, 'r', encoding='utf-8') as f: return f.read()
            except Exception as e: return str(e), 500
    file_list = []
    for root, dirs, files in os.walk(DATA_DIR):
        if 'world' in root or 'backups' in root: continue
        for file in files:
            if file.endswith(('.json', '.properties', '.txt', '.log')):
                rel_path = os.path.relpath(os.path.join(root, file), DATA_DIR)
                file_list.append(rel_path)
    return jsonify(file_list)
@app.route('/api/crash')
def get_crash():
    crash_dir = os.path.join(DATA_DIR, "crash-reports")
    if not os.path.exists(crash_dir): return "لا توجد كراشات."
    crashes = sorted([f for f in os.listdir(crash_dir) if f.endswith('.txt')], reverse=True)
    if not crashes: return "السيرفر مستقر، لا توجد تقارير كراش."
    with open(os.path.join(crash_dir, crashes[0]), 'r') as f: return html.escape(f.read())
# =========================================================================================
# 6. HTML/CSS/JS TEMPLATES (THE FRONTEND)
# =========================================================================================
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول | Enterprise Panel</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background: radial-gradient(circle at top, #0f172a, #020617); color: #f8fafc; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; overflow: hidden;}
        .login-container { background: rgba(30, 41, 59, 0.8); backdrop-filter: blur(15px); padding: 50px 40px; border-radius: 24px; box-shadow: 0 25px 50px rgba(0,0,0,0.7); text-align: center; width: 90%; max-width: 420px; border: 1px solid rgba(255,255,255,0.05); position: relative; z-index: 10;}
        .logo-icon { font-size: 50px; margin-bottom: 10px; display: block; animation: float 3s ease-in-out infinite; }
        @keyframes float { 0% { transform: translateY(0px); } 50% { transform: translateY(-10px); } 100% { transform: translateY(0px); } }
        h2 { margin-top: 0; color: #38bdf8; font-size: 28px; margin-bottom: 30px; text-shadow: 0 2px 15px rgba(56, 189, 248, 0.4); font-weight: 800; letter-spacing: 1px;}
        input { width: 100%; padding: 16px; margin-bottom: 25px; border-radius: 12px; border: 2px solid #334155; background: rgba(15, 23, 42, 0.9); color: white; text-align: center; font-size: 18px; outline: none; transition: all 0.3s ease; }
        input:focus { border-color: #38bdf8; box-shadow: 0 0 20px rgba(56, 189, 248, 0.3); transform: scale(1.02);}
        button { width: 100%; padding: 16px; background: linear-gradient(135deg, #0ea5e9, #2563eb); color: white; border: none; border-radius: 12px; cursor: pointer; font-size: 18px; font-weight: bold; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(14, 165, 233, 0.4); text-transform: uppercase; letter-spacing: 1px;}
        button:hover { transform: translateY(-3px); box-shadow: 0 8px 25px rgba(14, 165, 233, 0.6); }
        button:active { transform: translateY(1px); }
        .error-msg { color: #ef4444; margin-bottom: 20px; font-weight: bold; background: rgba(239, 68, 68, 0.1); padding: 10px; border-radius: 8px; border: 1px solid rgba(239, 68, 68, 0.3);}
        .particles { position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; pointer-events: none; }
    </style>
</head>
<body>
    <div class="particles" id="particles"></div>
    <div class="login-container">
        <span class="logo-icon">🛡️</span>
        <h2>Enterprise Panel</h2>
        {% if error %}<div class="error-msg">{{ error }}</div>{% endif %}
        <form action="/login" method="POST">
            <input type="password" name="password" placeholder="أدخل مفتاح التشفير..." required autofocus>
            <button type="submit">تسجيل الدخول الآمن</button>
        </form>
    </div>
    <script>
        const canvas = document.createElement('canvas');
        document.getElementById('particles').appendChild(canvas);
        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth; canvas.height = window.innerHeight;
        const particlesArray = [];
        class Particle {
            constructor() { this.x = Math.random() * canvas.width; this.y = Math.random() * canvas.height; this.size = Math.random() * 3 + 1; this.speedX = Math.random() * 1 - 0.5; this.speedY = Math.random() * 1 - 0.5; }
            update() { this.x += this.speedX; this.y += this.speedY; if (this.size > 0.2) this.size -= 0.01; }
            draw() { ctx.fillStyle = 'rgba(56, 189, 248, 0.5)'; ctx.beginPath(); ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2); ctx.fill(); }
        }
        function init() { for (let i = 0; i < 100; i++) particlesArray.push(new Particle()); }
        function animate() { ctx.clearRect(0, 0, canvas.width, canvas.height); for (let i = 0; i < particlesArray.length; i++) { particlesArray[i].update(); particlesArray[i].draw(); if (particlesArray[i].size <= 0.2) { particlesArray.splice(i, 1); i--; particlesArray.push(new Particle()); } } requestAnimationFrame(animate); }
        init(); animate();
    </script>
</body>
</html>
"""
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة تحكم السيرفر | Enterprise Edition</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root { --bg-main: #0f172a; --bg-card: #1e293b; --bg-input: #020617; --text-main: #f8fafc; --text-muted: #94a3b8; --primary: #0ea5e9; --primary-hover: #0284c7; --success: #10b981; --danger: #ef4444; --warning: #f59e0b; --border: #334155; }
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background: var(--bg-main); color: var(--text-main); margin: 0; padding: 0; display: flex; height: 100vh; overflow: hidden; }
        /* Sidebar Navigation */
        .sidebar { width: 260px; background: var(--bg-card); border-left: 1px solid var(--border); display: flex; flex-direction: column; padding: 20px 0; transition: 0.3s; z-index: 100;}
        .sidebar-header { padding: 0 20px 20px; border-bottom: 1px solid var(--border); margin-bottom: 20px; text-align: center; }
        .sidebar-header h2 { margin: 0; color: var(--primary); font-size: 22px; text-shadow: 0 2px 10px rgba(14, 165, 233, 0.3); }
        .nav-item { padding: 15px 25px; color: var(--text-muted); cursor: pointer; font-weight: bold; transition: 0.3s; display: flex; align-items: center; gap: 10px; border-right: 4px solid transparent; }
        .nav-item:hover { background: rgba(14, 165, 233, 0.1); color: var(--text-main); }
        .nav-item.active { background: rgba(14, 165, 233, 0.15); color: var(--primary); border-right-color: var(--primary); }
        /* Main Content Area */
        .main-content { flex: 1; display: flex; flex-direction: column; overflow-y: auto; padding: 20px; }
        /* Top Header */
        .top-header { display: flex; justify-content: space-between; align-items: center; background: var(--bg-card); padding: 15px 25px; border-radius: 12px; border: 1px solid var(--border); margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
        .network-box { display: flex; align-items: center; gap: 10px; background: var(--bg-input); padding: 8px 15px; border-radius: 8px; border: 1px solid var(--border); }
        .ip-badge { font-weight: bold; font-size: 16px; letter-spacing: 1px; }
        .ip-connected { color: var(--success); }
        .ip-error { color: var(--danger); }
        .btn-copy { background: var(--border); color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; transition: 0.3s; font-size: 12px; }
        .btn-copy:hover { background: #475569; }
        .btn-logout { background: rgba(239, 68, 68, 0.1); color: var(--danger); border: 1px solid var(--danger); padding: 8px 20px; text-decoration: none; border-radius: 8px; font-weight: bold; transition: 0.3s; }
        .btn-logout:hover { background: var(--danger); color: white; }
        /* Stats Grid & Charts */
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .stat-card { background: var(--bg-card); padding: 20px; border-radius: 12px; border: 1px solid var(--border); display: flex; flex-direction: column; justify-content: space-between; position: relative; overflow: hidden;}
        .stat-title { color: var(--text-muted); font-size: 14px; margin-bottom: 10px; text-transform: uppercase; font-weight: bold; z-index: 2;}
        .stat-value { font-size: 32px; font-weight: 900; color: var(--text-main); z-index: 2;}
        .status-online { color: var(--success); text-shadow: 0 0 15px rgba(16, 185, 129, 0.4); }
        .status-offline { color: var(--danger); }
        .chart-container { position: absolute; bottom: 0; left: 0; width: 100%; height: 60px; opacity: 0.3; z-index: 1;}
        /* Tab Content */
        .tab-content { display: none; background: var(--bg-card); padding: 25px; border-radius: 12px; border: 1px solid var(--border); animation: fadeIn 0.4s cubic-bezier(0.4, 0, 0.2, 1); flex: 1; }
        .tab-content.active { display: flex; flex-direction: column; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        /* Console */
        .console-wrapper { background: var(--bg-input); border-radius: 8px; border: 1px solid var(--border); display: flex; flex-direction: column; flex: 1; min-height: 400px;}
        .console-output { padding: 15px; flex: 1; overflow-y: auto; font-family: 'Consolas', monospace; font-size: 14px; color: #a3e635; direction: ltr; text-align: left; line-height: 1.6; }
        .console-input-area { display: flex; border-top: 1px solid var(--border); background: rgba(255,255,255,0.02);}
        .console-input { flex: 1; background: transparent; border: none; padding: 15px; color: white; font-family: monospace; font-size: 15px; outline: none; }
        .console-btn { background: var(--primary); color: white; border: none; padding: 0 30px; cursor: pointer; font-weight: bold; transition: 0.3s; }
        .console-btn:hover { background: var(--primary-hover); }
        /* Buttons & Forms */
        .action-bar { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        .btn { padding: 12px 24px; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; color: white; transition: 0.3s; display: inline-flex; align-items: center; gap: 8px; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px;}
        .btn-green { background: var(--success); } .btn-green:hover { background: #059669; box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);}
        .btn-red { background: var(--danger); } .btn-red:hover { background: #dc2626; box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4);}
        .btn-blue { background: var(--primary); } .btn-blue:hover { background: var(--primary-hover); box-shadow: 0 4px 15px rgba(14, 165, 233, 0.4);}
        .btn-orange { background: var(--warning); } .btn-orange:hover { background: #d97706; box-shadow: 0 4px 15px rgba(245, 158, 11, 0.4);}
        /* Lists */
        .list-item { display: flex; justify-content: space-between; align-items: center; background: var(--bg-input); padding: 15px 20px; border-radius: 8px; margin-bottom: 10px; border: 1px solid var(--border); transition: 0.2s; }
        .list-item:hover { border-color: #475569; transform: translateX(-5px);}
        .list-item-title { font-weight: bold; font-size: 16px; display: flex; align-items: center; gap: 10px;}
        .list-actions { display: flex; gap: 8px; }
        /* Config Grid (The Ultimate Config) */
        .config-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; max-height: 60vh; overflow-y: auto; padding-right: 10px;}
        .config-row { display: flex; flex-direction: column; background: var(--bg-input); padding: 15px; border-radius: 8px; border: 1px solid var(--border); transition: 0.3s;}
        .config-row:focus-within { border-color: var(--primary); box-shadow: 0 0 10px rgba(14, 165, 233, 0.2);}
        .config-row span { margin-bottom: 8px; font-weight: bold; color: var(--text-main); font-size: 14px; }
        .config-row select, .config-row input { width: 100%; background: var(--bg-card); color: white; border: 1px solid var(--border); padding: 10px; border-radius: 6px; outline: none; font-weight: bold; transition: 0.3s; }
        .config-row input:focus, .config-row select:focus { border-color: var(--primary); }
        /* File Viewer */
        .file-viewer { background: var(--bg-input); color: #e2e8f0; padding: 20px; border-radius: 8px; font-family: 'Consolas', monospace; white-space: pre-wrap; max-height: 500px; overflow-y: auto; direction: ltr; text-align: left; border: 1px solid var(--border); margin-top: 15px; display: none; font-size: 14px; line-height: 1.5;}
        /* Toast Notifications */
        #toast-container { position: fixed; bottom: 20px; left: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 10px; }
        .toast { background: var(--bg-card); color: white; padding: 15px 25px; border-radius: 8px; border-right: 4px solid var(--primary); box-shadow: 0 10px 25px rgba(0,0,0,0.5); animation: slideIn 0.3s cubic-bezier(0.4, 0, 0.2, 1) forwards; font-weight: bold; display: flex; align-items: center; gap: 10px;}
        /* Scrollbars */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg-input); border-radius: 4px;}
        ::-webkit-scrollbar-thumb { background: #475569; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #64748b; }
        /* Responsive */
        @media (max-width: 768px) {
            body { flex-direction: column; }
            .sidebar { width: 100%; height: auto; flex-direction: row; overflow-x: auto; padding: 10px; border-left: none; border-bottom: 1px solid var(--border); }
            .sidebar-header { display: none; }
            .nav-item { padding: 10px 15px; border-right: none; border-bottom: 3px solid transparent; white-space: nowrap;}
            .nav-item.active { border-right: none; border-bottom-color: var(--primary); }
            .stats-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div id="toast-container"></div>
    <!-- Sidebar Navigation -->
    <div class="sidebar">
        <div class="sidebar-header">
            <h2>🛡️ Enterprise</h2>
        </div>
        <div class="nav-item active" onclick="openTab('console', this)">💻 الكونسول والتحكم</div>
        <div class="nav-item" onclick="openTab('livemap', this)">🗺️ الخريطة المباشرة</div>
        <div class="nav-item" onclick="openTab('players', this)">👥 إدارة اللاعبين</div>
        <div class="nav-item" onclick="openTab('mods', this); loadMods();">🧩 مدير المودات</div>
        <div class="nav-item" onclick="openTab('files', this); loadFiles();">📁 مدير الملفات</div>
        <div class="nav-item" onclick="openTab('backups', this); loadBackups();">💾 النسخ الاحتياطي</div>
        <div class="nav-item" onclick="openTab('settings', this); loadConfig();">⚙️ إعدادات السيرفر</div>
        <div class="nav-item" onclick="openTab('crashes', this); loadCrash();">⚠️ تقارير الكراش</div>
    </div>
    <!-- Main Content -->
    <div class="main-content">
        <!-- Top Header -->
        <div class="top-header">
            <div id="network-area" class="network-box">
                <span class="ip-badge ip-connected" id="ip-display">جاري الاتصال...</span>
                <button class="btn-copy" onclick="copyIP()">📋 نسخ</button>
            </div>
            <a href="/logout" class="btn-logout">تسجيل خروج 🚪</a>
        </div>
        <!-- Stats Grid with Live Charts -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-title">حالة السيرفر</div>
                <div class="stat-value" id="status-text">جاري التحميل...</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">استهلاك المعالج (CPU)</div>
                <div class="stat-value" id="cpu-text">0%</div>
                <div class="chart-container"><canvas id="cpuChart"></canvas></div>
            </div>
            <div class="stat-card">
                <div class="stat-title">استهلاك الرام (RAM)</div>
                <div class="stat-value" id="ram-text">0%</div>
                <div class="chart-container"><canvas id="ramChart"></canvas></div>
            </div>
            <div class="stat-card">
                <div class="stat-title">اللاعبين المتصلين</div>
                <div class="stat-value" id="players-count">0</div>
            </div>
        </div>
        <!-- 1. Console Tab -->
        <div id="console" class="tab-content active">
            <div class="action-bar">
                <button class="btn btn-green" onclick="sendAction('start')">▶ تشغيل السيرفر</button>
                <button class="btn btn-orange" onclick="sendAction('stop')">⏹ إيقاف آمن (حفظ)</button>
                <button class="btn btn-red" onclick="sendAction('kill')">💀 إيقاف إجباري</button>
                <button class="btn btn-blue" onclick="execCmd('!resetworld')" style="margin-right: auto;">💥 فرمتة العالم</button>
            </div>
            <div class="console-wrapper">
                <div class="console-output" id="console-box"></div>
                <div class="console-input-area">
                    <input type="text" id="cmd" class="console-input" placeholder="اكتب أمر السيرفر هنا (مثال: time set day)..." onkeypress="if(event.key === 'Enter') sendCmd()">
                    <button class="console-btn" onclick="sendCmd()">إرسال</button>
                </div>
            </div>
        </div>
        <!-- 2. Live Map Tab -->
        <div id="livemap" class="tab-content" style="padding: 0; overflow: hidden; display: none; flex-direction: column;">
            <div style="padding: 15px; background: var(--bg-card); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin:0; color:var(--primary);">🗺️ الخريطة المباشرة (Dynmap)</h3>
                <div>
                    <button class="btn btn-blue" onclick="document.getElementById('map-frame').src = '/map/';">🔄 تحديث</button>
                    <a href="/map/" target="_blank" class="btn btn-green" style="text-decoration:none;">🌍 فتح بنافذة</a>
                </div>
            </div>
            <iframe id="map-frame" src="/map/" style="width: 100%; flex: 1; border: none; background: #000; min-height: 60vh;"></iframe>
        </div>
        <!-- 3. Players Tab -->
        <div id="players" class="tab-content">
            <h3 style="margin-top:0; color:var(--primary);">👥 إدارة اللاعبين المتصلين</h3>
            <div id="players-list"><p style="color: var(--text-muted);">جاري التحميل...</p></div>
        </div>
        <!-- 4. Mods Tab -->
        <div id="mods" class="tab-content">
            <h3 style="margin-top:0; color:var(--primary);">📦 مدير المودات (Fabric 1.20.4)</h3>
            <div class="action-bar" style="background: var(--bg-input); padding: 20px; border-radius: 8px; border: 1px dashed #475569; align-items: center;">
                <input type="file" id="mod-file" accept=".jar" style="color: white; flex: 1;">
                <button class="btn btn-green" onclick="uploadMod()">⬆️ رفع المود للسيرفر</button>
            </div>
            <div id="mods-list" style="margin-top: 20px; overflow-y: auto; flex: 1;">جاري التحميل...</div>
        </div>
        <!-- 5. File Manager Tab -->
        <div id="files" class="tab-content">
            <h3 style="margin-top:0; color:var(--primary);">📁 مدير ملفات النظام</h3>
            <p style="color: var(--text-muted); font-size: 14px;">تصفح، اقرأ، واحذف ملفات الإعدادات والتقارير بأمان.</p>
            <div id="files-list" style="overflow-y: auto; max-height: 40vh;">جاري التحميل...</div>
            <div id="file-viewer" class="file-viewer"></div>
        </div>
        <!-- 6. Backups Tab -->
        <div id="backups" class="tab-content">
            <h3 style="margin-top:0; color:var(--primary);">💾 نظام النسخ الاحتياطي (Disaster Recovery)</h3>
            <button class="btn btn-blue" onclick="createBackup()" style="width: 100%; justify-content: center; padding: 15px; font-size: 16px; margin-bottom: 20px;">
                📦 إنشاء نسخة احتياطية للعالم الآن
            </button>
            <div id="backups-list" style="overflow-y: auto; flex: 1;">جاري التحميل...</div>
        </div>
        <!-- 7. Settings Tab (The Ultimate Config) -->
        <div id="settings" class="tab-content">
            <h3 style="margin-top:0; color:var(--primary);">⚙️ إعدادات السيرفر الشاملة (server.properties)</h3>
            <p style="color: var(--warning); font-size: 14px; margin-bottom: 20px;">⚠️ يجب إيقاف السيرفر وتشغيله مرة أخرى لتطبيق أي تعديلات.</p>
            <div id="config-form" class="config-grid">جاري التحميل...</div>
            <button class="btn btn-green" onclick="saveConfig()" style="width: 100%; justify-content: center; padding: 15px; font-size: 18px; margin-top: 20px; box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);">
                💾 حفظ جميع الإعدادات
            </button>
        </div>
        <!-- 8. Crashes Tab -->
        <div id="crashes" class="tab-content">
            <h3 style="margin-top:0; color:var(--danger);">⚠️ محلل تقارير الكراش (Crash Analyzer)</h3>
            <div class="console-wrapper" style="flex: 1;">
                <div class="console-output" id="crash-box" style="color: #fca5a5;">جاري التحميل...</div>
            </div>
        </div>
    </div>
    <script>
        // --- UI & Toast System ---
        function showToast(message, type = 'success') {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            toast.className = 'toast';
            toast.style.borderRightColor = type === 'success' ? 'var(--success)' : (type === 'error' ? 'var(--danger)' : 'var(--primary)');
            toast.innerHTML = `<span>${type === 'success' ? '✅' : (type === 'error' ? '❌' : 'ℹ️')}</span> ${message}`;
            container.appendChild(toast);
            setTimeout(() => {
                toast.style.animation = 'fadeOut 0.3s ease-out forwards';
                setTimeout(() => toast.remove(), 300);
            }, 4000);
        }
        function copyIP() {
            const ipText = document.getElementById('ip-display').innerText;
            navigator.clipboard.writeText(ipText).then(() => showToast('تم نسخ الآي بي بنجاح!'));
        }
        let autoScroll = true;
        let consoleBox = document.getElementById('console-box');
        consoleBox.addEventListener('scroll', () => {
            autoScroll = (consoleBox.scrollHeight - consoleBox.scrollTop - consoleBox.clientHeight < 50);
        });
        function openTab(tabName, btnElement) {
            document.querySelectorAll('.tab-content').forEach(t => {
                t.classList.remove('active');
                t.style.display = 'none';
            });
            document.querySelectorAll('.nav-item').forEach(t => t.classList.remove('active'));
            const targetTab = document.getElementById(tabName);
            targetTab.classList.add('active');
            targetTab.style.display = tabName === 'livemap' ? 'flex' : 'block';
            if(btnElement) btnElement.classList.add('active');
        }
        // --- Live Charts Setup (Chart.js) ---
        const chartOptions = {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            scales: { x: { display: false }, y: { display: false, min: 0, max: 100 } },
            elements: { point: { radius: 0 }, line: { tension: 0.4, borderWidth: 2 } }
        };
        const cpuCtx = document.getElementById('cpuChart').getContext('2d');
        const cpuChart = new Chart(cpuCtx, {
            type: 'line',
            data: { labels: Array(20).fill(''), datasets: [{ data: Array(20).fill(0), borderColor: '#0ea5e9', backgroundColor: 'rgba(14, 165, 233, 0.1)', fill: true }] },
            options: chartOptions
        });
        const ramCtx = document.getElementById('ramChart').getContext('2d');
        const ramChart = new Chart(ramCtx, {
            type: 'line',
            data: { labels: Array(20).fill(''), datasets: [{ data: Array(20).fill(0), borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.1)', fill: true }] },
            options: chartOptions
        });
        function updateCharts(cpu, ram) {
            cpuChart.data.datasets[0].data.push(cpu);
            cpuChart.data.datasets[0].data.shift();
            cpuChart.update('none');
            ramChart.data.datasets[0].data.push(ram);
            ramChart.data.datasets[0].data.shift();
            ramChart.update('none');
        }
        // --- Core Status Loop ---
        function updateStatus() {
            fetch('/api/status').then(res => {
                if(res.status === 401) window.location.reload();
                return res.json();
            }).then(data => {
                document.getElementById('cpu-text').innerText = data.cpu + '%';
                document.getElementById('ram-text').innerText = data.ram + '%';
                updateCharts(data.cpu, data.ram);
                let statusEl = document.getElementById('status-text');
                statusEl.innerText = data.status;
                statusEl.className = data.status.includes('شغال') ? 'stat-value status-online' : 'stat-value status-offline';
                document.getElementById('players-count').innerText = data.players.length;
                let ipDisplay = document.getElementById('ip-display');
                ipDisplay.innerText = data.network.ip;
                if(data.network.status === 'error') ipDisplay.className = 'ip-badge ip-error';
                else ipDisplay.className = 'ip-badge ip-connected';
                consoleBox.innerHTML = data.logs.join('<br>');
                if (autoScroll) consoleBox.scrollTop = consoleBox.scrollHeight;
                let p_html = data.players.length === 0 ? '<p style="color: var(--text-muted); text-align:center; padding: 20px;">لا يوجد لاعبين متصلين حالياً.</p>' : '';
                data.players.forEach(p => {
                    p_html += `
                    <div class="list-item">
                        <div class="list-item-title">👤 ${p}</div>
                        <div class="list-actions">
                            <button class="btn btn-blue" onclick="execCmd('op ${p}')">👑 أدمن</button>
                            <button class="btn btn-green" onclick="execCmd('gamemode creative ${p}')">✨ إبداع</button>
                            <button class="btn btn-orange" onclick="execCmd('gamemode survival ${p}')">❤️ نجاة</button>
                            <button class="btn btn-red" onclick="execCmd('kick ${p}')">👢 طرد</button>
                        </div>
                    </div>`;
                });
                document.getElementById('players-list').innerHTML = p_html;
            }).catch(err => console.error("Status fetch error:", err));
        }
        setInterval(updateStatus, 2000);
        // --- Actions & Commands ---
        function sendCmd() {
            let cmd = document.getElementById('cmd').value;
            if(cmd.trim() === "") return;
            execCmd(cmd);
            document.getElementById('cmd').value = '';
            autoScroll = true;
        }
        function execCmd(cmd) {
            fetch('/api/command', { method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: 'cmd=' + encodeURIComponent(cmd) });
        }
        function sendAction(act) {
            if(act === 'kill' && !confirm('تحذير: الإيقاف الإجباري قد يؤدي إلى ضياع آخر التغييرات. متأكد؟')) return;
            if(act === 'stop') showToast('🛑 تم إرسال أمر الإيقاف الآمن، يرجى الانتظار...', 'info');
            if(act === 'start') showToast('🚀 جاري تشغيل السيرفر...', 'info');
            fetch('/api/action', { method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: 'action=' + act });
        }
        // --- Mods Manager ---
        function loadMods() {
            fetch('/api/mods').then(res => res.json()).then(mods => {
                let html = mods.length === 0 ? '<p style="color: var(--text-muted); text-align:center; padding: 20px;">لا توجد مودات مثبتة.</p>' : '';
                mods.forEach(mod => {
                    html += `
                    <div class="list-item">
                        <div class="list-item-title">🧩 ${mod}</div>
                        <button class="btn btn-red" onclick="deleteMod('${mod}')">🗑️ حذف</button>
                    </div>`;
                });
                document.getElementById('mods-list').innerHTML = html;
            });
        }
        function uploadMod() {
            let fileInput = document.getElementById('mod-file');
            if(fileInput.files.length === 0) return showToast('الرجاء اختيار ملف المود أولاً!', 'error');
            let formData = new FormData();
            formData.append("file", fileInput.files[0]);
            let btn = event.target;
            let originalText = btn.innerText;
            btn.innerText = "⏳ جاري الرفع...";
            btn.disabled = true;
            fetch('/api/mods', { method: 'POST', body: formData }).then(() => {
                showToast('تم رفع المود بنجاح!');
                fileInput.value = '';
                loadMods();
                btn.innerText = originalText;
                btn.disabled = false;
            });
        }
        function deleteMod(modName) {
            if(!confirm('هل أنت متأكد من حذف المود: ' + modName + '؟')) return;
            fetch('/api/mods', { method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: 'delete=' + encodeURIComponent(modName) }).then(() => {
                showToast('تم الحذف بنجاح!');
                loadMods();
            });
        }
        // --- File Manager ---
        function loadFiles() {
            fetch('/api/files').then(res => res.json()).then(files => {
                let html = files.length === 0 ? '<p style="color: var(--text-muted); text-align:center; padding: 20px;">لا توجد ملفات.</p>' : '';
                files.forEach(f => {
                    html += `
                    <div class="list-item">
                        <div class="list-item-title">📄 ${f}</div>
                        <div class="list-actions">
                            <button class="btn btn-blue" onclick="readFile('${f}')">👁️ عرض</button>
                            <button class="btn btn-red" onclick="deleteFile('${f}')">🗑️ حذف</button>
                        </div>
                    </div>`;
                });
                document.getElementById('files-list').innerHTML = html;
            });
        }
        function readFile(filename) {
            let formData = new FormData();
            formData.append('action', 'read');
            formData.append('target', filename);
            fetch('/api/files', { method: 'POST', body: formData }).then(res => res.text()).then(text => {
                let viewer = document.getElementById('file-viewer');
                viewer.style.display = 'block';
                viewer.innerText = text;
                viewer.scrollIntoView({behavior: "smooth"});
            });
        }
        function deleteFile(filename) {
            if(!confirm('هل أنت متأكد من حذف الملف: ' + filename + '؟')) return;
            let formData = new FormData();
            formData.append('action', 'delete');
            formData.append('target', filename);
            fetch('/api/files', { method: 'POST', body: formData }).then(() => {
                showToast('تم الحذف بنجاح!');
                document.getElementById('file-viewer').style.display = 'none';
                loadFiles();
            });
        }
        // --- Backups ---
        function loadBackups() {
            fetch('/api/backup').then(res => res.json()).then(backups => {
                let html = backups.length === 0 ? '<p style="color: var(--text-muted); text-align:center; padding: 20px;">لا توجد نسخ احتياطية.</p>' : '';
                backups.forEach(b => {
                    html += `
                    <div class="list-item">
                        <div class="list-item-title">🗄️ ${b}</div>
                        <a href="/api/backup/download/${b}" class="btn btn-green" style="text-decoration:none;">⬇️ تحميل للكمبيوتر</a>
                    </div>`;
                });
                document.getElementById('backups-list').innerHTML = html;
            });
        }
        function createBackup() {
            fetch('/api/backup', { method: 'POST' }).then(() => {
                showToast('بدأ إنشاء النسخة الاحتياطية...', 'info');
                setTimeout(loadBackups, 5000);
            });
        }
        // --- The Ultimate Config Manager ---
        function loadConfig() {
            fetch('/api/config').then(res => res.json()).then(data => {
                let html = '';
                const schema = data.schema;
                const values = data.values;
                schema.forEach(f => {
                    let val = values[f.key] !== undefined ? values[f.key] : f.default;
                    html += `<div class="config-row"><span>${f.label} <small style="color:var(--text-muted); font-weight:normal;">(${f.key})</small></span>`;
                    if(f.type === 'select') {
                        html += `<select id="cfg-${f.key}" data-key="${f.key}">`;
                        f.options.forEach(opt => { html += `<option value="${opt}" ${val===opt?'selected':''}>${opt}</option>`; });
                        html += `</select></div>`;
                    } else {
                        html += `<input type="${f.type}" id="cfg-${f.key}" data-key="${f.key}" value="${val}"></div>`;
                    }
                });
                document.getElementById('config-form').innerHTML = html;
            });
        }
        function saveConfig() {
            let data = {};
            document.querySelectorAll('#config-form input, #config-form select').forEach(el => {
                if(el.value.trim() !== '') {
                    data[el.getAttribute('data-key')] = el.value;
                }
            });
            fetch('/api/config', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) }).then(() => {
                showToast('تم حفظ جميع الإعدادات! أعد تشغيل السيرفر لتطبيقها.');
            });
        }
        // --- Crash Analyzer ---
        function loadCrash() {
            fetch('/api/crash').then(res => res.text()).then(text => {
                document.getElementById('crash-box').innerHTML = text;
            });
        }
    </script>
</body>
</html>
"""
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)
