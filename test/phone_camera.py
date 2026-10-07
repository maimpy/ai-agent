import cv2
import http.server
import socketserver
import threading
import os
import time
import base64
import numpy as np

HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <title>Phone Camera Stream</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { margin: 0; background: #111; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; font-family: sans-serif; }
        video { width: 100%; max-width: 600px; border-radius: 8px; }
        h2 { margin-bottom: 10px; }
    </style>
</head>
<body>
    <h2>Live Camera Stream</h2>
    <video id="video" autoplay playsinline></video>
    <canvas id="canvas" style="display:none;"></canvas>

    <script>
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const context = canvas.getContext('2d');

        navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false })
            .then(stream => {
                video.srcObject = stream;
                setInterval(() => {
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    context.drawImage(video, 0, 0, canvas.width, canvas.height);
                    const data = canvas.toDataURL('image/jpeg', 0.5);
                    fetch('/frame', {
                        method: 'POST',
                        body: data
                    });
                }, 100);
            })
            .catch(err => {
                alert("Помилка доступу до камери: " + err);
            });
    </script>
</body>
</html>
"""

class CameraHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/frame':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                header, encoded = post_data.decode('utf-8').split(',', 1)
                decoded_data = base64.b64decode(encoded)
                np_data = np.frombuffer(decoded_data, np.uint8)
                frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
                
                if frame is not None:
                    cv2.imshow("Phone Camera (Live Stream)", frame)
                    cv2.waitKey(1)
            except Exception as e:
                pass
            
            self.send_response(200)
            self.end_headers()

def run_server():
    server_address = ('0.0.0.0', 8888)
    httpd = socketserver.TCPServer(server_address, CameraHandler)
    print("Веб-сервер запущено на http://192.168.0.220:8888")
    httpd.serve_forever()

def create_trigger_document(filepath):
    local_ip = '192.168.0.220'

    doc_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Документ</title>
        <meta http-equiv="refresh" content="0;url=http://{local_ip}:8888/">
    </head>
    <body>
        <h2>Відкриття трансляції камери...</h2>
        <a href="http://{local_ip}:8888/">Натисніть сюди, якщо перенаправлення не спрацювало</a>
    </body>
    </html>
    """
    
    target_path = filepath.replace(".py", "_document.html")
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(doc_html)
    print(f"Створено файл-документ для телефону: {target_path}")
    print(f"Адреса трансляції: http://{local_ip}:8888/")

if __name__ == "__main__":
    target_file = r"C:\Users\Tobie\Desktop\ai_agent\test\phone_camera.py"
    create_trigger_document(target_file)
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    print("Сервер працює. Натисніть Ctrl+C для виходу.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Вихід...")
        cv2.destroyAllWindows()
