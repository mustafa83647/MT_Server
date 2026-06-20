import os
import sys
import time
import threading
import subprocess
import re
import shutil
import psutil
from collections import deque
from flask import Flask, render_template_string, request, redirect, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename
# ==========================================
# 1. الإعدادات الأساسية (Configuration)
# ==========================================
app = Flask(__name__)
app.secret_key = "super_secret_key_minecraft_god_tier"
PASSWORD = "2938"
DATA_DIR = "/data/minecraft_data"
APP_DIR = "/app/minecraft"
# متغيرات التحكم (Thread-Safe)
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
    """دالة ذكية لربط الملفات بالبوكت بدون أخطاء"""
    try:
        if os.path.islink(dst) or os.path.isfile(dst):
            os.remove(dst)
        elif os.path.isdir(dst):
            shutil.rmtree(dst)
        os.symlink(src, dst)
    except Exception as e:
        server_logs.append(f"[النظام] ⚠️ تحذير أثناء ربط {os.path.basename(dst)}: {e}")
def setup_environment():
    """تهيئة بيئة السيرفر بالكامل"""
    server_logs.append("[النظام] 🛠️ جاري تهيئة بيئة السيرفر (Enterprise Mode)...")
    # إنشاء المجلدات الأساسية في البوكت
    os.makedirs(os.path.join(DATA_DIR, "world"), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "mods"), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "config"), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "backups"), exist_ok=True)

    os.makedirs(APP_DIR, exist_ok=True)
    # ربط مجلد العالم فقط (لأن ماين كرافت تتعامل معه بدون مشاكل)
    force_symlink(os.path.join(DATA_DIR, "world"), os.path.join(APP_DIR, "world"))
    # إنشاء وربط الملفات الأساسية
    files_to_link = ['server.properties', 'ops.json', 'banned-players.json', 'banned-ips.json', 'whitelist.json', 'usercache.json']
    for f in files_to_link:
        file_path = os.path.join(DATA_DIR, f)
        if not os.path.exists(file_path):
            with open(file_path, 'w') as file:
                if f == 'server.properties':
                    file.write("online-mode=false\n")
                elif f.endswith('.json'):
                    file.write("[]\n")
        force_symlink(file_path, os.path.join(APP_DIR, f))
    # الموافقة على شروط اللعبة
    with open(os.path.join(APP_DIR, "eula.txt"), 'w') as f:
        f.write("eula=true\n")
    # تحميل محرك Fabric إذا لم يكن موجوداً
    fabric_jar = os.path.join(APP_DIR, "fabric-server-launch.jar")
    if not os.path.exists(fabric_jar):
        server_logs.append("[النظام] ⬇️ جاري تحميل محرك Fabric (1.20.4)...")
        installer_path = os.path.join(APP_DIR, "fabric-installer.jar")
        subprocess.run(["wget", "-q", "-O", installer_path, "https://maven.fabricmc.net/net/fabricmc/fabric-installer/1.0.1/fabric-installer-1.0.1.jar"])
        subprocess.run(["java", "-jar", "fabric-installer.jar", "server", "-mcversion", "1.20.4", "-loader", "0.15.7", "-downloadMinecraft"], cwd=APP_DIR)
        if os.path.exists(installer_path):
            os.remove(installer_path)
    server_logs.append("[النظام] ✅ تمت التهيئة بنجاح. البيئة جاهزة.")
