import os
import sys
import time
import threading
import subprocess
import re
import shutil
import psutil
import html
import requests
from collections import deque
from flask import Flask, render_template_string, request, redirect, session, jsonify, send_from_directory, abort, Response
from werkzeug.utils import secure_filename
# ==========================================
# 1. الإعدادات الأساسية والأمنية (Security & Config)
# ==========================================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", os.urandom(32))
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400
PASSWORD = os.environ.get("PANEL_PASSWORD", "2938")
DATA_DIR = "/data/minecraft_data"
APP_DIR = "/app/minecraft"
failed_logins = {}
MAX_ATTEMPTS = 5
LOCKOUT_TIME = 900
mc_process = None
playit_process = None
server_logs = deque(maxlen=500)
online_players = set()
network_info = {
    "status": "loading",
    "ip": "جاري الاتصال...",
    "details": ""
}
ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
# ==========================================
# 2. دوال النظام المساعدة (Helper Functions)
# ==========================================
def force_symlink(src, dst):
    try:
        if os.path.islink(dst) or os.path.isfile(dst): os.remove(dst)
        elif os.path.isdir(dst): shutil.rmtree(dst)
        os.symlink(src, dst)
    except Exception as e:
        server_logs.append(f"[النظام] ⚠️ تحذير أثناء ربط {os.path.basename(dst)}: {html.escape(str(e))}")
def setup_environment():
    server_logs.append("[النظام] 🛠️ جاري تهيئة بيئة السيرفر (Ultimate Secure Mode)...")
    os.makedirs(os.path.join(DATA_DIR, "world"), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "mods"), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "config"), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "backups"), exist_ok=True)
    os.makedirs(APP_DIR, exist_ok=True)
    force_symlink(os.path.join(DATA_DIR, "world"), os.path.join(APP_DIR, "world"))
    files_to_link = ['server.properties', 'ops.json', 'banned-players.json', 'banned-ips.json', 'whitelist.json', 'usercache.json']
    for f in files_to_link:
        file_path = os.path.join(DATA_DIR, f)
        if not os.path.exists(file_path):
            with open(file_path, 'w') as file:
                if f == 'server.properties': file.write("online-mode=false\n")
                elif f.endswith('.json'): file.write("[]\n")
        force_symlink(file_path, os.path.join(APP_DIR, f))
    with open(os.path.join(APP_DIR, "eula.txt"), 'w') as f: f.write("eula=true\n")
    fabric_jar = os.path.join(APP_DIR, "fabric-server-launch.jar")
    if not os.path.exists(fabric_jar):
        server_logs.append("[النظام] ⬇️ جاري تحميل محرك Fabric...")
        installer_path = os.path.join(APP_DIR, "fabric-installer.jar")
        subprocess.run(["wget", "-q", "-O", installer_path, "https://maven.fabricmc.net/net/fabricmc/fabric-installer/1.0.1/fabric-installer-1.0.1.jar"])
        subprocess.run(["java", "-jar", "fabric-installer.jar", "server", "-mcversion", "1.20.4", "-loader", "0.15.7", "-downloadMinecraft"], cwd=APP_DIR)
        if os.path.exists(installer_path): os.remove(installer_path)
    server_logs.append("[النظام] ✅ تمت التهيئة بنجاح.")
# ==========================================
# 3. إدارة العمليات (Playit & Minecraft)
# ==========================================
def start_playit():
    global playit_process, network_info
    secret = os.environ.get("PLAYIT_SECRET")
    static_ip = os.environ.get("PLAYIT_IP", "الآي بي الثابت (انسخه من موقع Playit)")
    if not secret:
        network_info["status"] = "error"
        network_info["ip"] = "مفقود PLAYIT_SECRET"
        server_logs.append("[Playit] ❌ خطأ: لم يتم العثور على PLAYIT_SECRET!")
        return
    env = os.environ.copy()
    env["HOME"] = DATA_DIR
    server_logs.append("[Playit] 🔄 جاري بدء الاتصال بخوادم Playit...")
    try:
        playit_process = subprocess.Popen(
            ["playit", "--secret", secret.strip()],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, bufsize=1, env=env
        )
        network_info["status"] = "connected"
        network_info["ip"] = static_ip
        for line in playit_process.stdout:
            clean_line = ansi_escape.sub('', line.strip())
            if not clean_line: continue
            safe_line = html.escape(clean_line)
            if "error" in clean_line.lower() or "invalid" in clean_line.lower() or "fail" in clean_line.lower():
                server_logs.append(f"[Playit] ❌ {safe_line}")
            elif "tunnel" in clean_line.lower() or "registered" in clean_line.lower() or "connected" in clean_line.lower():
                server_logs.append(f"[Playit] 🌐 {safe_line}")
    except Exception as e:
        server_logs.append(f"[Playit] ❌ انهيار في أداة الشبكة: {html.escape(str(e))}")
