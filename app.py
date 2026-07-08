"""
=========================================================================================
👑 ULTIMATE MINECRAFT SERVER PANEL - MODULAR ENTERPRISE EDITION 👑
=========================================================================================
Author: Senior AI Architect
Version: 14.0.0 (Modular Architecture + God-Tier UI)
Description: Clean app.py acting as the API and Frontend router.
=========================================================================================
"""
import os
import shutil
import threading
import psutil
import html
import requests
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, session, jsonify, send_from_directory, abort, Response
from werkzeug.utils import secure_filename
# =========================================================================================
# 1. استيراد الأنظمة الأساسية من مجلد (core)
# =========================================================================================
from core.config import DATA_DIR, APP_DIR, PASSWORD, FLASK_SECRET, SERVER_PROPERTIES_SCHEMA
from core.logger import LoggerManager
from core.security import SecurityManager
from core.storage import EnterpriseStorageManager
from core.network import PlayitDaemon
from core.minecraft import MinecraftDaemon, WatchdogDaemon
# =========================================================================================
# 2. أدوات إضافية (النسخ الاحتياطي وقراءة الرام)
# =========================================================================================
def get_container_ram_percent():
    try:
        with open('/sys/fs/cgroup/memory.current', 'r') as f: used = int(f.read().strip())
        with open('/sys/fs/cgroup/memory.max', 'r') as f:
            max_val = f.read().strip()
            if max_val == 'max': return psutil.virtual_memory().percent
            total = int(max_val)
        return round((used / total) * 100, 1)
    except:
        try:
            with open('/sys/fs/cgroup/memory/memory.usage_in_bytes', 'r') as f: used = int(f.read().strip())
            with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'r') as f: total = int(f.read().strip())
            return round((used / total) * 100, 1)
        except:
            return psutil.virtual_memory().percent
class BackupManager:
    def __init__(self, logger):
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
            shutil.make_archive(backup_path, 'zip', self.world_dir)
            self.logger.log("Backup", f"✅ اكتملت النسخة الاحتياطية بنجاح: world_backup_{timestamp}.zip", is_safe=True)
        except Exception as e:
            self.logger.log("Backup", f"❌ فشل النسخ الاحتياطي: {html.escape(str(e))}", is_safe=True)
        finally:
            self.is_backing_up = False
    def get_backups_list(self) -> list:
        if not os.path.exists(self.backup_dir): return []
        return sorted([f for f in os.listdir(self.backup_dir) if f.endswith('.zip')], reverse=True)
# =========================================================================================
# 3. تهيئة السيرفر والأنظمة (Initialization)
# =========================================================================================
app = Flask(__name__)
app.secret_key = FLASK_SECRET
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400
logger_mgr = LoggerManager()
security_mgr = SecurityManager()
storage_mgr = EnterpriseStorageManager(logger_mgr)
backup_mgr = BackupManager(logger_mgr)
mc_server = MinecraftDaemon(logger_mgr, backup_mgr, storage_mgr)
playit_net = PlayitDaemon(logger_mgr)
watchdog = WatchdogDaemon(mc_server, backup_mgr, storage_mgr, logger_mgr)
playit_net.start_async()
mc_server.start_async()
watchdog.start()
# =========================================================================================
# 4. مسارات الـ API (Routes)
# =========================================================================================
@app.before_request
def check_auth():
    if request.path.startswith('/api/') and not session.get('logged_in'):
        abort(401)
@app.route('/')
def index():
    if not session.get('logged_in'): return render_template_string(LOGIN_HTML)
    return render_template_string(DASHBOARD_HTML)
@app.route('/login', methods=['POST'])
def login():
    ip = request.remote_addr
    is_allowed, error_msg = security_mgr.check_ip(ip)
    if not is_allowed: return error_msg, 429
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
        req = requests.get(target_url, stream=True, timeout=15)
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
        "ram": get_container_ram_percent(),
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
        if mc_server.is_running():
            logger_mgr.log("النظام", "❌ لا يمكنك فرمتة العالم والسيرفر يعمل! قم بإيقاف السيرفر أولاً.", is_safe=True)
            return "OK"
        shutil.rmtree(os.path.join(DATA_DIR, "world"), ignore_errors=True)
        logger_mgr.log("النظام", "💥 تم فرمتة العالم القديم بنجاح! شغل السيرفر لتوليد عالم جديد.", is_safe=True)
        return "OK"
    if cmd.strip().startswith("!installmod "):
        url = cmd.strip().split(" ", 1)[1]
        def download_mod():
            try:
                logger_mgr.log("النظام", f"⬇️ جاري تحميل المود من الرابط المباشر...", is_safe=True)
                mods_dir = os.path.join(DATA_DIR, "mods")
                os.makedirs(mods_dir, exist_ok=True)
                filename = url.split("/")[-1]
                if not filename.endswith(".jar"): filename = "downloaded_mod.jar"
                filepath = os.path.join(mods_dir, filename)
                response = requests.get(url, stream=True)
                response.raise_for_status()
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger_mgr.log("النظام", f"✅ تم تثبيت المود بنجاح: {filename} (يرجى إعادة تشغيل السيرفر)", is_safe=True)
            except Exception as e:
                logger_mgr.log("النظام", f"❌ فشل تحميل المود: {e}", is_safe=True)
        threading.Thread(target=download_mod, daemon=True).start()
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
    mods_list = []
    if os.path.exists(mods_path):
        for f in os.listdir(mods_path):
            if f.endswith('.jar'):
                size = os.path.getsize(os.path.join(mods_path, f))
                mods_list.append({"name": f, "size": round(size / (1024 * 1024), 2)})
    return jsonify(mods_list)
