import json
import base64
import time
import threading
import traceback

import numpy as np
import paho.mqtt.client as mqtt
from flask import Flask, render_template_string, request, redirect, session, Response
import bcrypt
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ---------------- CONFIG ----------------
BROKER = "localhost"
BROKER_PORT = 1883
CAMERA_TOPIC = "camera/1"

app = Flask(__name__)
# NOTE: for production use a secure random secret key (os.urandom or env var)
app.secret_key = "supersecret_demo_key_change_me"

# Demo users (bcrypt hashed). For demonstration we hash here (not recommended for real user DB)
users = {
    "alice": bcrypt.hashpw("password123".encode(), bcrypt.gensalt()),
    "robin": bcrypt.hashpw("rob123".encode(), bcrypt.gensalt())
}

# ---------------- TEMPLATES ----------------
login_page = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>IoT Camera - Login</title>
<style>
  :root{
    --neon:#00c2ff;
    font-family: "Segoe UI", Roboto, system-ui, Arial;
  }
  html,body{height:100%;margin:0;background:linear-gradient(180deg,#000 0%, #020417 60%);color:#e6f7ff;}
  .center {min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;}
  .card{background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));border:1px solid rgba(0,194,255,0.08);padding:28px;width:360px;border-radius:12px;box-shadow: 0 0 18px rgba(0,194,255,0.18);backdrop-filter: blur(6px);}
  h2{margin:0 0 18px 0;color:var(--neon);text-shadow: 0 0 8px rgba(0,194,255,0.25);}
  label{display:block;margin:12px 0 6px 0;font-size:13px;color:#cfeeff;}
  input[type="text"], input[type="password"]{width:100%;padding:10px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.04);background:transparent;color:#eafcff;outline:none;box-shadow: inset 0 0 8px rgba(0,194,255,0.02);}
  input::placeholder{color:#6eaecb;}
  .btn{margin-top:16px;width:100%;padding:10px 12px;border-radius:10px;border: none;cursor:pointer;font-weight:600;color:#00121a;background: linear-gradient(90deg,var(--neon), #0bb7ff);box-shadow: 0 6px 18px rgba(0,194,255,0.18);}
  .error{color:#ffb3b3;margin-top:12px;}
</style>
</head>
<body>
  <div class="center">
    <div class="card" role="main" aria-labelledby="login-title">
      <h2 id="login-title">IoT Camera Login</h2>
      <form method="post" novalidate>
        <label for="username">Username</label>
        <input id="username" name="username" type="text" placeholder="Enter username" required/>
        <label for="password">Password</label>
        <input id="password" name="password" type="password" placeholder="Enter password" required/>
        <input type="submit" value="Login" class="btn"/>
      </form>
      {% if error %}
        <div class="error">{{ error }}</div>
      {% endif %}
    </div>
  </div>
</body>
</html>
"""

dashboard_page = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>IoT Camera Dashboard</title>
<style>
  body{margin:0;background-color:#000;color:#e6f7ff;font-family: "Segoe UI", Roboto, system-ui, Arial;}
  header{background:linear-gradient(90deg,#00121a,#002d3d);padding:16px 24px;color:#00c2ff;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 12px rgba(0,194,255,0.18);}
  main{padding:24px;display:flex;flex-direction:column;gap:16px;align-items:center;}
  img{border:3px solid #00c2ff;border-radius:10px;box-shadow:0 0 12px rgba(0,194,255,0.2);}
  a{color:#00c2ff;text-decoration:none;}
</style>
</head>
<body>
  <header>
    <div>Welcome {{user}}</div>
    <div><a href="/logout">Logout</a></div>
  </header>

  <main>
    <h2>Live Camera Feed</h2>
    <img src="/video_feed" width="640" height="480" alt="Camera Feed"/>
  </main>
</body>
</html>
"""

# ---------------- CRYPTO ----------------
server_private = ec.generate_private_key(ec.SECP256R1())
server_public = server_private.public_key()
server_pub_bytes = server_public.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

aes_key = None
key_ready = threading.Event()
latest_frame = None
frame_lock = threading.Lock()

# Track last error to avoid spam
last_error_time = 0

# ---------------- MQTT ----------------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[server] Connected to MQTT broker (rc=0). Subscribing topics.")
        client.subscribe(CAMERA_TOPIC + "/pubkey")
        client.subscribe(CAMERA_TOPIC + "/frame")
    else:
        print(f"[server] MQTT connect failed with rc={rc}")

def try_load_device_pubkey(payload_bytes):
    """
    Try multiple ways to interpret incoming payload as a device public key:
    - Raw PEM bytes
    - JSON with {"pubkey": "PEM text"} or {"pubkey_b64": "..."}
    - JSON with base64-encoded DER or PEM
    Returns a cryptography public key object or raises.
    """
    # 1) raw PEM
    try:
        if payload_bytes.startswith(b"-----BEGIN PUBLIC KEY-----"):
            return serialization.load_pem_public_key(payload_bytes)
    except Exception:
        pass

    # 2) try JSON
    try:
        txt = payload_bytes.decode('utf-8')
        j = json.loads(txt)
        # common field names
        if "pubkey" in j:
            pub = j["pubkey"]
            if isinstance(pub, str) and pub.startswith("-----BEGIN"):
                return serialization.load_pem_public_key(pub.encode())
            # if it's base64-encoded
            try:
                b = base64.b64decode(pub)
                # try PEM first, then DER
                try:
                    return serialization.load_pem_public_key(b)
                except Exception:
                    return serialization.load_der_public_key(b)
            except Exception:
                pass
        if "pubkey_b64" in j:
            b = base64.b64decode(j["pubkey_b64"])
            try:
                return serialization.load_pem_public_key(b)
            except Exception:
                return serialization.load_der_public_key(b)
    except Exception:
        pass

    # 3) try DER directly (binary)
    try:
        return serialization.load_der_public_key(payload_bytes)
    except Exception as e:
        raise ValueError("Unable to parse device public key") from e

def on_message(client, userdata, msg):
    global aes_key, latest_frame, last_error_time
    topic = msg.topic
    try:
        if topic.endswith("pubkey"):
            try:
                device_pub = try_load_device_pubkey(msg.payload)
                shared = server_private.exchange(ec.ECDH(), device_pub)
                aes_key = HKDF(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=None,
                    info=b"camera-session-key"
                ).derive(shared)
                # send server public key (PEM) back
                client.publish(CAMERA_TOPIC + "/serverkey", server_pub_bytes)
                key_ready.set()
                print("[server] AES session key established.")
            except Exception as e:
                print("[server] Failed to establish key:", e)
                traceback.print_exc()

        elif topic.endswith("frame"):
            if not key_ready.is_set():
                # ignore frames until key established
                now = time.time()
                if now - last_error_time > 2:
                    print("[server] Received frame but AES key not ready yet.")
                    last_error_time = now
                return

            try:
                payload = json.loads(msg.payload.decode())
                nonce = base64.b64decode(payload["nonce"])
                ct = base64.b64decode(payload["ciphertext"])
                aesgcm = AESGCM(aes_key)
                jpg_bytes = aesgcm.decrypt(nonce, ct, None)
                # store the latest frame thread-safely
                with frame_lock:
                    latest_frame = jpg_bytes
            except Exception as e:
                now = time.time()
                if now - last_error_time > 2:
                    print("[server] Decryption or frame handling failed:", e)
                    traceback.print_exc()
                    last_error_time = now

    except Exception:
        print("[server] Unexpected error in on_message:")
        traceback.print_exc()

# ---------------- FLASK ROUTES ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "").encode()
        if username in users and bcrypt.checkpw(password, users[username]):
            session["user"] = username
            return redirect("/dashboard")
        else:
            return render_template_string(login_page, error="Invalid credentials")
    return render_template_string(login_page, error=None)

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return render_template_string(dashboard_page, user=session["user"])

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/video_feed")
def video_feed():
    if "user" not in session:
        return redirect("/")
    return Response(generate_mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")

def generate_mjpeg():
    global latest_frame
    while True:
        with frame_lock:
            frame = latest_frame
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.05)

# ---------------- STARTUP ----------------
def start_mqtt():
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(BROKER, BROKER_PORT)
    except Exception as e:
        print(f"[server] MQTT connect error: {e}")
        traceback.print_exc()
        # try reconnect loop (blocking)
        while True:
            try:
                time.sleep(2)
                client.connect(BROKER, BROKER_PORT)
                break
            except Exception:
                print("[server] retrying MQTT connection...")
    # run network loop forever (blocking) inside this thread
    client.loop_forever()

if __name__ == "__main__":
    # Start MQTT thread once
    t = threading.Thread(target=start_mqtt, daemon=True)
    t.start()
    # Run Flask without the reloader to avoid double-execution
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