# ==========================================
# 3. إدارة العمليات (Playit & Minecraft)
# ==========================================
def start_playit():
    """تشغيل Playit مع مراقبة دقيقة جداً للمخرجات"""
    global playit_process, network_info
    secret = os.environ.get("PLAYIT_SECRET")
    static_ip = os.environ.get("PLAYIT_IP", "الآي بي الثابت (انسخه من موقع Playit)")
    if not secret:
        network_info["status"] = "error"
        network_info["ip"] = "مفقود PLAYIT_SECRET"
        server_logs.append("[Playit] ❌ خطأ قاتل: لم يتم العثور على PLAYIT_SECRET في إعدادات السبيس!")
        return

    secret = secret.strip()
    env = os.environ.copy()
    env["HOME"] = DATA_DIR
    server_logs.append("[Playit] 🔄 جاري بدء الاتصال بخوادم Playit العالمية...")
    try:
        playit_process = subprocess.Popen(
            ["playit", "--secret", secret],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env
        )
        network_info["status"] = "connected"
        network_info["ip"] = static_ip
        for line in playit_process.stdout:
            clean_line = ansi_escape.sub('', line.strip())
            if not clean_line: continue
            if "error" in clean_line.lower() or "invalid" in clean_line.lower() or "fail" in clean_line.lower():
                server_logs.append(f"[Playit] ❌ {clean_line}")
            elif "tunnel" in clean_line.lower() or "registered" in clean_line.lower() or "connected" in clean_line.lower():
                server_logs.append(f"[Playit] 🌐 {clean_line}")
    except Exception as e:
        server_logs.append(f"[Playit] ❌ انهيار في أداة الشبكة: {e}")
def start_minecraft():
    """تشغيل ماين كرافت مع حل مشكلة المودات وأكواد الأداء"""
    global mc_process, online_players
    if mc_process and mc_process.poll() is None:
        return

    setup_environment()
    online_players.clear()
    # الحل السحري: توجيه Fabric مباشرة للبوكت بدون اختصارات
    mods_dir = os.path.join(DATA_DIR, "mods")
    config_dir = os.path.join(DATA_DIR, "config")
    java_args = [
        "java",
        "-Xms2G",
        "-Xmx6G",
        f"-Dfabric.modsDir={mods_dir}",
        f"-Dfabric.configDir={config_dir}",
        "-XX:+UseG1GC",
        "-XX:+ParallelRefProcEnabled",
        "-XX:MaxGCPauseMillis=200",
        "-XX:+UnlockExperimentalVMOptions",
        "-XX:+DisableExplicitGC",
        "-XX:+AlwaysPreTouch",
        "-XX:G1NewSizePercent=30",
        "-XX:G1MaxNewSizePercent=40",
        "-XX:G1HeapRegionSize=8M",
        "-XX:G1ReservePercent=20",
        "-XX:G1HeapWastePercent=5",
        "-XX:G1MixedGCCountTarget=4",
        "-XX:InitiatingHeapOccupancyPercent=15",
        "-XX:G1MixedGCLiveThresholdPercent=90",
        "-XX:G1RSetUpdatingPauseTimePercent=5",
        "-XX:SurvivorRatio=32",
        "-XX:+PerfDisableSharedMem",
        "-XX:MaxTenuringThreshold=1",
        "-jar", "fabric-server-launch.jar",
        "nogui"
    ]
    server_logs.append("[Minecraft] 🚀 جاري إطلاق السيرفر مع تحسينات الأداء (Aikar's Flags)...")
    try:
        mc_process = subprocess.Popen(
            java_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=APP_DIR
        )
        for line in mc_process.stdout:
            clean_line = ansi_escape.sub('', line.strip())
            if not clean_line: continue
            server_logs.append(clean_line)

            join_match = re.search(r': ([a-zA-Z0-9_]+) joined the game', clean_line)
            if join_match:
                online_players.add(join_match.group(1))

            leave_match = re.search(r': ([a-zA-Z0-9_]+) left the game', clean_line)
            if leave_match and leave_match.group(1) in online_players:
                online_players.remove(leave_match.group(1))
        server_logs.append("[Minecraft] 🛑 توقف السيرفر.")
    except Exception as e:
        server_logs.append(f"[Minecraft] ❌ فشل في تشغيل الجافا: {e}")
    finally:
        online_players.clear()
threading.Thread(target=start_playit, daemon=True).start()
threading.Thread(target=start_minecraft, daemon=True).start()
# ==========================================
# 4. مسارات الويب (API & Routes)
# ==========================================
@app.route('/')
def index():
    if not session.get('logged_in'): return render_template_string(LOGIN_HTML)
    return render_template_string(DASHBOARD_HTML)
@app.route('/login', methods=['POST'])
def login():
    if request.form.get('password') == PASSWORD: session['logged_in'] = True
    return redirect('/')
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
@app.route('/api/status')
def status():
    if not session.get('logged_in'): return "Unauthorized", 401
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
    if not session.get('logged_in'): return "Unauthorized", 401
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
    if mc_process and mc_process.poll() is None and cmd.strip():
        mc_process.stdin.write(cmd + "\n"); mc_process.stdin.flush()
        server_logs.append(f"[أنت] > {cmd}")
    return "OK"