@app.route('/api/backup', methods=['GET', 'POST'])
def handle_backup_route():
    if request.method == 'POST':
        backup_mgr.create_backup_async()
        return "Started"
    backups = []
    if os.path.exists(backup_mgr.backup_dir):
        for f in os.listdir(backup_mgr.backup_dir):
            if f.endswith('.zip'):
                size = os.path.getsize(os.path.join(backup_mgr.backup_dir, f))
                backups.append({"name": f, "size": round(size / (1024 * 1024), 2)})
    return jsonify(sorted(backups, key=lambda x: x['name'], reverse=True))
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
            if file.endswith(('.json', '.properties', '.txt', '.log', '.schem', '.schematic')):
                rel_path = os.path.relpath(os.path.join(root, file), DATA_DIR)
                size = os.path.getsize(os.path.join(root, file))
                file_list.append({"name": rel_path, "size": round(size / 1024, 2)})
    return jsonify(file_list)
@app.route('/api/crash')
def get_crash():
    crash_dir = os.path.join(DATA_DIR, "crash-reports")
    if not os.path.exists(crash_dir): return "لا توجد كراشات."
    crashes = sorted([f for f in os.listdir(crash_dir) if f.endswith('.txt')], reverse=True)
    if not crashes: return "السيرفر مستقر، لا توجد تقارير كراش."
    with open(os.path.join(crash_dir, crashes[0]), 'r') as f: return html.escape(f.read())
