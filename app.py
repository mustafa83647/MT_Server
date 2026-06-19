from flask import Flask, render_template_string, request, redirect, session, jsonify
import subprocess
import threading
import os
import time
import re
import psutil
app = Flask(__name__)
app.secret_key = "super_secret_key_minecraft"
PASSWORD = "2938"
mc_process = None
server_logs = []
bore_ip = "جاري جلب الآي بي..."
DATA_DIR = "/data/minecraft_data"
def fetch_bore_ip():
    global bore_ip
    while True:
        try:
            if os.path.exists("/app/bore.log"):
                with open("/app/bore.log", "r") as f:
                    content = f.read()
                    match = re.search(r'bore\.pub:(\d+)', content)
                    if match:
                        new_ip = f"bore.pub:{match.group(1)}"
                        if bore_ip != new_ip:
                            bore_ip = new_ip
                            server_logs.append(f"[النظام] 🟢 تم التقاط الآي بي: {bore_ip}")
        except: pass
        time.sleep(5)
def run_server():
    global mc_process, server_logs
    if mc_process and mc_process.poll() is None:
        return # السيرفر شغال أصلاً

    server_logs.append("[النظام] 🚀 جاري تشغيل السيرفر...")
    mc_process = subprocess.Popen(
        ["bash", "start.sh"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd="/app"
    )
    for line in mc_process.stdout:
        server_logs.append(line.strip())
        if len(server_logs) > 200: server_logs.pop(0)
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
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    is_running = mc_process and mc_process.poll() is None
    return jsonify({"cpu": cpu, "ram": ram, "status": "شغال 🟢" if is_running else "متوقف 🔴", "logs": server_logs, "ip": bore_ip})
@app.route('/api/action', methods=['POST'])
def action():
    if not session.get('logged_in'): return "Unauthorized", 401
    act = request.form.get('action')
    global mc_process
    if act == "stop" and mc_process and mc_process.poll() is None:
        mc_process.stdin.write("stop\n")
        mc_process.stdin.flush()
        server_logs.append("[النظام] 🛑 تم إرسال أمر الإيقاف الآمن...")
    elif act == "kill" and mc_process:
        mc_process.kill()
        server_logs.append("[النظام] 💀 تم قتل السيرفر إجبارياً!")
    elif act == "start":
        threading.Thread(target=run_server, daemon=True).start()
    return "OK"
@app.route('/api/command', methods=['POST'])
def send_command():
    if not session.get('logged_in'): return "Unauthorized", 401
    cmd = request.form.get('cmd')
    if mc_process and mc_process.poll() is None and cmd.trim() != "":
        mc_process.stdin.write(cmd + "\n")
        mc_process.stdin.flush()
        server_logs.append(f"[أنت] > {cmd}")
    return "OK"
@app.route('/api/mods')
def list_mods():
    if not session.get('logged_in'): return "Unauthorized", 401
    mods_path = os.path.join(DATA_DIR, "mods")
    if not os.path.exists(mods_path): return jsonify([])
    mods = [f for f in os.listdir(mods_path) if f.endswith('.jar')]
    return jsonify(mods)
@app.route('/api/mods/delete', methods=['POST'])
def delete_mod():
    if not session.get('logged_in'): return "Unauthorized", 401
    mod_name = request.form.get('mod_name')
    try:
        os.remove(os.path.join(DATA_DIR, "mods", mod_name))
        return "Deleted"
    except: return "Error", 500
# ================= واجهات HTML =================
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>تسجيل الدخول</title><style>body{background:#121212;color:#fff;font-family:Arial;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}.box{background:#1e1e1e;padding:40px;border-radius:10px;text-align:center;box-shadow:0 4px 15px rgba(0,0,0,0.5)}input{padding:10px;margin:10px 0;width:90%;border-radius:5px;border:none;text-align:center;font-size:18px}button{padding:10px 20px;background:#4CAF50;color:#fff;border:none;border-radius:5px;cursor:pointer;width:100%;font-size:16px}</style></head><body><div class="box"><h2>🔒 لوحة التحكم</h2><form action="/login" method="POST"><input type="password" name="password" placeholder="الرمز السري..." required autofocus><br><button type="submit">دخول</button></form></div></body></html>
"""
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
        .stats { display: flex; gap: 15px; margin-top: 15px; }
        .stat-box { background: #2d2d2d; padding: 15px; border-radius: 8px; flex: 1; text-align: center; font-weight: bold; }
        .tabs { margin-top: 20px; display: flex; gap: 10px; }
        .tab-btn { background: #333; color: white; border: none; padding: 10px 20px; cursor: pointer; border-radius: 5px; }
        .tab-btn.active { background: #4CAF50; }
        .tab-content { display: none; background: #1e1e1e; padding: 20px; border-radius: 8px; margin-top: 10px; }
        .tab-content.active { display: block; }
        .console { background: #000; color: #0f0; padding: 15px; height: 50vh; overflow-y: scroll; border-radius: 8px; font-family: monospace; direction: ltr; text-align: left; }
        .input-group { display: flex; gap: 10px; margin-top: 10px; }
        input[type="text"] { flex: 1; padding: 10px; background: #2d2d2d; color: white; border: none; border-radius: 5px; }
        .btn { padding: 10px 15px; border: none; border-radius: 5px; cursor: pointer; color: white; font-weight: bold; }
        .btn-green { background: #4CAF50; } .btn-red { background: #f44336; } .btn-blue { background: #2196F3; }
        .mod-item { display: flex; justify-content: space-between; background: #2d2d2d; padding: 10px; margin-bottom: 5px; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="header">
        <h2 style="margin:0;">🎮 إدارة السيرفر</h2>
        <div style="background:#2d2d2d; padding:10px; border-radius:5px; color:#4CAF50; font-weight:bold;" id="ip-display">الآي بي: {{ ip }}</div>
        <a href="/logout" class="btn btn-red" style="text-decoration:none;">خروج</a>
    </div>
    <div class="stats">
        <div class="stat-box">الحالة: <span id="status-text">جاري التحميل...</span></div>
        <div class="stat-box">المعالج (CPU): <span id="cpu-text">0%</span></div>
        <div class="stat-box">الرام (RAM): <span id="ram-text">0%</span></div>
    </div>
    <div class="tabs">
        <button class="tab-btn active" onclick="openTab('console')">الكونسول والتحكم</button>
        <button class="tab-btn" onclick="openTab('mods'); loadMods();">مدير المودات</button>
        <button class="tab-btn" onclick="openTab('players')">إجراءات سريعة</button>
    </div>
    <!-- تبويب الكونسول -->
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
    <!-- تبويب المودات -->
    <div id="mods" class="tab-content">
        <h3>📦 المودات المثبتة (في مجلد /data)</h3>
        <p style="color: #aaa; font-size: 12px;">لإضافة مود جديد، ارفعه يدوياً لمجلد mods أو سنضيف زر الرفع بالتحديث القادم.</p>
        <div id="mods-list">جاري التحميل...</div>
    </div>
    <!-- تبويب اللاعبين -->
    <div id="players" class="tab-content">
        <h3>⚡ أوامر سريعة</h3>
        <div class="input-group" style="max-width: 400px; margin-bottom: 15px;">
            <input type="text" id="target-player" placeholder="اسم اللاعب المستهدف...">
        </div>
        <button class="btn btn-blue" onclick="quickCmd('op')">إعطاء أدمن (OP)</button>
        <button class="btn btn-red" onclick="quickCmd('kick')">طرد (Kick)</button>
        <button class="btn btn-red" onclick="quickCmd('ban')">حظر (Ban)</button>
        <hr style="border-color: #333; margin: 20px 0;">
        <button class="btn btn-green" onclick="execCmd('time set day')">☀️ نهار</button>
        <button class="btn btn-blue" onclick="execCmd('time set night')">🌙 ليل</button>
        <button class="btn btn-green" onclick="execCmd('weather clear')">🌤 طقس صافي</button>
    </div>
    <script>
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
                document.getElementById('status-text').innerText = data.status;
                document.getElementById('ip-display').innerText = "الآي بي: " + data.ip;

                consoleBox.innerHTML = data.logs.join('<br>');
                if (autoScroll) consoleBox.scrollTop = consoleBox.scrollHeight;
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
            fetch('/api/command', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: 'cmd=' + encodeURIComponent(cmd)
            });
        }
        function sendAction(act) {
            if(act === 'kill' && !confirm('هل أنت متأكد؟ قد تفقد بعض البيانات غير المحفوظة!')) return;
            fetch('/api/action', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: 'action=' + act
            });
        }
        function quickCmd(action) {
            let player = document.getElementById('target-player').value;
            if(!player) { alert('اكتب اسم اللاعب أولاً!'); return; }
            execCmd(action + ' ' + player);
        }
        function loadMods() {
            fetch('/api/mods').then(res => res.json()).then(mods => {
                let html = '';
                if(mods.length === 0) html = '<p>لا توجد مودات مثبتة.</p>';
                mods.forEach(mod => {
                    html += `<div class="mod-item"><span>${mod}</span> <button class="btn btn-red" onclick="deleteMod('${mod}')">حذف</button></div>`;
                });
                document.getElementById('mods-list').innerHTML = html;
            });
        }
        function deleteMod(modName) {
            if(!confirm('هل تريد حذف ' + modName + '؟')) return;
            fetch('/api/mods/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: 'mod_name=' + encodeURIComponent(modName)
            }).then(() => loadMods());
        }
    </script>
</body>
</html>
"""
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)
