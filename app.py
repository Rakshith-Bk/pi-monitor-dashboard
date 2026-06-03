from flask import Flask, render_template, jsonify, request, redirect, url_for, session, Response
from datetime import timedelta
from datetime import datetime
from flask import send_file
import io
import os
import psutil
import socket
import platform
import time
import cv2


app = Flask(__name__)

@app.before_request
def session_handler():

    allowed_routes = ['login', 'static']

    if request.endpoint not in allowed_routes:

        session.clear()
app.secret_key = "raspberrypi_dashboard_secret"

app.permanent_session_lifetime = timedelta(minutes=5)

USERNAME = "pi"
PASSWORD = "pi"

old_data = psutil.net_io_counters()
old_time = time.time()
cap = cv2.VideoCapture(
    "rtsp://admin:Datacorp123$@10.1.21.235"
)

cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

latest_frame = None

# LOGIN PAGE
@app.route('/', methods=['GET', 'POST'])
def login():

    error = None

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        if username == USERNAME and password == PASSWORD:

            session['logged_in'] = True

            return redirect(url_for('dashboard'))

        else:

            error = "Incorrect Username or Password"

    return render_template('login.html', error=error)


# DASHBOARD
@app.route('/dashboard')
def dashboard():

    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent

    temp = open("/sys/class/thermal/thermal_zone0/temp").read()
    temp = int(temp) / 1000

    uptime = open('/proc/uptime').read().split()[0]
    uptime = float(uptime)

    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)

    uptime = f"{hours}h {minutes}m"

    hostname = socket.gethostname()

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()

    freq = psutil.cpu_freq().current

    linux = platform.system() + " " + platform.release()

    return render_template(
        'index.html',
        cpu=cpu,
        ram=ram,
        disk=disk,
        temp=temp,
        uptime=uptime,
        hostname=hostname,
        ip=ip,
        freq=freq,
        linux=linux
    )

@app.route('/memory')
def memory():

    mem = psutil.virtual_memory()

    swap = psutil.swap_memory()

    return render_template(

        'memory.html',

        total_ram=round(mem.total / (1024**3), 2),

        used_ram=round(mem.used / (1024**3), 2),

        free_ram=round(mem.free / (1024**3), 2),

        available_ram=round(mem.available / (1024**3), 2),

        ram_percent=mem.percent,

        cached_ram=round(mem.cached / (1024**3), 2),

        buffers_ram=round(mem.buffers / (1024**3), 2),

        swap_total=round(swap.total / (1024**3), 2),

        swap_used=round(swap.used / (1024**3), 2),

        swap_free=round(swap.free / (1024**3), 2)

    )

@app.route('/memory_stats')
def memory_stats():

    mem = psutil.virtual_memory()

    swap = psutil.swap_memory()

    return jsonify({

        'total_ram': round(mem.total / (1024**3), 2),

        'used_ram': round(mem.used / (1024**3), 2),

        'free_ram': round(mem.free / (1024**3), 2),

        'available_ram': round(mem.available / (1024**3), 2),

        'ram_percent': mem.percent,

        'cached_ram': round(mem.cached / (1024**3), 2),

        'buffers_ram': round(mem.buffers / (1024**3), 2),

        'swap_used': round(swap.used / (1024**3), 2)

    })

@app.route('/network')
def network():

    hostname = socket.gethostname()

    ip = "Unavailable"

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:

        s.connect(("8.8.8.8", 80))

        ip = s.getsockname()[0]

    except:

        pass

    finally:

        s.close()

    mac = psutil.net_if_addrs()['wlan0'][0].address

    return render_template(

        'network.html',

        hostname=hostname,

        ip=ip,

        mac=mac
    )

# SYSTEM LOGS PAGE
@app.route('/logs')
def logs():

    try:

        import subprocess

        logs = subprocess.check_output(

            ['journalctl', '-n', '50', '--no-pager']

        ).decode('utf-8')

        log_data = logs.split('\n')

    except Exception as e:

        log_data = [str(e)]

    return render_template(

        'logs.html',

        logs=log_data

    )

@app.route('/camera')
def camera():

    return render_template('camera.html')

def generate_frames():

    global latest_frame
    global cap

    while True:

        success, frame = cap.read()

        if not success:

            print("RTSP Lost - Reconnecting...")

            cap.release()

            time.sleep(1)

            cap = cv2.VideoCapture(
                "rtsp://admin:Datacorp123$@10.1.21.235"
            )

            cap.set(
                cv2.CAP_PROP_BUFFERSIZE,
                1
            )

            continue

        latest_frame = frame.copy()

        frame = cv2.resize(
            frame,
            (960, 540)
        )

        ret, buffer = cv2.imencode(
            '.jpg',
            frame
        )

        if not ret:

            continue

        frame_bytes = buffer.tobytes()

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n'
            + frame_bytes +
            b'\r\n'
        )

@app.route('/video_feed')
def video_feed():

    return Response(

        generate_frames(),

        mimetype=
        'multipart/x-mixed-replace; boundary=frame'

    )

@app.route('/capture')
def capture():

    global latest_frame

    if latest_frame is None:

        return "No frame available"

    ret, buffer = cv2.imencode(
        '.jpg',
        latest_frame
    )

    img_io = io.BytesIO(
        buffer.tobytes()
    )

    return send_file(

        img_io,

        mimetype='image/jpeg',

        as_attachment=True,

        download_name=datetime.now().strftime(
            "snapshot_%Y%m%d_%H%M%S.jpg"
        )

    )

@app.route('/logs_data')
def logs_data():

    try:

        import subprocess

        logs = subprocess.check_output(

            ['journalctl', '-n', '50', '--no-pager']

        ).decode('utf-8')

        log_data = logs.split('\n')

    except Exception as e:

        log_data = [str(e)]

    return jsonify({

        'logs': log_data

    })

# SETTINGS PAGE
@app.route('/settings')
def settings():

    return render_template('settings.html')

# REBOOT PI
@app.route('/reboot')
def reboot():

    import os

    os.system('sudo reboot')

    return redirect(url_for('settings'))


# SHUTDOWN PI
@app.route('/shutdown')
def shutdown():

    import os

    os.system('sudo shutdown now')

    return redirect(url_for('settings'))


# RESTART DASHBOARD
@app.route('/restart_dashboard')
def restart_dashboard():

    session.clear()

    import os

    os.system(
        'sudo systemctl restart pi-monitor.service &'
    )

    return redirect(url_for('login'))


# LIVE STATS
@app.route('/stats')
def stats():

    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent

    temp = open("/sys/class/thermal/thermal_zone0/temp").read()
    temp = int(temp) / 1000

    global old_data, old_time

    new_data = psutil.net_io_counters()
    new_time = time.time()

    time_diff = new_time - old_time

    download_speed = (
        (new_data.bytes_recv - old_data.bytes_recv)
        / time_diff / 1024
    )

    upload_speed = (
        (new_data.bytes_sent - old_data.bytes_sent)
        / time_diff / 1024
    )

    old_data = new_data
    old_time = new_time

    return jsonify({

        'cpu': cpu,
        'ram': ram,
        'disk': disk,
        'temp': temp,
        'download': round(download_speed, 2),
        'upload': round(upload_speed, 2)

    })


# LOGOUT
@app.route('/logout')
def logout():

    session.clear()

    return redirect(url_for('login'))


if __name__ == "__main__":
    app.run(
        host='0.0.0.0',
        port=5000,
        threaded=True
    )