def start_minecraft():
    global mc_process, online_players
    if mc_process and mc_process.poll() is None: return
    setup_environment()
    online_players.clear()
    mods_dir = os.path.join(DATA_DIR, "mods")
    config_dir = os.path.join(DATA_DIR, "config")
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
    server_logs.append("[Minecraft] 🚀 جاري إطلاق السيرفر...")
    try:
        mc_process = subprocess.Popen(
            java_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, text=True, bufsize=1, cwd=APP_DIR
        )
        for line in mc_process.stdout:
            clean_line = ansi_escape.sub('', line.strip())
            if not clean_line: continue
            safe_line = html.escape(clean_line)
            server_logs.append(safe_line)
            join_match = re.search(r': ([a-zA-Z0-9_]+) joined the game', clean_line)
            if join_match: online_players.add(html.escape(join_match.group(1)))
            leave_match = re.search(r': ([a-zA-Z0-9_]+) left the game', clean_line)
            if leave_match and html.escape(leave_match.group(1)) in online_players:
                online_players.remove(html.escape(leave_match.group(1)))
        server_logs.append("[Minecraft] 🛑 توقف السيرفر.")
    except Exception as e:
        server_logs.append(f"[Minecraft] ❌ فشل في تشغيل الجافا: {html.escape(str(e))}")
    finally:
        online_players.clear()
threading.Thread(target=start_playit, daemon=True).start()
threading.Thread(target=start_minecraft, daemon=True).start()
# ==========================================
# 4. مسارات الويب (API & Routes)
# ==========================================
@app.before_request
def check_auth():
    if request.path.startswith('/api/') and not session.get('logged_in'): abort(401)
    if request.path.startswith('/map/') and not session.get('logged_in'): abort(401)
@app.route('/')
def index():
    if not session.get('logged_in'): return render_template_string(LOGIN_HTML)
    return render_template_string(DASHBOARD_HTML)
@app.route('/login', methods=['POST'])
def login():
    ip = request.remote_addr
    current_time = time.time()
    if ip in failed_logins:
        attempts, lockout_time = failed_logins[ip]
        if current_time < lockout_time:
            return f"تم حظر عنوان IP الخاص بك مؤقتاً لدواعي أمنية. حاول بعد {int((lockout_time - current_time)/60)} دقيقة.", 429
        elif current_time >= lockout_time and attempts >= MAX_ATTEMPTS:
            failed_logins.pop(ip, None)
    if request.form.get('password') == PASSWORD:
        session.permanent = True
        session['logged_in'] = True
        failed_logins.pop(ip, None)
        return redirect('/')
    else:
        attempts, _ = failed_logins.get(ip, (0, 0))
        attempts += 1
        lockout = current_time + LOCKOUT_TIME if attempts >= MAX_ATTEMPTS else 0
        failed_logins[ip] = (attempts, lockout)
        return render_template_string(LOGIN_HTML, error="كلمة المرور غير صحيحة!")
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
# 🗺️ الوكيل العكسي للخريطة المباشرة (Live Map Reverse Proxy)
@app.route('/map/', defaults={'subpath': ''}, methods=['GET', 'POST'])
@app.route('/map/<path:subpath>', methods=['GET', 'POST'])
def map_proxy(subpath):
    if not session.get('logged_in'): return "Unauthorized", 401
    # افتراضياً Dynmap يعمل على بورت 8123
    target_url = f"http://127.0.0.1:8123/{subpath}"
    try:
        if request.method == 'POST':
            req = requests.post(target_url, data=request.get_data(), headers={k:v for k,v in request.headers if k.lower() != 'host'}, stream=True, timeout=5)
        else:
            req = requests.get(target_url, params=request.args, headers={k:v for k,v in request.headers if k.lower() != 'host'}, stream=True, timeout=5)

        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in req.headers.items() if name.lower() not in excluded_headers]
        return Response(req.iter_content(chunk_size=10*1024), req.status_code, headers)
    except Exception as e:
        return f"<div style='color:#94a3b8; text-align:center; padding:50px; font-family:sans-serif;'><h3>الخريطة غير متصلة 🔴</h3><p>تأكد من رفع مود <b>Dynmap</b> إلى مجلد المودات وتشغيل السيرفر.</p><p style='font-size:12px; color:#ef4444;'>الخطأ التقني: {e}</p></div>", 502
