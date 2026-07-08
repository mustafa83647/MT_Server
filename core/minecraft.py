import os
import time
import threading
import subprocess
import shutil
import html
from datetime import datetime
from core.config import DATA_DIR, APP_DIR, ANSI_ESCAPE, PLAYER_JOIN_REGEX, PLAYER_LEAVE_REGEX, WATCHDOG_CHECK_INTERVAL, AUTO_BACKUP_INTERVAL_HOURS
class MinecraftDaemon:
    def __init__(self, logger, backup_mgr, storage_mgr):
        self.process = None
        self.logger = logger
        self.backup_mgr = backup_mgr
        self.storage_mgr = storage_mgr
        self.online_players = set()
        self.thread = None
        self.intentional_stop = False
        self.is_starting = False # 🔥 القفل الذكي لمنع التداخل
        self.lock = threading.Lock()
    def force_symlink(self, src: str, dst: str):
        try:
            if os.path.islink(dst) or os.path.isfile(dst): os.remove(dst)
            elif os.path.isdir(dst): shutil.rmtree(dst)
            os.symlink(src, dst)
        except Exception as e:
            self.logger.log("النظام", f"⚠️ تحذير أثناء ربط {os.path.basename(dst)}: {html.escape(str(e))}", is_safe=True)
    def setup_environment(self):
        self.logger.log("النظام", "🛠️ جاري تهيئة بيئة السيرفر (Enterprise Secure Mode)...", is_safe=True)
        for d in ['world', 'mods', 'config', 'backups', 'logs', 'crash-reports']:
            os.makedirs(os.path.join(DATA_DIR, d), exist_ok=True)
        os.makedirs(APP_DIR, exist_ok=True)

        self.force_symlink(os.path.join(DATA_DIR, "world"), os.path.join(APP_DIR, "world"))
        self.force_symlink(os.path.join(DATA_DIR, "logs"), os.path.join(APP_DIR, "logs"))
        self.force_symlink(os.path.join(DATA_DIR, "crash-reports"), os.path.join(APP_DIR, "crash-reports"))
        files_to_link = ['server.properties', 'ops.json', 'banned-players.json', 'banned-ips.json', 'whitelist.json', 'usercache.json']
        for f in files_to_link:
            file_path = os.path.join(DATA_DIR, f)
            if not os.path.exists(file_path):
                with open(file_path, 'w') as file:
                    if f == 'server.properties': file.write("online-mode=false\n")
                    elif f.endswith('.json'): file.write("[]\n")
            self.force_symlink(file_path, os.path.join(APP_DIR, f))
        with open(os.path.join(APP_DIR, "eula.txt"), 'w') as f: f.write("eula=true\n")

        fabric_jar = os.path.join(APP_DIR, "fabric-server-launch.jar")
        if not os.path.exists(fabric_jar):
            self.logger.log("النظام", "⬇️ جاري تحميل وتثبيت محرك Fabric (1.20.4)...", is_safe=True)
            installer_path = os.path.join(APP_DIR, "fabric-installer.jar")
            subprocess.run(["wget", "-q", "-O", installer_path, "https://maven.fabricmc.net/net/fabricmc/fabric-installer/1.0.1/fabric-installer-1.0.1.jar"])
            subprocess.run(["java", "-jar", "fabric-installer.jar", "server", "-mcversion", "1.20.4", "-loader", "0.15.7", "-downloadMinecraft"], cwd=APP_DIR)
            if os.path.exists(installer_path): os.remove(installer_path)
        self.storage_mgr.hydrate_to_ram()
        self.storage_mgr.wake_up_world()
        self.logger.log("النظام", "✅ تمت التهيئة بنجاح. البيئة جاهزة.", is_safe=True)
    def start_async(self):
        with self.lock:
            if self.is_running() or self.is_starting: return
            self.is_starting = True
            self.intentional_stop = False
        os.system("pkill -9 java") # قتل أي عمليات جافا معلقة
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    def _run(self):
        try:
            self.setup_environment()
            self.online_players.clear()
            real_mods_dir = os.path.join(APP_DIR, "mods")
            data_mods_dir = os.path.join(DATA_DIR, "mods")
            os.makedirs(real_mods_dir, exist_ok=True)
            for f in os.listdir(real_mods_dir):
                file_path = os.path.join(real_mods_dir, f)
                if os.path.isfile(file_path) or os.path.islink(file_path): os.remove(file_path)
            if os.path.exists(data_mods_dir):
                for f in os.listdir(data_mods_dir):
                    if f.endswith('.jar'):
                        src = os.path.join(data_mods_dir, f)
                        dst = os.path.join(real_mods_dir, f)
                        self.logger.log("النظام", f"📦 جاري استخراج المود للذاكرة السريعة: {f}", is_safe=True)
                        shutil.copy2(src, dst)

            config_dir = os.path.join(APP_DIR, "config")
            java_args = [
                "java", "-Xms2G", "-Xmx8G",
                f"-Dfabric.modsDir={real_mods_dir}",
                f"-Dfabric.configDir={config_dir}",
                "-XX:+UseG1GC", "-XX:+ParallelRefProcEnabled", "-XX:MaxGCPauseMillis=200",
                "-XX:+UnlockExperimentalVMOptions", "-XX:+DisableExplicitGC", "-XX:+AlwaysPreTouch",
                "-XX:G1NewSizePercent=30", "-XX:G1MaxNewSizePercent=40", "-XX:G1HeapRegionSize=8M",
                "-XX:G1ReservePercent=20", "-XX:G1HeapWastePercent=5", "-XX:G1MixedGCCountTarget=4",
                "-XX:InitiatingHeapOccupancyPercent=15", "-XX:G1MixedGCLiveThresholdPercent=90",
                "-XX:G1RSetUpdatingPauseTimePercent=5", "-XX:SurvivorRatio=32", "-XX:+PerfDisableSharedMem",
                "-XX:MaxTenuringThreshold=1", "-jar", "fabric-server-launch.jar", "nogui"
            ]
            self.logger.log("Minecraft", "🚀 جاري إطلاق السيرفر وقراءة الملفات الفيزيائية...", is_safe=True)
            self.process = subprocess.Popen(
                java_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, text=True, bufsize=1, cwd=APP_DIR
            )
            self.is_starting = False # تم التشغيل بنجاح، نرفع القفل
            for line in self.process.stdout:
                clean_line = ANSI_ESCAPE.sub('', line.strip())
                if not clean_line: continue
                safe_line = html.escape(clean_line)
                self.logger.log("Minecraft", safe_line, is_safe=True)

                join_match = PLAYER_JOIN_REGEX.search(clean_line)
                if join_match: self.online_players.add(html.escape(join_match.group(1)))

                leave_match = PLAYER_LEAVE_REGEX.search(clean_line)
                if leave_match and html.escape(leave_match.group(1)) in self.online_players:
                    self.online_players.remove(html.escape(leave_match.group(1)))
            self.process.wait()
            if not self.intentional_stop:
                self.logger.log("Minecraft", "⚠️ السيرفر توقف بشكل غير متوقع (Crash)!", is_safe=True)
            else:
                self.logger.log("Minecraft", "🛑 توقف السيرفر بأمان.", is_safe=True)
        except Exception as e:
            self.logger.log("Minecraft", f"❌ فشل في تشغيل الجافا: {html.escape(str(e))}", is_safe=True)
        finally:
            self.is_starting = False
            self.online_players.clear()
            self.process = None
            self.storage_mgr.dehydrate_to_disk()
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
            os.system("pkill -9 java")
            self.logger.log("النظام", "💀 تم قتل العملية إجبارياً!", is_safe=True)
    def is_running(self) -> bool:
        return self.is_starting or (self.process is not None and self.process.poll() is None)
