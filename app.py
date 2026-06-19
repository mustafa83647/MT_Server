from flask import Flask, render_template_string, request, redirect, session, jsonify, send_from_directory
import subprocess, threading, os, time, re, psutil, shutil
from werkzeug.utils import secure_filename
app = Flask(__name__)
app.secret_key = "super_secret_key_minecraft"
PASSWORD = "2938"
mc_process = None
server_logs = []
bore_ip = "جاري جلب الآي بي..."
online_players = set()
DATA_DIR = "/data/minecraft_data"
os.makedirs(os.path.join(DATA_DIR, "mods"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "backups"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "crash-reports"), exist_ok=True)
def fetch_bore_ip():
    global bore_ip
    while True:
        try:
            if os.path.exists("/app/bore.log"):
                with open("/app/bore.log", "r") as f:
                    match = re.search(r'bore\.pub:(\d+)', f.read())
                    if match:
                        new_ip = f"bore.pub:{match.group(1)}"
                        if bore_ip != new_ip:
                            bore_ip = new_ip
                            server_logs.append(f"[النظام] 🟢 تم التقاط الآي بي: {bore_ip}")
        except: pass
        time.sleep(5)
def run_server():
    global mc_process, server_logs, online_players
    if mc_process and mc_process.poll() is None: return
    server_logs.append("[النظام] 🚀 جاري تشغيل السيرفر...")
    online_players.clear()
    mc_process = subprocess.Popen(["bash", "start.sh"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd="/app")

    for line in mc_process.stdout:
        clean_line = line.strip()
        server_logs.append(clean_line)
        if len(server_logs) > 250: server_logs.pop(0)

        # صيد اللاعبين من اللوق
        join_match = re.search(r': ([a-zA-Z0-9_]+) joined the game', clean_line)
        if join_match: online_players.add(join_match.group(1))
        leave_match = re.search(r': ([a-zA-Z0-9_]+) left the game', clean_line)
        if leave_match and leave_match.group(1) in online_players: online_players.remove(leave_match.group(1))
threading.Thread(target=fetch_bore_ip, daemon=True).start()
threading.Thread(target=run_server, daemon=True).start()
@app.route('/')
def index():
    if not session.get('logged_in'): return render_template_string(LOGIN_HTML)
    return render_template_string(DASHBOARD_HTML, ip=bore_ip)
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
        "cpu": psutil.cpu_percent(), "ram": psutil.virtual_memory().percent,
        "status": "شغال 🟢" if is_running else "متوقف 🔴",
        "logs": server_logs, "ip": bore_ip, "players": list(online_players)
    })
@app.route('/api/action', methods=['POST'])
def action():
    if not session.get('logged_in'): return "Unauthorized", 401
    act = request.form.get('action')
    global mc_process
    if act == "stop" and mc_process and mc_process.poll() is None:
        mc_process.stdin.write("stop\n"); mc_process.stdin.flush()
    elif act == "kill" and mc_process: mc_process.kill()
    elif act == "start": threading.Thread(target=run_server, daemon=True).start()
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
        threading.Thread(target=lambda: shutil.make_archive(os.path.join(backup_dir, f"world_backup_{time.strftime('%Y%m%d-%H%M%S')}"), 'zip', os.path.join(DATA_DIR, "world")), daemon=True).start()
        return "Started"
    return jsonify([f for f in os.listdir(backup_dir) if f.endswith('.zip')] if os.path.exists(backup_dir) else [])
@app.route('/api/backup/download/<filename>')
def download_backup(filename):
    if not session.get('logged_in'): return "Unauthorized", 401
    return send_from_directory(os.path.join(DATA_DIR, "backups"), filename, as_attachment=True)
