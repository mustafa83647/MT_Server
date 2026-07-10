import os
import subprocess
import threading
import html
import shutil
from core.config import DATA_DIR, ANSI_ESCAPE
class PlayitDaemon:
    def __init__(self, logger):
        self.process = None
        self.logger = logger
        self.status = "loading"
        self.ip = "جاري الاتصال..."
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
        env = os.environ.copy()
        env["HOME"] = DATA_DIR
        # 🔥 المكنسة البرمجية: مسح ملفات الأشباح القديمة لمنع التضارب 🔥
        old_config_path = os.path.join(DATA_DIR, ".config", "playit")
        if os.path.exists(old_config_path):
            try:
                shutil.rmtree(old_config_path)
                self.logger.log("Playit", "🧹 تم تنظيف إعدادات الشبكة القديمة بنجاح.", is_safe=True)
            except:
                pass
        self.logger.log("Playit", "🔄 جاري بدء الاتصال بخوادم Playit العالمية...", is_safe=True)
        try:
            self.process = subprocess.Popen(["playit", "--secret", secret.strip()], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, bufsize=1, env=env)
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