class WatchdogDaemon:
    def __init__(self, mc_server: MinecraftDaemon, backup_mgr, storage_mgr, logger):
        self.mc_server = mc_server
        self.backup_mgr = backup_mgr
        self.storage_mgr = storage_mgr
        self.logger = logger
        self.last_backup_time = datetime.now()
    def start(self):
        threading.Thread(target=self._run, daemon=True).start()
    def _run(self):
        sync_counter = 0
        while True:
            time.sleep(WATCHDOG_CHECK_INTERVAL)
            sync_counter += 1
            if sync_counter >= 6:
                self.storage_mgr.dehydrate_to_disk()
                sync_counter = 0
            if not self.mc_server.is_running() and not self.mc_server.intentional_stop:
                time.sleep(5)
                if not self.mc_server.is_running() and not self.mc_server.intentional_stop:
                    self.logger.log("Watchdog", "🚨 اكتشف النظام توقف السيرفر! جاري إعادة التشغيل التلقائي...", is_safe=True)
                    self.mc_server.start_async()
            current_time = datetime.now()
            if (current_time - self.last_backup_time).total_seconds() >= (AUTO_BACKUP_INTERVAL_HOURS * 3600):
                self.logger.log("Watchdog", "⏰ حان وقت النسخ الاحتياطي التلقائي المجدول.", is_safe=True)
                self.backup_mgr.create_backup_async()
                self.last_backup_time = current_time