@app.route('/api/status')
def status():
    is_running = mc_process and mc_process.poll() is None
    return jsonify({
        "cpu": psutil.cpu_percent(),
        "ram": psutil.virtual_memory().percent,
        "status": "شغال 🟢" if is_running else "متوقف 🔴",
        "logs": list(server_logs),
        "network": network_info,
        "players": list(online_players)
    })
@app.route('/api/action', methods=['POST'])
def action():
    act = request.form.get('action')
    global mc_process
    if act == "stop" and mc_process and mc_process.poll() is None:
        mc_process.stdin.write("stop\n"); mc_process.stdin.flush()
        server_logs.append("[النظام] ⏳ جاري حفظ العالم وإيقاف السيرفر بأمان...")
    elif act == "kill" and mc_process:
        mc_process.kill()
        server_logs.append("[النظام] 💀 تم قتل العملية إجبارياً!")
    elif act == "start":
        threading.Thread(target=start_minecraft, daemon=True).start()
    return "OK"
@app.route('/api/command', methods=['POST'])
def send_command():
    if not session.get('logged_in'): return "Unauthorized", 401
    cmd = request.form.get('cmd')

    # 💥 الأمر السري لمسح العالم
    if cmd.strip() == "!resetworld":
        import shutil
        shutil.rmtree(os.path.join(DATA_DIR, "world"), ignore_errors=True)
        server_logs.append("[النظام] 💥 تم فرمتة العالم القديم بنجاح! أوقف السيرفر وشغله من جديد لتوليد عالم بالسيد الجديد.")
        return "OK"
    if mc_process and mc_process.poll() is None and cmd.strip():
        mc_process.stdin.write(cmd + "\n"); mc_process.stdin.flush()
        server_logs.append(f"[أنت] > {html.escape(cmd)}")
    return "OK"
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
def handle_backup():
    backup_dir = os.path.join(DATA_DIR, "backups")
    if request.method == 'POST':
        def make_backup():
            server_logs.append("[النظام] ⏳ جاري ضغط العالم...")
            timestamp = time.strftime('%Y%m%d-%H%M%S')
            shutil.make_archive(os.path.join(backup_dir, f"world_backup_{timestamp}"), 'zip', os.path.join(DATA_DIR, "world"))
            server_logs.append("[النظام] ✅ اكتملت النسخة الاحتياطية!")
        threading.Thread(target=make_backup, daemon=True).start()
        return "Started"
    return jsonify([f for f in os.listdir(backup_dir) if f.endswith('.zip')] if os.path.exists(backup_dir) else [])
@app.route('/api/backup/download/<filename>')
def download_backup(filename):
    safe_name = secure_filename(filename)
    return send_from_directory(os.path.join(DATA_DIR, "backups"), safe_name, as_attachment=True)
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
    return jsonify(props)
@app.route('/api/files', methods=['GET', 'POST'])
def file_manager():
    if request.method == 'POST':
        action = request.form.get('action')
        target = request.form.get('target')
        target_path = os.path.realpath(os.path.join(DATA_DIR, target))
        safe_dir = os.path.realpath(DATA_DIR)
        if not target_path.startswith(safe_dir): return "Access Denied", 403
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
    crash_dir = os.path.join(APP_DIR, "crash-reports")
    if not os.path.exists(crash_dir): return "لا توجد كراشات."
    crashes = sorted([f for f in os.listdir(crash_dir) if f.endswith('.txt')], reverse=True)
    if not crashes: return "السيرفر مستقر، لا توجد تقارير كراش."
    with open(os.path.join(crash_dir, crashes[0]), 'r') as f: return html.escape(f.read())