# =========================================================================================
# 5. واجهات المستخدم (HTML/CSS/JS) - God Tier UI
# =========================================================================================
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enterprise Panel | Login</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #050505; --primary: #3b82f6; --primary-glow: rgba(59, 130, 246, 0.5); --surface: rgba(20, 20, 20, 0.7); --text: #f8fafc; }
        * { box-sizing: border-box; font-family: 'Cairo', sans-serif; }
        body { background: var(--bg); color: var(--text); display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; overflow: hidden; }
        .bg-animation { position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 0; background: radial-gradient(circle at 50% 50%, #1e1b4b 0%, #050505 100%); }
        .login-box { position: relative; z-index: 1; background: var(--surface); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); padding: 3rem; border-radius: 24px; border: 1px solid rgba(255,255,255,0.05); box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5), 0 0 40px var(--primary-glow); width: 100%; max-width: 420px; text-align: center; transform: translateY(20px); opacity: 0; animation: slideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
        @keyframes slideUp { to { transform: translateY(0); opacity: 1; } }
        .logo { font-size: 4rem; margin-bottom: 1rem; display: inline-block; filter: drop-shadow(0 0 15px var(--primary)); animation: float 3s ease-in-out infinite; }
        @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
        h1 { margin: 0 0 2rem 0; font-weight: 900; font-size: 2rem; background: linear-gradient(to right, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .input-group { position: relative; margin-bottom: 2rem; }
        input { width: 100%; padding: 1rem 1.5rem; background: rgba(0,0,0,0.5); border: 2px solid rgba(255,255,255,0.1); border-radius: 12px; color: white; font-size: 1.1rem; outline: none; transition: all 0.3s ease; text-align: center; letter-spacing: 2px; }
        input:focus { border-color: var(--primary); box-shadow: 0 0 20px var(--primary-glow); }
        button { width: 100%; padding: 1rem; background: linear-gradient(135deg, #2563eb, #7c3aed); color: white; border: none; border-radius: 12px; font-size: 1.2rem; font-weight: 700; cursor: pointer; transition: all 0.3s ease; text-transform: uppercase; letter-spacing: 1px; position: relative; overflow: hidden; }
        button:hover { transform: translateY(-2px); box-shadow: 0 10px 25px var(--primary-glow); }
        button:active { transform: translateY(1px); }
        .error { color: #ef4444; background: rgba(239, 68, 68, 0.1); padding: 0.75rem; border-radius: 8px; margin-bottom: 1.5rem; font-weight: 700; border: 1px solid rgba(239, 68, 68, 0.3); }
    </style>
</head>
<body>
    <div class="bg-animation"></div>
    <div class="login-box">
        <div class="logo">💠</div>
        <h1>Enterprise Panel</h1>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form action="/login" method="POST" onsubmit="this.querySelector('button').innerHTML = 'جاري التشفير... ⏳';">
            <div class="input-group">
                <input type="password" name="password" placeholder="أدخل مفتاح التشفير" required autofocus>
            </div>
            <button type="submit">تسجيل الدخول</button>
        </form>
    </div>
</body>
</html>
"""
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enterprise Dashboard | God-Tier</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&family=Fira+Code:wght@400;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-base: #09090b; --bg-surface: #18181b; --bg-glass: rgba(24, 24, 27, 0.6);
            --border: rgba(255, 255, 255, 0.08); --border-hover: rgba(255, 255, 255, 0.15);
            --text-main: #f8fafc; --text-muted: #94a3b8;
            --primary: #3b82f6; --primary-hover: #2563eb; --primary-glow: rgba(59, 130, 246, 0.4);
            --success: #10b981; --success-glow: rgba(16, 185, 129, 0.4);
            --danger: #ef4444; --danger-glow: rgba(239, 68, 68, 0.4);
            --warning: #f59e0b; --info: #0ea5e9;
            --radius-lg: 16px; --radius-md: 12px; --radius-sm: 8px;
            --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Cairo', sans-serif; background: var(--bg-base); color: var(--text-main); display: flex; height: 100vh; overflow: hidden; }
        /* Scrollbar */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg-base); }
        ::-webkit-scrollbar-thumb { background: #3f3f46; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #52525b; }
        /* Sidebar */
        .sidebar { width: 280px; background: var(--bg-surface); border-left: 1px solid var(--border); display: flex; flex-direction: column; z-index: 100; transition: var(--transition); }
        .brand { padding: 24px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid var(--border); }
        .brand i { font-size: 28px; color: var(--primary); filter: drop-shadow(0 0 8px var(--primary-glow)); }
        .brand h2 { font-size: 20px; font-weight: 800; letter-spacing: 1px; background: linear-gradient(90deg, #fff, #94a3b8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .nav-menu { padding: 16px 12px; flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
        .nav-item { padding: 14px 16px; border-radius: var(--radius-md); cursor: pointer; display: flex; align-items: center; gap: 14px; color: var(--text-muted); font-weight: 600; transition: var(--transition); border: 1px solid transparent; }
        .nav-item i { font-size: 18px; width: 24px; text-align: center; }
        .nav-item:hover { background: rgba(255,255,255,0.03); color: var(--text-main); border-color: var(--border); transform: translateX(-4px); }
        .nav-item.active { background: linear-gradient(90deg, rgba(59,130,246,0.15), transparent); color: var(--primary); border-color: var(--primary-glow); border-right: 3px solid var(--primary); }
        /* Main Content */
        .main-wrapper { flex: 1; display: flex; flex-direction: column; overflow: hidden; position: relative; }
        .bg-glow { position: absolute; top: -20%; left: -10%; width: 50%; height: 50%; background: radial-gradient(circle, var(--primary-glow) 0%, transparent 70%); filter: blur(100px); z-index: 0; pointer-events: none; opacity: 0.5; }
        /* Header */
        .header { padding: 20px 32px; display: flex; justify-content: space-between; align-items: center; background: var(--bg-glass); backdrop-filter: blur(12px); border-bottom: 1px solid var(--border); z-index: 10; }
        .network-pill { display: flex; align-items: center; gap: 12px; background: rgba(0,0,0,0.4); padding: 8px 16px; border-radius: 50px; border: 1px solid var(--border); }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--danger); box-shadow: 0 0 10px var(--danger-glow); }
        .status-dot.online { background: var(--success); box-shadow: 0 0 10px var(--success-glow); animation: pulse 2s infinite; }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 var(--success-glow); } 70% { box-shadow: 0 0 0 10px rgba(16,185,129,0); } 100% { box-shadow: 0 0 0 0 rgba(16,185,129,0); } }
        .ip-text { font-family: 'Fira Code', monospace; font-weight: 600; font-size: 15px; letter-spacing: 0.5px; }
        .btn-icon { background: transparent; border: 1px solid var(--border); color: var(--text-main); width: 36px; height: 36px; border-radius: 50%; cursor: pointer; transition: var(--transition); display: flex; justify-content: center; align-items: center; }
        .btn-icon:hover { background: var(--border-hover); transform: scale(1.1); }
        .btn-logout { background: rgba(239,68,68,0.1); color: var(--danger); border: 1px solid rgba(239,68,68,0.2); padding: 8px 20px; border-radius: 50px; text-decoration: none; font-weight: 600; transition: var(--transition); display: flex; align-items: center; gap: 8px; }
        .btn-logout:hover { background: var(--danger); color: white; box-shadow: 0 4px 15px var(--danger-glow); }
        /* Content Area */
        .content { flex: 1; padding: 32px; overflow-y: auto; z-index: 1; position: relative; }
        .tab-pane { display: none; animation: fadeUp 0.4s ease forwards; }
        .tab-pane.active { display: block; }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: translateY(0); } }
        /* Stats Grid */
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 24px; margin-bottom: 32px; }
        .stat-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 24px; position: relative; overflow: hidden; transition: var(--transition); }
        .stat-card:hover { border-color: var(--border-hover); transform: translateY(-5px); box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .stat-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; color: var(--text-muted); font-weight: 600; font-size: 14px; }
        .stat-header i { font-size: 20px; color: var(--primary); }
        .stat-value { font-size: 36px; font-weight: 800; font-family: 'Fira Code', monospace; }
        .chart-bg { position: absolute; bottom: 0; left: 0; width: 100%; height: 60px; opacity: 0.2; }
        /* Buttons */
        .btn { padding: 12px 24px; border-radius: var(--radius-md); border: none; font-weight: 700; font-family: 'Cairo'; cursor: pointer; transition: var(--transition); display: inline-flex; align-items: center; gap: 10px; font-size: 15px; color: white; }
        .btn-primary { background: linear-gradient(135deg, var(--primary), #6366f1); box-shadow: 0 4px 15px var(--primary-glow); }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 25px var(--primary-glow); }
        .btn-success { background: linear-gradient(135deg, var(--success), #059669); box-shadow: 0 4px 15px var(--success-glow); }
        .btn-danger { background: linear-gradient(135deg, var(--danger), #dc2626); box-shadow: 0 4px 15px var(--danger-glow); }
        .btn-warning { background: linear-gradient(135deg, var(--warning), #d97706); }
        .btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text-main); }
        .btn-outline:hover { background: var(--border-hover); }
        /* Console */
        .console-container { background: #000; border: 1px solid var(--border); border-radius: var(--radius-lg); display: flex; flex-direction: column; height: 60vh; box-shadow: inset 0 0 20px rgba(0,0,0,0.8); overflow: hidden; }
        .console-header { background: #111; padding: 12px 20px; border-bottom: 1px solid #222; display: flex; justify-content: space-between; align-items: center; }
        .console-title { font-family: 'Fira Code', monospace; font-size: 13px; color: #888; display: flex; align-items: center; gap: 8px; }
        .console-title i { color: var(--primary); }
        .console-output { flex: 1; padding: 20px; overflow-y: auto; font-family: 'Fira Code', monospace; font-size: 14px; line-height: 1.6; color: #ccc; direction: ltr; text-align: left; }
        .log-time { color: #555; } .log-source { font-weight: bold; } .log-msg { color: #ddd; }
        .console-input-wrapper { display: flex; background: #111; border-top: 1px solid #222; padding: 10px; }
        .console-prefix { padding: 10px; color: var(--primary); font-family: 'Fira Code'; font-weight: bold; }
        .console-input { flex: 1; background: transparent; border: none; color: #fff; font-family: 'Fira Code', monospace; font-size: 15px; outline: none; }
        /* Player Grid */
        .player-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }
        .player-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 20px; display: flex; flex-direction: column; align-items: center; gap: 15px; transition: var(--transition); position: relative; overflow: hidden; }
        .player-card:hover { border-color: var(--primary); transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.3); }
        .player-head { width: 80px; height: 80px; border-radius: 12px; image-rendering: pixelated; box-shadow: 0 8px 16px rgba(0,0,0,0.5); border: 2px solid rgba(255,255,255,0.1); }
        .player-name { font-size: 18px; font-weight: 800; font-family: 'Fira Code'; }
        .player-actions { display: flex; gap: 8px; width: 100%; justify-content: center; flex-wrap: wrap; }
        .player-actions .btn { padding: 8px 12px; font-size: 12px; flex: 1; min-width: 80px; justify-content: center; }
        /* Lists (Mods, Files, Backups) */
        .data-list { display: flex; flex-direction: column; gap: 12px; }
        .data-item { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 16px 20px; display: flex; justify-content: space-between; align-items: center; transition: var(--transition); }
        .data-item:hover { border-color: var(--border-hover); background: rgba(255,255,255,0.02); }
        .data-info { display: flex; align-items: center; gap: 16px; }
        .data-icon { width: 40px; height: 40px; border-radius: 10px; background: rgba(255,255,255,0.05); display: flex; justify-content: center; align-items: center; font-size: 20px; color: var(--primary); }
        .data-name { font-weight: 700; font-size: 16px; font-family: 'Fira Code'; direction: ltr; }
        .data-meta { font-size: 13px; color: var(--text-muted); margin-top: 4px; }
        /* Drag & Drop Zone */
        .drop-zone { border: 2px dashed var(--border); border-radius: var(--radius-lg); padding: 40px; text-align: center; background: rgba(0,0,0,0.2); cursor: pointer; transition: var(--transition); margin-bottom: 24px; }
        .drop-zone:hover, .drop-zone.dragover { border-color: var(--primary); background: rgba(59,130,246,0.05); }
        .drop-zone i { font-size: 48px; color: var(--primary); margin-bottom: 16px; }
        .drop-zone p { font-size: 16px; color: var(--text-muted); }
        /* Settings Toggles */
        .settings-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; }
        .setting-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 20px; display: flex; justify-content: space-between; align-items: center; transition: var(--transition); }
        .setting-card:focus-within { border-color: var(--primary); }
        .setting-info h4 { font-size: 15px; margin-bottom: 4px; }
        .setting-info p { font-size: 12px; color: var(--text-muted); font-family: 'Fira Code'; }
        /* Custom Toggle Switch */
        .switch { position: relative; display: inline-block; width: 50px; height: 28px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(255,255,255,0.1); transition: .4s; border-radius: 34px; border: 1px solid var(--border); }
        .slider:before { position: absolute; content: ""; height: 20px; width: 20px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }
        input:checked + .slider { background-color: var(--success); border-color: var(--success); }
        input:checked + .slider:before { transform: translateX(22px); }
        /* Custom Inputs */
        .custom-input { background: rgba(0,0,0,0.3); border: 1px solid var(--border); color: white; padding: 8px 12px; border-radius: 6px; outline: none; font-family: 'Fira Code'; width: 120px; text-align: center; transition: 0.3s; }
        .custom-input:focus { border-color: var(--primary); }
        .custom-select { background: rgba(0,0,0,0.3); border: 1px solid var(--border); color: white; padding: 8px 12px; border-radius: 6px; outline: none; font-family: 'Cairo'; font-weight: bold; cursor: pointer; }
        /* Custom Modal */
        .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); backdrop-filter: blur(5px); z-index: 9999; display: flex; justify-content: center; align-items: center; opacity: 0; pointer-events: none; transition: 0.3s; }
        .modal-overlay.active { opacity: 1; pointer-events: all; }
        .modal-box { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 32px; width: 90%; max-width: 400px; text-align: center; transform: scale(0.9); transition: 0.3s; box-shadow: 0 25px 50px rgba(0,0,0,0.5); }
        .modal-overlay.active .modal-box { transform: scale(1); }
        .modal-icon { font-size: 48px; margin-bottom: 16px; }
        .modal-title { font-size: 22px; font-weight: 800; margin-bottom: 12px; }
        .modal-desc { color: var(--text-muted); margin-bottom: 24px; font-size: 15px; }
        .modal-actions { display: flex; gap: 12px; justify-content: center; }
        .modal-actions .btn { flex: 1; justify-content: center; }
        /* Toasts */
        #toast-container { position: fixed; bottom: 24px; left: 24px; z-index: 10000; display: flex; flex-direction: column; gap: 12px; }
        .toast { background: var(--bg-surface); border: 1px solid var(--border); padding: 16px 24px; border-radius: var(--radius-md); display: flex; align-items: center; gap: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); animation: slideRight 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; position: relative; overflow: hidden; }
        @keyframes slideRight { from { transform: translateX(-100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        .toast-icon { font-size: 20px; }
        .toast-success .toast-icon { color: var(--success); }
        .toast-error .toast-icon { color: var(--danger); }
        .toast-info .toast-icon { color: var(--info); }
        .toast-progress { position: absolute; bottom: 0; left: 0; height: 3px; background: var(--primary); width: 100%; animation: progress 4s linear forwards; }
        @keyframes progress { to { width: 0; } }
        /* File Viewer */
        .file-viewer-container { display: none; margin-top: 20px; border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; }
        .file-viewer-header { background: #111; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #222; }
        .file-viewer-content { background: #000; padding: 20px; color: #e2e8f0; font-family: 'Fira Code', monospace; font-size: 14px; white-space: pre-wrap; max-height: 500px; overflow-y: auto; direction: ltr; text-align: left; }
        @media (max-width: 900px) {
            body { flex-direction: column; }
            .sidebar { width: 100%; height: auto; flex-direction: row; overflow-x: auto; padding: 10px; border-left: none; border-bottom: 1px solid var(--border); }
            .brand { display: none; }
            .nav-menu { flex-direction: row; padding: 0; }
            .nav-item { white-space: nowrap; border-right: none; border-bottom: 3px solid transparent; }
            .nav-item.active { border-right: none; border-bottom-color: var(--primary); background: linear-gradient(0deg, rgba(59,130,246,0.15), transparent); }
            .header { flex-direction: column; gap: 15px; }
        }
    </style>
</head>
<body>
    <!-- Custom Modal -->
    <div class="modal-overlay" id="custom-modal">
        <div class="modal-box">
            <div class="modal-icon" id="modal-icon">⚠️</div>
            <h3 class="modal-title" id="modal-title">تأكيد الإجراء</h3>
            <p class="modal-desc" id="modal-desc">هل أنت متأكد من هذا الإجراء؟</p>
            <div class="modal-actions">
                <button class="btn btn-outline" onclick="closeModal()">إلغاء</button>
                <button class="btn btn-danger" id="modal-confirm">تأكيد</button>
            </div>
        </div>
    </div>
    <div id="toast-container"></div>
    <div class="sidebar">
        <div class="brand">
            <i class="fa-solid fa-shield-halved"></i>
            <h2>Enterprise</h2>
        </div>
        <div class="nav-menu">
            <div class="nav-item active" onclick="openTab('dashboard', this)"><i class="fa-solid fa-chart-pie"></i> نظرة عامة</div>
            <div class="nav-item" onclick="openTab('console', this)"><i class="fa-solid fa-terminal"></i> الكونسول</div>
            <div class="nav-item" onclick="openTab('players', this)"><i class="fa-solid fa-users"></i> اللاعبين</div>
            <div class="nav-item" onclick="openTab('mods', this); loadMods();"><i class="fa-solid fa-puzzle-piece"></i> المودات</div>
            <div class="nav-item" onclick="openTab('files', this); loadFiles();"><i class="fa-solid fa-folder-open"></i> الملفات</div>
            <div class="nav-item" onclick="openTab('backups', this); loadBackups();"><i class="fa-solid fa-box-archive"></i> النسخ الاحتياطي</div>
            <div class="nav-item" onclick="openTab('settings', this); loadConfig();"><i class="fa-solid fa-sliders"></i> الإعدادات</div>
            <div class="nav-item" onclick="openTab('livemap', this)"><i class="fa-solid fa-map-location-dot"></i> الخريطة</div>
        </div>
    </div>
    <div class="main-wrapper">
        <div class="bg-glow"></div>
        <div class="header">
            <div class="network-pill">
                <div class="status-dot" id="net-dot"></div>
                <span class="ip-text" id="ip-display">جاري الاتصال...</span>
                <button class="btn-icon" onclick="copyIP()" title="نسخ الآي بي"><i class="fa-regular fa-copy"></i></button>
            </div>
            <div style="display: flex; gap: 15px;">
                <button class="btn-icon" onclick="updateStatus()" title="تحديث البيانات"><i class="fa-solid fa-rotate-right"></i></button>
                <a href="/logout" class="btn-logout"><i class="fa-solid fa-arrow-right-from-bracket"></i> خروج</a>
            </div>
        </div>
        <div class="content">
            <!-- Dashboard Tab -->
            <div id="dashboard" class="tab-pane active">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-header"><span>حالة السيرفر</span> <i class="fa-solid fa-server"></i></div>
                        <div class="stat-value" id="status-text" style="font-family: 'Cairo';">جاري التحميل...</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-header"><span>اللاعبين المتصلين</span> <i class="fa-solid fa-users"></i></div>
                        <div class="stat-value" id="players-count">0<span style="font-size:16px; color:var(--text-muted)">/20</span></div>
                    </div>
                    <div class="stat-card" style="padding-bottom: 60px;">
                        <div class="stat-header"><span>استهلاك المعالج</span> <i class="fa-solid fa-microchip"></i></div>
                        <div class="stat-value" id="cpu-text">0%</div>
                        <div class="chart-bg"><canvas id="cpuChart"></canvas></div>
                    </div>
                    <div class="stat-card" style="padding-bottom: 60px;">
                        <div class="stat-header"><span>استهلاك الرام</span> <i class="fa-solid fa-memory"></i></div>
                        <div class="stat-value" id="ram-text">0%</div>
                        <div class="chart-bg"><canvas id="ramChart"></canvas></div>
                    </div>
                </div>
                <h3 style="margin-bottom: 20px; font-weight: 800;">التحكم السريع</h3>
                <div style="display: flex; gap: 15px; flex-wrap: wrap;">
                    <button class="btn btn-success" onclick="sendAction('start')"><i class="fa-solid fa-play"></i> تشغيل السيرفر</button>
                    <button class="btn btn-warning" onclick="sendAction('stop')"><i class="fa-solid fa-stop"></i> إيقاف آمن</button>
                    <button class="btn btn-danger" onclick="confirmAction('إيقاف إجباري', 'هل أنت متأكد؟ قد تفقد آخر التغييرات في العالم.', () => sendAction('kill'))"><i class="fa-solid fa-skull"></i> إيقاف إجباري</button>
                    <button class="btn btn-outline" onclick="confirmAction('فرمتة العالم', 'تحذير خطير! سيتم مسح العالم بالكامل ولا يمكن التراجع. هل أنت متأكد؟', () => execCmd('!resetworld'))" style="color: var(--danger); border-color: var(--danger);"><i class="fa-solid fa-bomb"></i> فرمتة العالم</button>
                </div>
            </div>
            <!-- Console Tab -->
            <div id="console" class="tab-pane">
                <div class="console-container">
                    <div class="console-header">
                        <div class="console-title"><i class="fa-solid fa-terminal"></i> root@enterprise-server:~</div>
                        <button class="btn-icon" style="width:28px; height:28px; font-size:12px;" onclick="toggleAutoScroll()" title="إيقاف/تشغيل التمرير التلقائي"><i class="fa-solid fa-lock-open" id="scroll-icon"></i></button>
                    </div>
                    <div class="console-output" id="console-box"></div>
                    <div class="console-input-wrapper">
                        <span class="console-prefix">/</span>
                        <input type="text" id="cmd" class="console-input" placeholder="اكتب الأمر هنا (استخدم الأسهم للتنقل في التاريخ)..." autocomplete="off">
                        <button class="btn btn-primary" style="padding: 8px 20px;" onclick="sendCmd()"><i class="fa-solid fa-paper-plane"></i></button>
                    </div>
                </div>
            </div>
            <!-- Players Tab -->
            <div id="players" class="tab-pane">
                <div class="player-grid" id="players-list">
                    <p style="color: var(--text-muted); grid-column: 1/-1; text-align: center; padding: 40px;">جاري التحميل...</p>
                </div>
            </div>
            <!-- Mods Tab -->
            <div id="mods" class="tab-pane">
                <div class="drop-zone" id="drop-zone" onclick="document.getElementById('mod-file').click()">
                    <i class="fa-solid fa-cloud-arrow-up"></i>
                    <h3 style="margin-bottom: 8px;">اسحب وأفلت المودات هنا</h3>
                    <p>أو اضغط لاختيار ملف (.jar)</p>
                    <input type="file" id="mod-file" accept=".jar" style="display: none;" onchange="handleFileUpload(this.files)">
                </div>
                <div class="data-list" id="mods-list">جاري التحميل...</div>
            </div>
            <!-- Files Tab -->
            <div id="files" class="tab-pane">
                <div class="data-list" id="files-list" style="max-height: 40vh; overflow-y: auto;">جاري التحميل...</div>
                <div class="file-viewer-container" id="file-viewer-container">
                    <div class="file-viewer-header">
                        <span style="font-family: 'Fira Code'; font-weight: bold;" id="viewer-title">file.txt</span>
                        <button class="btn-icon" style="width:28px; height:28px;" onclick="document.getElementById('file-viewer-container').style.display='none'"><i class="fa-solid fa-xmark"></i></button>
                    </div>
                    <div class="file-viewer-content" id="file-viewer"></div>
                </div>
            </div>
            <!-- Backups Tab -->
            <div id="backups" class="tab-pane">
                <button class="btn btn-primary" onclick="createBackup()" style="width: 100%; justify-content: center; padding: 16px; font-size: 18px; margin-bottom: 24px;">
                    <i class="fa-solid fa-box-archive"></i> إنشاء نسخة احتياطية الآن
                </button>
                <div class="data-list" id="backups-list">جاري التحميل...</div>
            </div>
            <!-- Settings Tab -->
            <div id="settings" class="tab-pane">
                <div class="settings-grid" id="config-form">جاري التحميل...</div>
                <button class="btn btn-success" onclick="saveConfig()" style="width: 100%; justify-content: center; padding: 16px; font-size: 18px; margin-top: 24px;">
                    <i class="fa-solid fa-floppy-disk"></i> حفظ الإعدادات (يتطلب إعادة تشغيل)
                </button>
            </div>
            <!-- Livemap Tab -->
            <div id="livemap" class="tab-pane" style="height: 75vh;">
                <iframe id="map-frame" src="/map/" style="width: 100%; height: 100%; border: 1px solid var(--border); border-radius: var(--radius-lg); background: #000;"></iframe>
            </div>
        </div>
    </div>
    <script>
        // --- UI Utilities ---
        function showToast(message, type = 'success') {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            const icon = type === 'success' ? 'fa-check-circle' : (type === 'error' ? 'fa-circle-exclamation' : 'fa-circle-info');
            toast.innerHTML = `
                <i class="fa-solid ${icon} toast-icon"></i>
                <span style="font-weight: 600;">${message}</span>
                <div class="toast-progress"></div>
            `;
            container.appendChild(toast);
            setTimeout(() => {
                toast.style.animation = 'slideRight 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) reverse forwards';
                setTimeout(() => toast.remove(), 400);
            }, 4000);
        }
        let modalCallback = null;
        function confirmAction(title, desc, callback) {
            document.getElementById('modal-title').innerText = title;
            document.getElementById('modal-desc').innerText = desc;
            document.getElementById('modal-icon').innerText = title.includes('إجباري') || title.includes('فرمتة') ? '💀' : '⚠️';
            document.getElementById('custom-modal').classList.add('active');
            modalCallback = callback;
        }
        function closeModal() {
            document.getElementById('custom-modal').classList.remove('active');
            modalCallback = null;
        }
        document.getElementById('modal-confirm').addEventListener('click', () => {
            if(modalCallback) modalCallback();
            closeModal();
        });
        function copyIP() {
            const ipText = document.getElementById('ip-display').innerText;
            navigator.clipboard.writeText(ipText).then(() => showToast('تم نسخ الآي بي بنجاح!', 'success'));
        }
        function openTab(tabName, btnElement) {
            document.querySelectorAll('.tab-pane').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(t => t.classList.remove('active'));
            document.getElementById(tabName).classList.add('active');
            if(btnElement) btnElement.classList.add('active');
        }
        // --- Charts ---
        const chartOptions = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { enabled: false } }, scales: { x: { display: false }, y: { display: false, min: 0, max: 100 } }, elements: { point: { radius: 0 }, line: { tension: 0.4, borderWidth: 2 } } };
        const cpuChart = new Chart(document.getElementById('cpuChart').getContext('2d'), { type: 'line', data: { labels: Array(20).fill(''), datasets: [{ data: Array(20).fill(0), borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.1)', fill: true }] }, options: chartOptions });
        const ramChart = new Chart(document.getElementById('ramChart').getContext('2d'), { type: 'line', data: { labels: Array(20).fill(''), datasets: [{ data: Array(20).fill(0), borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.1)', fill: true }] }, options: chartOptions });
        function updateCharts(cpu, ram) {
            cpuChart.data.datasets[0].data.push(cpu); cpuChart.data.datasets[0].data.shift(); cpuChart.update('none');
            ramChart.data.datasets[0].data.push(ram); ramChart.data.datasets[0].data.shift(); ramChart.update('none');
        }
        // --- Console Logic ---
        let autoScroll = true;
        const consoleBox = document.getElementById('console-box');
        const cmdInput = document.getElementById('cmd');
        let cmdHistory = [];
        let historyIndex = -1;
        consoleBox.addEventListener('scroll', () => {
            autoScroll = (consoleBox.scrollHeight - consoleBox.scrollTop - consoleBox.clientHeight < 50);
            document.getElementById('scroll-icon').className = autoScroll ? "fa-solid fa-lock-open" : "fa-solid fa-lock";
        });
        function toggleAutoScroll() {
            autoScroll = !autoScroll;
            document.getElementById('scroll-icon').className = autoScroll ? "fa-solid fa-lock-open" : "fa-solid fa-lock";
            if(autoScroll) consoleBox.scrollTop = consoleBox.scrollHeight;
        }
        cmdInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') sendCmd();
            else if (e.key === 'ArrowUp') {
                if (cmdHistory.length > 0 && historyIndex < cmdHistory.length - 1) {
                    historyIndex++;
                    cmdInput.value = cmdHistory[cmdHistory.length - 1 - historyIndex];
                }
                e.preventDefault();
            } else if (e.key === 'ArrowDown') {
                if (historyIndex > 0) {
                    historyIndex--;
                    cmdInput.value = cmdHistory[cmdHistory.length - 1 - historyIndex];
                } else if (historyIndex === 0) {
                    historyIndex = -1;
                    cmdInput.value = '';
                }
                e.preventDefault();
            }
        });
        function sendCmd() {
            let cmd = cmdInput.value.trim();
            if(cmd === "") return;
            if(cmdHistory[cmdHistory.length-1] !== cmd) cmdHistory.push(cmd);
            historyIndex = -1;
            execCmd(cmd);
            cmdInput.value = '';
            autoScroll = true;
        }
        // --- API Calls ---
        function execCmd(cmd) {
            fetch('/api/command', { method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: 'cmd=' + encodeURIComponent(cmd) });
        }
        function sendAction(act) {
            if(act === 'stop') showToast('تم إرسال أمر الإيقاف الآمن...', 'info');
            if(act === 'start') showToast('جاري تشغيل السيرفر...', 'info');
            fetch('/api/action', { method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: 'action=' + act });
        }
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
                statusEl.style.color = data.status.includes('شغال') ? 'var(--success)' : 'var(--danger)';
                document.getElementById('players-count').innerHTML = `${data.players.length}<span style="font-size:16px; color:var(--text-muted)">/20</span>`;
                let ipDisplay = document.getElementById('ip-display');
                let netDot = document.getElementById('net-dot');
                ipDisplay.innerText = data.network.ip;
                if(data.network.status === 'error') { netDot.className = 'status-dot'; ipDisplay.style.color = 'var(--danger)'; }
                else { netDot.className = 'status-dot online'; ipDisplay.style.color = 'var(--text-main)'; }
                consoleBox.innerHTML = data.logs.join('<br>');
                if (autoScroll) consoleBox.scrollTop = consoleBox.scrollHeight;
                // Render Players Grid
                let p_html = data.players.length === 0 ? '<p style="color: var(--text-muted); grid-column: 1/-1; text-align: center; padding: 40px;">لا يوجد لاعبين متصلين حالياً.</p>' : '';
                data.players.forEach(p => {
                    p_html += `
                    <div class="player-card">
                        <img src="https://minotar.net/helm/${p}/100.png" class="player-head" alt="${p}" onerror="this.src='https://minotar.net/helm/MHF_Steve/100.png'">
                        <div class="player-name">${p}</div>
                        <div class="player-actions">
                            <button class="btn btn-outline" onclick="execCmd('op ${p}')" title="إعطاء أدمن"><i class="fa-solid fa-crown" style="color:var(--warning)"></i></button>
                            <button class="btn btn-outline" onclick="execCmd('gamemode creative ${p}')" title="كريتف"><i class="fa-solid fa-cube" style="color:var(--info)"></i></button>
                            <button class="btn btn-outline" onclick="execCmd('gamemode survival ${p}')" title="سرفايفل"><i class="fa-solid fa-heart" style="color:var(--danger)"></i></button>
                            <button class="btn btn-outline" onclick="confirmAction('طرد لاعب', 'هل تريد طرد ${p}؟', () => execCmd('kick ${p}'))" title="طرد"><i class="fa-solid fa-boot"></i></button>
                        </div>
                    </div>`;
                });
                document.getElementById('players-list').innerHTML = p_html;
            }).catch(err => console.error("Status fetch error:", err));
        }
        setInterval(updateStatus, 2000);
        // --- Mods Management ---
        const dropZone = document.getElementById('drop-zone');
        dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
        dropZone.addEventListener('drop', (e) => { e.preventDefault(); dropZone.classList.remove('dragover'); handleFileUpload(e.dataTransfer.files); });
        function handleFileUpload(files) {
            if(files.length === 0) return;
            let file = files[0];
            if(!file.name.endsWith('.jar')) return showToast('يجب أن يكون الملف بصيغة .jar', 'error');
            let formData = new FormData();
            formData.append("file", file);
            showToast('جاري رفع المود...', 'info');
            fetch('/api/mods', { method: 'POST', body: formData }).then(() => {
                showToast('تم رفع المود بنجاح!', 'success');
                loadMods();
            }).catch(() => showToast('فشل الرفع!', 'error'));
        }
        function loadMods() {
            fetch('/api/mods').then(res => res.json()).then(mods => {
                let html = mods.length === 0 ? '<p style="color: var(--text-muted); text-align:center; padding: 20px;">لا توجد مودات مثبتة.</p>' : '';
                mods.forEach(mod => {
                    html += `
                    <div class="data-item">
                        <div class="data-info">
                            <div class="data-icon"><i class="fa-brands fa-java"></i></div>
                            <div>
                                <div class="data-name">${mod.name}</div>
                                <div class="data-meta">${mod.size} MB</div>
                            </div>
                        </div>
                        <button class="btn btn-outline" style="color:var(--danger); border-color:var(--danger);" onclick="confirmAction('حذف مود', 'هل تريد حذف ${mod.name}؟', () => deleteMod('${mod.name}'))"><i class="fa-solid fa-trash"></i></button>
                    </div>`;
                });
                document.getElementById('mods-list').innerHTML = html;
            });
        }
        function deleteMod(modName) {
            fetch('/api/mods', { method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: 'delete=' + encodeURIComponent(modName) }).then(() => {
                showToast('تم الحذف بنجاح!', 'success'); loadMods();
            });
        }
        // --- Files Management ---
        function loadFiles() {
            fetch('/api/files').then(res => res.json()).then(files => {
                let html = files.length === 0 ? '<p style="color: var(--text-muted); text-align:center; padding: 20px;">لا توجد ملفات.</p>' : '';
                files.forEach(f => {
                    let icon = f.name.endsWith('.json') ? 'fa-code' : (f.name.endsWith('.schem') ? 'fa-cubes' : 'fa-file-lines');
                    html += `
                    <div class="data-item">
                        <div class="data-info">
                            <div class="data-icon"><i class="fa-solid ${icon}"></i></div>
                            <div>
                                <div class="data-name">${f.name}</div>
                                <div class="data-meta">${f.size} KB</div>
                            </div>
                        </div>
                        <div style="display:flex; gap:8px;">
                            <button class="btn btn-outline" onclick="readFile('${f.name}')"><i class="fa-solid fa-eye"></i></button>
                            <button class="btn btn-outline" style="color:var(--danger); border-color:var(--danger);" onclick="confirmAction('حذف ملف', 'هل تريد حذف ${f.name}؟', () => deleteFile('${f.name}'))"><i class="fa-solid fa-trash"></i></button>
                        </div>
                    </div>`;
                });
                document.getElementById('files-list').innerHTML = html;
            });
        }
        function readFile(filename) {
            let formData = new FormData(); formData.append('action', 'read'); formData.append('target', filename);
            fetch('/api/files', { method: 'POST', body: formData }).then(res => res.text()).then(text => {
                document.getElementById('viewer-title').innerText = filename;
                document.getElementById('file-viewer').innerText = text;
                document.getElementById('file-viewer-container').style.display = 'block';
                document.getElementById('file-viewer-container').scrollIntoView({behavior: "smooth"});
            });
        }
        function deleteFile(filename) {
            let formData = new FormData(); formData.append('action', 'delete'); formData.append('target', filename);
            fetch('/api/files', { method: 'POST', body: formData }).then(() => {
                showToast('تم الحذف بنجاح!', 'success');
                document.getElementById('file-viewer-container').style.display = 'none';
                loadFiles();
            });
        }
        // --- Backups ---
        function loadBackups() {
            fetch('/api/backup').then(res => res.json()).then(backups => {
                let html = backups.length === 0 ? '<p style="color: var(--text-muted); text-align:center; padding: 20px;">لا توجد نسخ احتياطية.</p>' : '';
                backups.forEach(b => {
                    html += `
                    <div class="data-item">
                        <div class="data-info">
                            <div class="data-icon"><i class="fa-solid fa-file-zipper"></i></div>
                            <div>
                                <div class="data-name">${b.name}</div>
                                <div class="data-meta">${b.size} MB</div>
                            </div>
                        </div>
                        <a href="/api/backup/download/${b.name}" class="btn btn-outline" style="color:var(--success); border-color:var(--success); text-decoration:none;"><i class="fa-solid fa-download"></i> تحميل</a>
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
        // --- Settings ---
        function loadConfig() {
            fetch('/api/config').then(res => res.json()).then(data => {
                let html = '';
                data.schema.forEach(f => {
                    let val = data.values[f.key] !== undefined ? data.values[f.key] : f.default;
                    html += `<div class="setting-card">
                                <div class="setting-info">
                                    <h4>${f.label}</h4>
                                    <p>${f.key}</p>
                                </div>`;
                    if(f.type === 'boolean') {
                        let checked = val === 'true' ? 'checked' : '';
                        html += `<label class="switch"><input type="checkbox" id="cfg-${f.key}" data-key="${f.key}" ${checked}><span class="slider"></span></label>`;
                    } else if(f.type === 'select') {
                        html += `<select class="custom-select" id="cfg-${f.key}" data-key="${f.key}">`;
                        f.options.forEach(opt => { html += `<option value="${opt}" ${val===opt?'selected':''}>${opt}</option>`; });
                        html += `</select>`;
                    } else {
                        html += `<input class="custom-input" type="${f.type}" id="cfg-${f.key}" data-key="${f.key}" value="${val}">`;
                    }
                    html += `</div>`;
                });
                document.getElementById('config-form').innerHTML = html;
            });
        }
        function saveConfig() {
            let data = {};
            document.querySelectorAll('#config-form input, #config-form select').forEach(el => {
                if(el.type === 'checkbox') {
                    data[el.getAttribute('data-key')] = el.checked ? 'true' : 'false';
                } else if(el.value.trim() !== '') {
                    data[el.getAttribute('data-key')] = el.value;
                }
            });
            fetch('/api/config', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) }).then(() => {
                showToast('تم حفظ الإعدادات بنجاح!', 'success');
            });
        }
        // --- Crash Reports ---
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
