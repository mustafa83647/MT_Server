from flask import Flask, render_template_string, request, redirect, session, jsonify
import subprocess
import threading
import os
import time
import re
app = Flask(__name__)
app.secret_key = "super_secret_key_minecraft"
PASSWORD = "2938"
# متغيرات للتحكم بالسيرفر
mc_process = None
server_logs = []
bore_ip = "جاري جلب الآي بي..."
# وظيفة صيد الآي بي من ملف Bore
def fetch_bore_ip():
    global bore_ip
    while bore_ip == "جاري جلب الآي بي...":
        try:
            if os.path.exists("/app/bore.log"):
                with open("/app/bore.log", "r") as f:
                    content = f.read()
                    # البحث عن البورت باستخدام الذكاء
                    match = re.search(r'bore\.pub:(\d+)', content)
                    if match:
                        bore_ip = f"bore.pub:{match.group(1)}"
                        server_logs.append(f"[النظام] 🟢 تم التقاط الآي بي بنجاح: {bore_ip}")
                        break
        except:
            pass
        time.sleep(2)
def run_server():
    global mc_process, server_logs
    server_logs.append("[النظام] بدأ تشغيل السيرفر...")
    # تشغيل صياد الآي بي بالخلفية
    threading.Thread(target=fetch_bore_ip, daemon=True).start()
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
        if len(server_logs) > 150: # كبرنا اللوق شوية حتى تشوف تفاصيل اكثر
            server_logs.pop(0)
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
        server_logs.append(f"[أنت] > {cmd}")
    return "OK"
# ================= واجهات HTML =================
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول - لوحة التحكم</title>
    <style>
        body { background-color: #121212; color: white; font-family: Arial; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-box { background: #1e1e1e; padding: 40px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); text-align: center; width: 80%; max-width: 400px; }
        input { padding: 10px; margin: 10px 0; width: 90%; border-radius: 5px; border: none; text-align: center; font-size: 18px; }
        button { padding: 10px 20px; background: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; width: 100%; }
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة تحكم ماين كرافت</title>
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: Arial; margin: 0; padding: 15px; }
        .header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; background: #1e1e1e; padding: 15px; border-radius: 8px; gap: 10px; }
        .ip-box { background: #2d2d2d; padding: 10px 15px; border-radius: 5px; font-size: 18px; font-weight: bold; color: #4CAF50; text-align: center; flex-grow: 1; }
        .console { background: #000; color: #0f0; padding: 15px; height: 60vh; overflow-y: scroll; border-radius: 8px; font-family: monospace; margin-top: 15px; direction: ltr; text-align: left; font-size: 14px; }
        .cmd-input { width: 100%; padding: 12px; margin-top: 10px; background: #1e1e1e; color: white; border: 1px solid #333; border-radius: 5px; box-sizing: border-box; font-size: 16px; }
        .btn-logout { background: #f44336; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; text-align: center; }
    </style>
</head>
<body>
    <div class="header">
        <h2 style="margin: 0;">🎮 إدارة السيرفر</h2>
        <div class="ip-box" id="ip-display">الآي بي: {{ ip }}</div>
        <a href="/logout" class="btn-logout">خروج</a>
    </div>
    <div class="console" id="console-box"></div>
    <input type="text" id="cmd" class="cmd-input" placeholder="اكتب أمر هنا (مثال: time set day) واضغط Enter..." onkeypress="sendCommand(event)">
    <script>
        let autoScroll = true;
        let consoleBox = document.getElementById('console-box');
        // إيقاف النزول التلقائي إذا صعدت تقرأ اللوق
        consoleBox.addEventListener('scroll', () => {
            if (consoleBox.scrollHeight - consoleBox.scrollTop - consoleBox.clientHeight > 50) {
                autoScroll = false;
            } else {
                autoScroll = true;
            }
        });
        function fetchLogs() {
            fetch('/api/logs').then(res => res.json()).then(data => {
                consoleBox.innerHTML = data.logs.join('<br>');
                if (autoScroll) {
                    consoleBox.scrollTop = consoleBox.scrollHeight;
                }
                document.getElementById('ip-display').innerText = "الآي بي: " + data.ip;
            });
        }
        setInterval(fetchLogs, 2000);
        function sendCommand(e) {
            if (e.key === 'Enter') {
                let cmd = document.getElementById('cmd').value;
                if(cmd.trim() === "") return;
                fetch('/api/command', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: 'cmd=' + encodeURIComponent(cmd)
                });
                document.getElementById('cmd').value = '';
                autoScroll = true; // إجبار النزول عند إرسال أمر
            }
        }
    </script>
</body>
</html>
"""
if __name__ == '__main__':
    threading.Thread(target=run_server, daemon=True).start()
    app.run(host='0.0.0.0', port=7860)
