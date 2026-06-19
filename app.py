from flask import Flask, render_template_string, request, redirect, session, jsonify
import subprocess
import threading
import os
import time
app = Flask(__name__)
app.secret_key = "super_secret_key_minecraft"
PASSWORD = "2938"
# متغيرات للتحكم بالسيرفر
mc_process = None
server_logs = []
bore_ip = "جاري جلب الآي بي..."
def run_server():
    global mc_process, server_logs, bore_ip
    server_logs.append("بدأ تشغيل السيرفر...")

    # تشغيل ملف start.sh
    mc_process = subprocess.Popen(
        ["bash", "start.sh"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd="/app"
    )

    for line in mc_process.stdout:
        server_logs.append(line.strip())
        if len(server_logs) > 100: # نحتفظ بآخر 100 سطر بس حتى ما يثقل المتصفح
            server_logs.pop(0)

        # سحب آي بي Bore من اللوق
        if "bore.pub:" in line:
            bore_ip = line.split("bore.pub:")[1].split()[0].strip()
            bore_ip = f"bore.pub:{bore_ip}"
@app.route('/')
def index():
    if not session.get('logged_in'):
        return render_template_string(LOGIN_HTML)
    return render_template_string(DASHBOARD_HTML, ip=bore_ip)
@app.route('/login', methods=['POST'])
def login():
    if request.form.get('password') == PASSWORD:
        session['logged_in'] = True
    return redirect('/')
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
@app.route('/api/logs')
def get_logs():
    if not session.get('logged_in'): return "Unauthorized", 401
    return jsonify({"logs": server_logs, "ip": bore_ip})
@app.route('/api/command', methods=['POST'])
def send_command():
    if not session.get('logged_in'): return "Unauthorized", 401
    cmd = request.form.get('cmd')
    if mc_process and mc_process.poll() is None:
        mc_process.stdin.write(cmd + "\n")
        mc_process.stdin.flush()
        server_logs.append(f"> {cmd}")
    return "OK"
# ================= واجهات HTML (مدمجة لسهولة الرفع) =================
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تسجيل الدخول - لوحة التحكم</title>
    <style>
        body { background-color: #121212; color: white; font-family: Arial; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-box { background: #1e1e1e; padding: 40px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); text-align: center; }
        input { padding: 10px; margin: 10px 0; width: 80%; border-radius: 5px; border: none; text-align: center; font-size: 18px; }
        button { padding: 10px 20px; background: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button:hover { background: #45a049; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>🔒 لوحة تحكم السيرفر</h2>
        <form action="/login" method="POST">
            <input type="password" name="password" placeholder="أدخل الرمز السري..." required autofocus>
            <br>
            <button type="submit">دخول</button>
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
    <title>لوحة تحكم ماين كرافت</title>
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: Arial; margin: 0; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; background: #1e1e1e; padding: 15px 20px; border-radius: 8px; }
        .ip-box { background: #2d2d2d; padding: 10px 20px; border-radius: 5px; font-size: 20px; font-weight: bold; color: #4CAF50; }
        .console { background: #000; color: #0f0; padding: 15px; height: 400px; overflow-y: scroll; border-radius: 8px; font-family: monospace; margin-top: 20px; direction: ltr; text-align: left; }
        .cmd-input { width: 100%; padding: 10px; margin-top: 10px; background: #1e1e1e; color: white; border: 1px solid #333; border-radius: 5px; }
        .btn-logout { background: #f44336; color: white; padding: 8px 15px; text-decoration: none; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="header">
        <h2>🎮 إدارة السيرفر</h2>
        <div class="ip-box" id="ip-display">الآي بي: {{ ip }}</div>
        <a href="/logout" class="btn-logout">تسجيل خروج</a>
    </div>

    <div class="console" id="console-box"></div>
    <input type="text" id="cmd" class="cmd-input" placeholder="اكتب أمر هنا (مثال: time set day) واضغط Enter..." onkeypress="sendCommand(event)">
    <script>
        function fetchLogs() {
            fetch('/api/logs').then(res => res.json()).then(data => {
                let consoleBox = document.getElementById('console-box');
                consoleBox.innerHTML = data.logs.join('<br>');
                consoleBox.scrollTop = consoleBox.scrollHeight;
                document.getElementById('ip-display').innerText = "الآي بي: " + data.ip;
            });
        }
        setInterval(fetchLogs, 2000);
        function sendCommand(e) {
            if (e.key === 'Enter') {
                let cmd = document.getElementById('cmd').value;
                fetch('/api/command', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: 'cmd=' + encodeURIComponent(cmd)
                });
                document.getElementById('cmd').value = '';
            }
        }
    </script>
</body>
</html>
"""
if __name__ == '__main__':
    threading.Thread(target=run_server, daemon=True).start()
    app.run(host='0.0.0.0', port=7860)