@app.route('/api/crash')
def get_crash():
    if not session.get('logged_in'): return "Unauthorized", 401
    crash_dir = os.path.join(DATA_DIR, "crash-reports")
    if not os.path.exists(crash_dir): return "لا توجد كراشات."
    crashes = sorted([f for f in os.listdir(crash_dir) if f.endswith('.txt')], reverse=True)
    if not crashes: return "السيرفر مستقر، لا توجد تقارير كراش."
    with open(os.path.join(crash_dir, crashes[0]), 'r') as f: return f.read()
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
# ================= واجهات HTML =================
LOGIN_HTML = """<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>تسجيل الدخول</title><style>body{background:#121212;color:#fff;font-family:Arial;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}.box{background:#1e1e1e;padding:40px;border-radius:10px;text-align:center;box-shadow:0 4px 15px rgba(0,0,0,0.5)}input{padding:10px;margin:10px 0;width:90%;border-radius:5px;border:none;text-align:center;font-size:18px}button{padding:10px 20px;background:#4CAF50;color:#fff;border:none;border-radius:5px;cursor:pointer;width:100%;font-size:16px}</style></head><body><div class="box"><h2>🔒 لوحة التحكم</h2><form action="/login" method="POST"><input type="password" name="password" placeholder="الرمز السري..." required autofocus><br><button type="submit">دخول</button></form></div></body></html>"""
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة تحكم السيرفر</title>
    <style>
        body { background: #121212; color: #e0e0e0; font-family: Arial; margin: 0; padding: 15px; }
        .header { display: flex; justify-content: space-between; background: #1e1e1e; padding: 15px; border-radius: 8px; align-items: center; flex-wrap: wrap; gap: 10px;}
        .stats { display: flex; gap: 10px; margin-top: 15px; flex-wrap: wrap;}
        .stat-box { background: #2d2d2d; padding: 15px; border-radius: 8px; flex: 1; text-align: center; font-weight: bold; min-width: 100px;}
        .tabs { margin-top: 20px; display: flex; gap: 5px; flex-wrap: wrap; overflow-x: auto;}
        .tab-btn { background: #333; color: white; border: none; padding: 10px 15px; cursor: pointer; border-radius: 5px; flex-grow: 1; white-space: nowrap;}
        .tab-btn.active { background: #4CAF50; }
        .tab-content { display: none; background: #1e1e1e; padding: 20px; border-radius: 8px; margin-top: 10px; }
        .tab-content.active { display: block; }
        .console { background: #000; color: #0f0; padding: 15px; height: 45vh; overflow-y: scroll; border-radius: 8px; font-family: monospace; direction: ltr; text-align: left; }
        .input-group { display: flex; gap: 10px; margin-top: 10px; }
        input[type="text"], input[type="number"], select { flex: 1; padding: 10px; background: #2d2d2d; color: white; border: 1px solid #444; border-radius: 5px; }
        .btn { padding: 10px 15px; border: none; border-radius: 5px; cursor: pointer; color: white; font-weight: bold; }
        .btn-green { background: #4CAF50; } .btn-red { background: #f44336; } .btn-blue { background: #2196F3; } .btn-orange { background: #ff9800; }
        .list-item { display: flex; justify-content: space-between; background: #2d2d2d; padding: 10px; margin-bottom: 5px; border-radius: 5px; align-items: center;}
        .config-row { display: flex; justify-content: space-between; margin-bottom: 10px; align-items: center; background: #2d2d2d; padding: 10px; border-radius: 5px;}
        pre { white-space: pre-wrap; word-wrap: break-word; }
    </style>
</head>
<body>
    <div class="header">
        <h2 style="margin:0;">🎮 إدارة السيرفر</h2>
        <div style="background:#2d2d2d; padding:10px; border-radius:5px; color:#4CAF50; font-weight:bold;" id="ip-display">الآي بي: {{ ip }}</div>
        <a href="/logout" class="btn btn-red" style="text-decoration:none;">خروج</a>
    </div>
    <div class="stats">
        <div class="stat-box">الحالة: <span id="status-text">...</span></div>
        <div class="stat-box">المعالج: <span id="cpu-text">0%</span></div>
        <div class="stat-box">الرام: <span id="ram-text">0%</span></div>
        <div class="stat-box">اللاعبين: <span id="players-count">0</span></div>
    </div>
    <div class="tabs">
        <button class="tab-btn active" onclick="openTab('console')">الكونسول</button>
        <button class="tab-btn" onclick="openTab('players')">اللاعبين</button>
        <button class="tab-btn" onclick="openTab('mods'); loadMods();">المودات</button>
        <button class="tab-btn" onclick="openTab('backups'); loadBackups();">النسخ</button>
        <button class="tab-btn" onclick="openTab('settings'); loadConfig();">الإعدادات</button>
        <button class="tab-btn" onclick="openTab('crashes'); loadCrash();">الكراشات</button>
    </div>
    <!-- الكونسول -->
    <div id="console" class="tab-content active">
        <div style="margin-bottom: 10px; display: flex; gap: 10px;">
            <button class="btn btn-green" onclick="sendAction('start')">▶ تشغيل</button>
            <button class="btn btn-blue" onclick="sendAction('stop')">⏹ إيقاف آمن</button>
            <button class="btn btn-red" onclick="sendAction('kill')">💀 إيقاف إجباري</button>
        </div>
        <div class="console" id="console-box"></div>
        <div class="input-group">
            <input type="text" id="cmd" placeholder="اكتب أمر هنا..." onkeypress="if(event.key === 'Enter') sendCmd()">
            <button class="btn btn-green" onclick="sendCmd()">إرسال</button>
        </div>
    </div>
    <!-- اللاعبين -->
    <div id="players" class="tab-content">
        <h3>👥 اللاعبين المتصلين حالياً</h3>
        <div id="players-list">جاري التحميل...</div>
    </div>
    <!-- المودات -->
    <div id="mods" class="tab-content">
        <h3>📦 إدارة المودات</h3>
        <div class="input-group" style="margin-bottom: 15px;">
            <input type="file" id="mod-file" accept=".jar" style="background: transparent; border: none;">
            <button class="btn btn-green" onclick="uploadMod()">⬆️ رفع مود</button>
        </div>
        <div id="mods-list">جاري التحميل...</div>
    </div>
    <!-- النسخ الاحتياطي -->
    <div id="backups" class="tab-content">
        <h3>💾 النسخ الاحتياطي</h3>
        <button class="btn btn-orange" onclick="createBackup()" style="margin-bottom: 15px; width: 100%;">📦 إنشاء نسخة احتياطية الآن</button>
        <div id="backups-list">جاري التحميل...</div>
    </div>
    <!-- الإعدادات -->
    <div id="settings" class="tab-content">
        <h3>⚙️ إعدادات السيرفر</h3>
        <div id="config-form">جاري التحميل...</div>
        <button class="btn btn-green" onclick="saveConfig()" style="margin-top: 15px; width: 100%;">💾 حفظ الإعدادات</button>
    </div>
    <!-- الكراشات -->
    <div id="crashes" class="tab-content">
        <h3>⚠️ آخر تقرير كراش (Crash Report)</h3>
        <div class="console" id="crash-box" style="color: #ff5555;">جاري التحميل...</div>
    </div>
    <script>
        let autoScroll = true;
        let consoleBox = document.getElementById('console-box');
        consoleBox.addEventListener('scroll', () => { autoScroll = (consoleBox.scrollHeight - consoleBox.scrollTop - consoleBox.clientHeight < 50); });

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
                document.getElementById('status-text').innerText = data.status;
                document.getElementById('ip-display').innerText = "الآي بي: " + data.ip;
                document.getElementById('players-count').innerText = data.players.length;

                consoleBox.innerHTML = data.logs.join('<br>');
                if (autoScroll) consoleBox.scrollTop = consoleBox.scrollHeight;
                // تحديث قائمة اللاعبين
                let p_html = data.players.length === 0 ? '<p>لا يوجد لاعبين متصلين.</p>' : '';
                data.players.forEach(p => {
                    p_html += `<div class="list-item"><span>👤 ${p}</span> <div>
                        <button class="btn btn-blue" onclick="execCmd('op ${p}')">أدمن</button>
                        <button class="btn btn-orange" onclick="execCmd('gamemode creative ${p}')">إبداع</button>
                        <button class="btn btn-red" onclick="execCmd('kick ${p}')">طرد</button>
                    </div></div>`;
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
        function execCmd(cmd) { fetch('/api/command', { method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: 'cmd=' + encodeURIComponent(cmd) }); }
        function sendAction(act) {
            if(act === 'kill' && !confirm('هل أنت متأكد؟')) return;
            fetch('/api/action', { method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: 'action=' + act });
        }
        function loadMods() {
            fetch('/api/mods').then(res => res.json()).then(mods => {
                let html = mods.length === 0 ? '<p>لا توجد مودات.</p>' : '';
                mods.forEach(mod => { html += `<div class="list-item"><span>${mod}</span> <button class="btn btn-red" onclick="deleteMod('${mod}')">حذف</button></div>`; });
                document.getElementById('mods-list').innerHTML = html;
            });
        }
        function uploadMod() {
            let fileInput = document.getElementById('mod-file');
            if(fileInput.files.length === 0) return alert('اختر ملف المود!');
            let formData = new FormData(); formData.append("file", fileInput.files[0]);
            fetch('/api/mods', { method: 'POST', body: formData }).then(() => { alert('تم الرفع!'); fileInput.value = ''; loadMods(); });
        }
        function deleteMod(modName) {
            if(!confirm('حذف ' + modName + '؟')) return;
            fetch('/api/mods', { method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: 'delete=' + encodeURIComponent(modName) }).then(() => loadMods());
        }
        function loadBackups() {
            fetch('/api/backup').then(res => res.json()).then(backups => {
                let html = backups.length === 0 ? '<p>لا توجد نسخ احتياطية.</p>' : '';
                backups.forEach(b => { html += `<div class="list-item"><span>${b}</span> <a href="/api/backup/download/${b}" class="btn btn-blue" style="text-decoration:none;">⬇️ تحميل</a></div>`; });
                document.getElementById('backups-list').innerHTML = html;
            });
        }
        function createBackup() { fetch('/api/backup', { method: 'POST' }).then(() => { alert('بدأ إنشاء النسخة!'); setTimeout(loadBackups, 5000); }); }
        function loadConfig() {
            fetch('/api/config').then(res => res.json()).then(data => {
                let html = '';
                const fields = [
                    {key: 'max-players', label: 'أقصى عدد لاعبين', type: 'number'},
                    {key: 'difficulty', label: 'الصعوبة', type: 'select', options: ['peaceful', 'easy', 'normal', 'hard']},
                    {key: 'pvp', label: 'القتال (PVP)', type: 'select', options: ['true', 'false']},
                    {key: 'view-distance', label: 'مسافة الرؤية', type: 'number'}
                ];
                fields.forEach(f => {
                    let val = data[f.key] || '';
                    html += `<div class="config-row"><span>${f.label}</span>`;
                    if(f.type === 'select') {
                        html += `<select id="cfg-${f.key}">`;
                        f.options.forEach(opt => { html += `<option value="${opt}" ${val===opt?'selected':''}>${opt}</option>`; });
                        html += `</select></div>`;
                    } else { html += `<input type="${f.type}" id="cfg-${f.key}" value="${val}" style="max-width: 100px;"></div>`; }
                });
                document.getElementById('config-form').innerHTML = html;
            });
        }
        function saveConfig() {
            let data = {
                'max-players': document.getElementById('cfg-max-players').value,
                'difficulty': document.getElementById('cfg-difficulty').value,
                'pvp': document.getElementById('cfg-pvp').value,
                'view-distance': document.getElementById('cfg-view-distance').value
            };
            fetch('/api/config', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) }).then(() => alert('تم الحفظ! أعد تشغيل السيرفر.'));
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