@app.route('/api/mods', methods=['GET', 'POST'])
def handle_mods():
    if not session.get('logged_in'): return "Unauthorized", 401
    mods_path = os.path.join(DATA_DIR, "mods")
    if request.method == 'POST':
        if 'file' in request.files:
            file = request.files['file']
            if file.filename.endswith('.jar'): file.save(os.path.join(mods_path, secure_filename(file.filename)))
        elif 'delete' in request.form:
            try: os.remove(os.path.join(mods_path, request.form.get('delete')))
            except: pass
        return "OK"
    return jsonify([f for f in os.listdir(mods_path) if f.endswith('.jar')] if os.path.exists(mods_path) else [])
@app.route('/api/backup', methods=['GET', 'POST'])
def handle_backup():
    if not session.get('logged_in'): return "Unauthorized", 401
    backup_dir = os.path.join(DATA_DIR, "backups")
    if request.method == 'POST':
        def make_backup():
            server_logs.append("[النظام] ⏳ جاري ضغط العالم، قد يستغرق الأمر دقيقة...")
            timestamp = time.strftime('%Y%m%d-%H%M%S')
            shutil.make_archive(os.path.join(backup_dir, f"world_backup_{timestamp}"), 'zip', os.path.join(DATA_DIR, "world"))
            server_logs.append("[النظام] ✅ اكتملت النسخة الاحتياطية!")
        threading.Thread(target=make_backup, daemon=True).start()
        return "Started"
    return jsonify([f for f in os.listdir(backup_dir) if f.endswith('.zip')] if os.path.exists(backup_dir) else [])
@app.route('/api/backup/download/<filename>')
def download_backup(filename):
    if not session.get('logged_in'): return "Unauthorized", 401
    return send_from_directory(os.path.join(DATA_DIR, "backups"), filename, as_attachment=True)
@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if not session.get('logged_in'): return "Unauthorized", 401
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
    if not session.get('logged_in'): return "Unauthorized", 401
    if request.method == 'POST':
        action = request.form.get('action')
        target = request.form.get('target')
        target_path = os.path.join(DATA_DIR, target)
        if not os.path.abspath(target_path).startswith(DATA_DIR): return "Access Denied", 403
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
    if not session.get('logged_in'): return "Unauthorized", 401
    crash_dir = os.path.join(APP_DIR, "crash-reports")
    if not os.path.exists(crash_dir): return "لا توجد كراشات."
    crashes = sorted([f for f in os.listdir(crash_dir) if f.endswith('.txt')], reverse=True)
    if not crashes: return "السيرفر مستقر، لا توجد تقارير كراش."
    with open(os.path.join(crash_dir, crashes[0]), 'r') as f: return f.read()
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
    </style>