# ==========================================
# 5. واجهات المستخدم (HTML/CSS/JS)
# ==========================================
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول | لوحة التحكم</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background: radial-gradient(circle at top, #0f172a, #020617); color: #f8fafc; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-container { background: rgba(30, 41, 59, 0.8); backdrop-filter: blur(15px); padding: 40px; border-radius: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.6); text-align: center; width: 90%; max-width: 400px; border: 1px solid rgba(255,255,255,0.05); }
        h2 { margin-top: 0; color: #38bdf8; font-size: 28px; margin-bottom: 30px; text-shadow: 0 2px 15px rgba(56, 189, 248, 0.4); }
        input { width: 100%; padding: 15px; margin-bottom: 20px; border-radius: 10px; border: 1px solid #334155; background: rgba(15, 23, 42, 0.9); color: white; text-align: center; font-size: 18px; outline: none; transition: 0.3s; }
        input:focus { border-color: #38bdf8; box-shadow: 0 0 15px rgba(56, 189, 248, 0.3); }
        button { width: 100%; padding: 15px; background: linear-gradient(135deg, #0ea5e9, #2563eb); color: white; border: none; border-radius: 10px; cursor: pointer; font-size: 18px; font-weight: bold; transition: 0.3s; box-shadow: 0 4px 15px rgba(14, 165, 233, 0.4); }
        button:hover { transform: translateY(-3px); box-shadow: 0 8px 25px rgba(14, 165, 233, 0.6); }
        .error-msg { color: #ef4444; margin-bottom: 15px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="login-container">
        <h2>🎮 لوحة تحكم السيرفر</h2>
        {% if error %}<div class="error-msg">{{ error }}</div>{% endif %}
        <form action="/login" method="POST">
            <input type="password" name="password" placeholder="أدخل الرمز السري..." required autofocus>
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
    <title>لوحة تحكم السيرفر | Ultimate Edition</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }
        .container { max-width: 1300px; margin: 0 auto; }
        #toast-container { position: fixed; bottom: 20px; left: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 10px; }
        .toast { background: #1e293b; color: white; padding: 15px 25px; border-radius: 8px; border-right: 4px solid #38bdf8; box-shadow: 0 4px 15px rgba(0,0,0,0.3); animation: slideIn 0.3s ease-out forwards; font-weight: bold; }
        @keyframes slideIn { from { transform: translateX(-100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        @keyframes fadeOut { from { opacity: 1; } to { opacity: 0; } }

        .header { display: flex; justify-content: space-between; align-items: center; background: linear-gradient(145deg, #1e293b, #0f172a); padding: 20px; border-radius: 16px; border: 1px solid #334155; margin-bottom: 20px; flex-wrap: wrap; gap: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
        .header h2 { margin: 0; color: #38bdf8; display: flex; align-items: center; gap: 10px; text-shadow: 0 2px 10px rgba(56, 189, 248, 0.2); }
        .network-box { display: flex; align-items: center; gap: 10px; background: rgba(15, 23, 42, 0.6); padding: 8px 15px; border-radius: 10px; border: 1px solid #334155; }
        .ip-badge { font-weight: bold; font-size: 18px; letter-spacing: 1px; }
        .ip-connected { color: #34d399; }
        .ip-error { color: #ef4444; }
        .btn-copy { background: #334155; color: white; border: none; padding: 8px 12px; border-radius: 6px; cursor: pointer; transition: 0.3s; font-size: 14px; }
        .btn-copy:hover { background: #475569; }
        .btn-logout { background: #ef4444; color: white; padding: 10px 20px; text-decoration: none; border-radius: 8px; font-weight: bold; transition: 0.3s; }
        .btn-logout:hover { background: #dc2626; }

        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; text-align: center; transition: transform 0.3s; }
        .stat-card:hover { transform: translateY(-5px); }
        .stat-title { color: #94a3b8; font-size: 14px; margin-bottom: 10px; text-transform: uppercase; }
        .stat-value { font-size: 26px; font-weight: bold; color: #f8fafc; }
        .status-online { color: #34d399; text-shadow: 0 0 10px rgba(52, 211, 153, 0.3); }
        .status-offline { color: #ef4444; }

        .tabs-nav { display: flex; gap: 10px; margin-bottom: 20px; overflow-x: auto; padding-bottom: 5px; }
        .tab-btn { background: #1e293b; color: #94a3b8; border: 1px solid #334155; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: bold; white-space: nowrap; transition: 0.3s; }
        .tab-btn:hover { background: #334155; color: white; }
        .tab-btn.active { background: #0ea5e9; color: white; border-color: #0ea5e9; box-shadow: 0 4px 15px rgba(14, 165, 233, 0.3); }
        .tab-content { display: none; background: #1e293b; padding: 25px; border-radius: 12px; border: 1px solid #334155; animation: fadeIn 0.3s; }
        .tab-content.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

        .console-wrapper { background: #020617; border-radius: 8px; border: 1px solid #334155; overflow: hidden; }
        .console-output { padding: 15px; height: 50vh; overflow-y: auto; font-family: 'Consolas', monospace; font-size: 14px; color: #a3e635; direction: ltr; text-align: left; line-height: 1.5; }
        .console-input-area { display: flex; border-top: 1px solid #334155; }
        .console-input { flex: 1; background: transparent; border: none; padding: 15px; color: white; font-family: monospace; font-size: 15px; outline: none; }
        .console-btn { background: #0ea5e9; color: white; border: none; padding: 0 25px; cursor: pointer; font-weight: bold; transition: 0.3s; }
        .console-btn:hover { background: #0284c7; }

        .action-bar { display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; }
        .btn { padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; color: white; transition: 0.3s; display: inline-flex; align-items: center; gap: 8px; }
        .btn-green { background: #10b981; } .btn-green:hover { background: #059669; }
        .btn-red { background: #ef4444; } .btn-red:hover { background: #dc2626; }
        .btn-blue { background: #3b82f6; } .btn-blue:hover { background: #2563eb; }
        .btn-orange { background: #f59e0b; } .btn-orange:hover { background: #d97706; }

        .list-item { display: flex; justify-content: space-between; align-items: center; background: #0f172a; padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #334155; transition: 0.2s; }
        .list-item:hover { border-color: #475569; }
        .list-item-title { font-weight: bold; font-size: 16px; }
        .list-actions { display: flex; gap: 8px; }

        /* تصميم شبكة الإعدادات الاحترافية */
        .config-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; }
        .config-row { display: flex; flex-direction: column; background: #0f172a; padding: 15px; border-radius: 8px; border: 1px solid #334155; }
        .config-row span { margin-bottom: 8px; font-weight: bold; color: #e2e8f0; font-size: 14px; }
        .config-row select, .config-row input { width: 100%; background: #1e293b; color: white; border: 1px solid #475569; padding: 10px; border-radius: 6px; outline: none; font-weight: bold; transition: 0.3s; }
        .config-row input:focus, .config-row select:focus { border-color: #38bdf8; box-shadow: 0 0 8px rgba(56, 189, 248, 0.3); }

        .file-viewer { background: #020617; color: #e2e8f0; padding: 15px; border-radius: 8px; font-family: monospace; white-space: pre-wrap; max-height: 400px; overflow-y: auto; direction: ltr; text-align: left; border: 1px solid #334155; margin-top: 15px; display: none;}

        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #475569; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #64748b; }
    </style>
</head>
<body>
    <div id="toast-container"></div>
    <div class="container">
        <div class="header">
            <h2><span style="font-size: 28px;">🎮</span> لوحة تحكم السيرفر</h2>
            <div id="network-area" class="network-box">
                <span class="ip-badge ip-connected" id="ip-display">جاري الاتصال...</span>
                <button class="btn-copy" onclick="copyIP()">📋 نسخ</button>
            </div>
            <a href="/logout" class="btn-logout">تسجيل خروج</a>
        </div>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-title">حالة السيرفر</div>
                <div class="stat-value" id="status-text">جاري التحميل...</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">استهلاك المعالج (CPU)</div>
                <div class="stat-value" id="cpu-text">0%</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">استهلاك الرام (RAM)</div>
                <div class="stat-value" id="ram-text">0%</div>
            </div>
            <div class="stat-card">
                <div class="stat-title">اللاعبين المتصلين</div>
                <div class="stat-value" id="players-count">0</div>
            </div>
        </div>
        <div class="tabs-nav">
            <button class="tab-btn active" onclick="openTab('console')">الكونسول والتحكم</button>
            <button class="tab-btn" onclick="openTab('livemap')">🗺️ الخريطة المباشرة</button>
            <button class="tab-btn" onclick="openTab('players')">إدارة اللاعبين</button>
            <button class="tab-btn" onclick="openTab('mods'); loadMods();">مدير المودات</button>
            <button class="tab-btn" onclick="openTab('files'); loadFiles();">مدير الملفات</button>
            <button class="tab-btn" onclick="openTab('backups'); loadBackups();">النسخ الاحتياطي</button>
            <button class="tab-btn" onclick="openTab('settings'); loadConfig();">إعدادات السيرفر</button>
            <button class="tab-btn" onclick="openTab('crashes'); loadCrash();">الكراشات</button>
        </div>
        <!-- 1. Console Tab -->
        <div id="console" class="tab-content active">
            <div class="action-bar">
                <button class="btn btn-green" onclick="sendAction('start')">▶ تشغيل السيرفر</button>
                <button class="btn btn-orange" onclick="sendAction('stop')">⏹ إيقاف آمن (حفظ)</button>
                <button class="btn btn-red" onclick="sendAction('kill')">💀 إيقاف إجباري</button>
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
        <div id="livemap" class="tab-content">
            <h3 style="margin-top:0; color:#38bdf8;">🗺️ الخريطة المباشرة (Live Map)</h3>
            <p style="color: #94a3b8; font-size: 14px;">لعرض الخريطة، يجب أن تكون قد قمت برفع مود <b>Dynmap</b> إلى مجلد المودات وتشغيل السيرفر.</p>
            <div class="action-bar" style="margin-bottom: 15px;">
                <button class="btn btn-blue" onclick="document.getElementById('map-frame').src = '/map/';">🔄 تحديث الخريطة</button>
                <a href="/map/" target="_blank" class="btn btn-green" style="text-decoration:none;">🌍 فتح في نافذة جديدة</a>
            </div>
            <div style="border: 1px solid #334155; border-radius: 8px; overflow: hidden; height: 60vh;">
                <iframe id="map-frame" src="/map/" style="width: 100%; height: 100%; border: none; background: #020617;"></iframe>
            </div>
        </div>
        <!-- 3. Players Tab -->
        <div id="players" class="tab-content">
            <h3 style="margin-top:0; color:#38bdf8;">👥 اللاعبين المتصلين حالياً</h3>
            <div id="players-list"><p style="color: #94a3b8;">جاري التحميل...</p></div>
        </div>
        <!-- 4. Mods Tab -->
        <div id="mods" class="tab-content">
            <h3 style="margin-top:0; color:#38bdf8;">📦 إدارة المودات (Mods)</h3>
            <div class="action-bar" style="background: #0f172a; padding: 15px; border-radius: 8px; border: 1px dashed #475569;">
                <input type="file" id="mod-file" accept=".jar" style="color: white;">
                <button class="btn btn-green" onclick="uploadMod()">⬆️ رفع المود للسيرفر</button>
            </div>
            <div id="mods-list" style="margin-top: 20px;">جاري التحميل...</div>
        </div>
        <!-- 5. File Manager Tab -->
        <div id="files" class="tab-content">
            <h3 style="margin-top:0; color:#38bdf8;">📁 مدير ملفات السيرفر (JSON & Logs)</h3>
            <p style="color: #94a3b8; font-size: 14px;">يمكنك قراءة وحذف ملفات الإعدادات والتقارير من هنا.</p>
            <div id="files-list">جاري التحميل...</div>
            <div id="file-viewer" class="file-viewer"></div>
        </div>
        <!-- 6. Backups Tab -->
        <div id="backups" class="tab-content">
            <h3 style="margin-top:0; color:#38bdf8;">💾 النسخ الاحتياطي للعالم (World)</h3>
            <button class="btn btn-blue" onclick="createBackup()" style="width: 100%; justify-content: center; padding: 15px; font-size: 16px; margin-bottom: 20px;">
                📦 إنشاء نسخة احتياطية جديدة الآن
            </button>
            <div id="backups-list">جاري التحميل...</div>
        </div>
        <!-- 7. Settings Tab (The Ultimate Config) -->
        <div id="settings" class="tab-content">
            <h3 style="margin-top:0; color:#38bdf8;">⚙️ إعدادات السيرفر الشاملة (server.properties)</h3>
            <p style="color: #f59e0b; font-size: 14px; margin-bottom: 20px;">⚠️ ملاحظة: يجب إيقاف السيرفر وتشغيله مرة أخرى لتطبيق أي تعديلات.</p>
            <div id="config-form" class="config-grid">جاري التحميل...</div>
            <button class="btn btn-green" onclick="saveConfig()" style="width: 100%; justify-content: center; padding: 15px; font-size: 18px; margin-top: 20px; box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);">
                💾 حفظ جميع الإعدادات
            </button>
        </div>
        <!-- 8. Crashes Tab -->
        <div id="crashes" class="tab-content">
            <h3 style="margin-top:0; color:#ef4444;">⚠️ آخر تقرير كراش (Crash Report)</h3>
            <div class="console-wrapper">
                <div class="console-output" id="crash-box" style="color: #fca5a5;">جاري التحميل...</div>
            </div>
        </div>
    </div>
    <script>
        // قائمة الإعدادات الشاملة
        const configFields = [
            {key: 'motd', label: 'رسالة الترحيب (MOTD)', type: 'text'},
            {key: 'max-players', label: 'أقصى عدد لاعبين', type: 'number'},
            {key: 'difficulty', label: 'مستوى الصعوبة', type: 'select', options: ['peaceful', 'easy', 'normal', 'hard']},
            {key: 'pvp', label: 'القتال بين اللاعبين (PVP)', type: 'select', options: ['true', 'false']},
            {key: 'hardcore', label: 'وضع الهاردكور (موتة وحدة)', type: 'select', options: ['true', 'false']},
            {key: 'view-distance', label: 'مسافة الرؤية (Chunks)', type: 'number'},
            {key: 'simulation-distance', label: 'مسافة المحاكاة', type: 'number'},
            {key: 'level-seed', label: 'سيد العالم (Seed)', type: 'text'},
            {key: 'allow-nether', label: 'تفعيل النذر (Nether)', type: 'select', options: ['true', 'false']},
            {key: 'allow-flight', label: 'السماح بالطيران (يمنع الطرد)', type: 'select', options: ['true', 'false']},
            {key: 'enable-command-block', label: 'تفعيل الكوماند بلوك', type: 'select', options: ['true', 'false']},
            {key: 'spawn-protection', label: 'حماية نقطة البداية (بلوكات)', type: 'number'},
            {key: 'white-list', label: 'تفعيل القائمة البيضاء', type: 'select', options: ['true', 'false']},
            {key: 'force-gamemode', label: 'إجبار وضع اللعب عند الدخول', type: 'select', options: ['true', 'false']},
            {key: 'max-build-height', label: 'أقصى ارتفاع للبناء', type: 'number'},
            {key: 'enforce-secure-profile', label: 'تشفير الشات (يفضل False للمكرك)', type: 'select', options: ['true', 'false']},
            {key: 'spawn-monsters', label: 'ترسبن الوحوش', type: 'select', options: ['true', 'false']},
            {key: 'spawn-animals', label: 'ترسبن الحيوانات', type: 'select', options: ['true', 'false']},
            {key: 'spawn-npcs', label: 'ترسبن القرويين (NPCs)', type: 'select', options: ['true', 'false']},
            {key: 'generate-structures', label: 'توليد القرى والمعابد', type: 'select', options: ['true', 'false']},
            {key: 'entity-broadcast-range-percentage', label: 'مسافة ظهور الكيانات (%)', type: 'number'},
            {key: 'sync-chunk-writes', label: 'مزامنة حفظ التشانكات', type: 'select', options: ['true', 'false']},
            {key: 'rate-limit', label: 'حد الرسايل (Rate Limit)', type: 'number'}
        ];
        function showToast(message, type = 'success') {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            toast.className = 'toast';
            toast.style.borderRightColor = type === 'success' ? '#34d399' : (type === 'error' ? '#ef4444' : '#38bdf8');
            toast.innerText = message;
            container.appendChild(toast);
            setTimeout(() => {
                toast.style.animation = 'fadeOut 0.3s ease-out forwards';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
        function copyIP() {
            const ipText = document.getElementById('ip-display').innerText;
            navigator.clipboard.writeText(ipText).then(() => {
                showToast('✅ تم نسخ الآي بي بنجاح!');
            });
        }
        let autoScroll = true;
        let consoleBox = document.getElementById('console-box');
        consoleBox.addEventListener('scroll', () => {
            autoScroll = (consoleBox.scrollHeight - consoleBox.scrollTop - consoleBox.clientHeight < 50);
        });
        function openTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
            document.getElementById(tabName).classList.add('active');
            event.currentTarget.classList.add('active');
        }
        function updateStatus() {
            fetch('/api/status').then(res => res.json()).then(data => {
                document.getElementById('cpu-text').innerText = data.cpu + '%';
                document.getElementById('ram-text').innerText = data.ram + '%';
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
                let p_html = data.players.length === 0 ? '<p style="color: #94a3b8;">لا يوجد لاعبين متصلين حالياً.</p>' : '';
                data.players.forEach(p => {
                    p_html += `
                    <div class="list-item">
                        <div class="list-item-title">👤 ${p}</div>
                        <div class="list-actions">
                            <button class="btn btn-blue" onclick="execCmd('op ${p}')">إعطاء أدمن</button>
                            <button class="btn btn-green" onclick="execCmd('gamemode creative ${p}')">إبداع</button>
                            <button class="btn btn-orange" onclick="execCmd('gamemode survival ${p}')">نجاة</button>
                            <button class="btn btn-red" onclick="execCmd('kick ${p}')">طرد</button>
                        </div>
                    </div>`;
                });
                document.getElementById('players-list').innerHTML = p_html;
            });
        }
        setInterval(updateStatus, 2000);
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
            fetch('/api/action', { method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: 'action=' + act }).then(() => {
                showToast(act === 'start' ? '🚀 جاري التشغيل...' : '🛑 تم إرسال أمر الإيقاف', 'info');
            });
        }
        function loadMods() {
            fetch('/api/mods').then(res => res.json()).then(mods => {
                let html = mods.length === 0 ? '<p style="color: #94a3b8;">لا توجد مودات مثبتة.</p>' : '';
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
                showToast('✅ تم رفع المود بنجاح!');
                fileInput.value = '';
                loadMods();
                btn.innerText = originalText;
                btn.disabled = false;
            });
        }
        function deleteMod(modName) {
            if(!confirm('هل أنت متأكد من حذف المود: ' + modName + '؟')) return;
            fetch('/api/mods', { method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: 'delete=' + encodeURIComponent(modName) }).then(() => {
                showToast('🗑️ تم الحذف بنجاح!');
                loadMods();
            });
        }
        function loadFiles() {
            fetch('/api/files').then(res => res.json()).then(files => {
                let html = files.length === 0 ? '<p style="color: #94a3b8;">لا توجد ملفات.</p>' : '';
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
                showToast('🗑️ تم الحذف بنجاح!');
                document.getElementById('file-viewer').style.display = 'none';
                loadFiles();
            });
        }
        function loadBackups() {
            fetch('/api/backup').then(res => res.json()).then(backups => {
                let html = backups.length === 0 ? '<p style="color: #94a3b8;">لا توجد نسخ احتياطية.</p>' : '';
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
                showToast('⏳ بدأ إنشاء النسخة الاحتياطية...', 'info');
                setTimeout(loadBackups, 5000);
            });
        }
        function loadConfig() {
            fetch('/api/config').then(res => res.json()).then(data => {
                let html = '';
                configFields.forEach(f => {
                    let val = data[f.key] || '';
                    html += `<div class="config-row"><span>${f.label}</span>`;
                    if(f.type === 'select') {
                        html += `<select id="cfg-${f.key}">`;
                        f.options.forEach(opt => { html += `<option value="${opt}" ${val===opt?'selected':''}>${opt}</option>`; });
                        html += `</select></div>`;
                    } else {
                        html += `<input type="${f.type}" id="cfg-${f.key}" value="${val}"></div>`;
                    }
                });
                document.getElementById('config-form').innerHTML = html;
            });
        }
        function saveConfig() {
            let data = {};
            configFields.forEach(f => {
                let el = document.getElementById('cfg-' + f.key);
                if(el && el.value.trim() !== '') {
                    data[f.key] = el.value;
                }
            });
            fetch('/api/config', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) }).then(() => {
                showToast('💾 تم حفظ الإعدادات! أعد تشغيل السيرفر لتطبيقها.');
            });
        }
        function loadCrash() {
            fetch('/api/crash').then(res => res.text()).then(text => {
                document.getElementById('crash-box').innerText = text;
            });
        }
    </script>
</body>
</html>
"""
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)