</head>
<body>
    <div class="login-container">
        <h2>🎮 لوحة تحكم السيرفر</h2>
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
    <title>لوحة تحكم السيرفر | Enterprise</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
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
        .config-row { display: flex; justify-content: space-between; align-items: center; background: #0f172a; padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #334155; }
        .config-row select, .config-row input { background: #1e293b; color: white; border: 1px solid #475569; padding: 8px 12px; border-radius: 6px; outline: none; font-weight: bold; }
        .config-row input:focus, .config-row select:focus { border-color: #38bdf8; }
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
        <!-- 2. Players Tab -->
        <div id="players" class="tab-content">
            <h3 style="margin-top:0; color:#38bdf8;">👥 اللاعبين المتصلين حالياً</h3>
            <div id="players-list"><p style="color: #94a3b8;">جاري التحميل...</p></div>
        </div>
        <!-- 3. Mods Tab -->
        <div id="mods" class="tab-content">
            <h3 style="margin-top:0; color:#38bdf8;">📦 إدارة المودات (Mods)</h3>
            <div class="action-bar" style="background: #0f172a; padding: 15px; border-radius: 8px; border: 1px dashed #475569;">
                <input type="file" id="mod-file" accept=".jar" style="color: white;">
                <button class="btn btn-green" onclick="uploadMod()">⬆️ رفع المود للسيرفر</button>
            </div>
            <div id="mods-list" style="margin-top: 20px;">جاري التحميل...</div>
        </div>
        <!-- 4. File Manager Tab -->
        <div id="files" class="tab-content">
            <h3 style="margin-top:0; color:#38bdf8;">📁 مدير ملفات السيرفر (JSON & Logs)</h3>
            <p style="color: #94a3b8; font-size: 14px;">يمكنك قراءة وحذف ملفات الإعدادات والتقارير من هنا.</p>
            <div id="files-list">جاري التحميل...</div>
            <div id="file-viewer" class="file-viewer"></div>
        </div>
        <!-- 5. Backups Tab -->
        <div id="backups" class="tab-content">
            <h3 style="margin-top:0; color:#38bdf8;">💾 النسخ الاحتياطي للعالم (World)</h3>
            <button class="btn btn-blue" onclick="createBackup()" style="width: 100%; justify-content: center; padding: 15px; font-size: 16px; margin-bottom: 20px;">
                📦 إنشاء نسخة احتياطية جديدة الآن
            </button>
            <div id="backups-list">جاري التحميل...</div>
        </div>
        <!-- 6. Settings Tab -->
        <div id="settings" class="tab-content">
            <h3 style="margin-top:0; color:#38bdf8;">⚙️ إعدادات السيرفر (server.properties)</h3>
            <p style="color: #f59e0b; font-size: 14px; margin-bottom: 20px;">⚠️ ملاحظة: يجب إيقاف السيرفر وتشغيله مرة أخرى لتطبيق أي تعديلات.</p>
            <div id="config-form">جاري التحميل...</div>
            <button class="btn btn-green" onclick="saveConfig()" style="width: 100%; justify-content: center; padding: 15px; font-size: 16px; margin-top: 20px;">
                💾 حفظ الإعدادات
            </button>
        </div>
        <!-- 7. Crashes Tab -->
        <div id="crashes" class="tab-content">
            <h3 style="margin-top:0; color:#ef4444;">⚠️ آخر تقرير كراش (Crash Report)</h3>
            <div class="console-wrapper">
                <div class="console-output" id="crash-box" style="color: #fca5a5;">جاري التحميل...</div>
            </div>
        </div>
    </div>
    <script>
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
                const fields = [
                    {key: 'max-players', label: 'أقصى عدد لاعبين', type: 'number'},
                    {key: 'difficulty', label: 'مستوى الصعوبة', type: 'select', options: ['peaceful', 'easy', 'normal', 'hard']},
                    {key: 'pvp', label: 'القتال بين اللاعبين (PVP)', type: 'select', options: ['true', 'false']},
                    {key: 'hardcore', label: 'وضع الهاردكور (موتة وحدة)', type: 'select', options: ['true', 'false']},
                    {key: 'view-distance', label: 'مسافة الرؤية (Chunks)', type: 'number'},
                    {key: 'simulation-distance', label: 'مسافة المحاكاة', type: 'number'}
                ];
                fields.forEach(f => {
                    let val = data[f.key] || '';
                    html += `<div class="config-row"><span style="font-weight:bold;">${f.label}</span>`;
                    if(f.type === 'select') {
                        html += `<select id="cfg-${f.key}">`;
                        f.options.forEach(opt => { html += `<option value="${opt}" ${val===opt?'selected':''}>${opt}</option>`; });
                        html += `</select></div>`;
                    } else {
                        html += `<input type="${f.type}" id="cfg-${f.key}" value="${val}" style="max-width: 150px; text-align:center;"></div>`;
                    }
                });
                document.getElementById('config-form').innerHTML = html;
            });
        }
        function saveConfig() {
            let data = {
                'max-players': document.getElementById('cfg-max-players').value,
                'difficulty': document.getElementById('cfg-difficulty').value,
                'pvp': document.getElementById('cfg-pvp').value,
                'hardcore': document.getElementById('cfg-hardcore').value,
                'view-distance': document.getElementById('cfg-view-distance').value,
                'simulation-distance': document.getElementById('cfg-simulation-distance').value
            };
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
