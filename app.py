from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from PIL import Image
import fitz  # PyMuPDF
import os, io, time
from datetime import datetime

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = '/tmp/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -----------------------------
# 📊 GLOBAL STATS
# -----------------------------
stats = {
    "start_time": datetime.utcnow().isoformat(),
    "total_conversions": 0,
    "active_conversions": 0,
    "active_users": 0
}

# -----------------------------
# ✅ HEALTH CHECK
# -----------------------------
@app.route('/')
def home():
    return jsonify({"status": "NeunovaPDF backend running"})

# -----------------------------
# 📈 STATS ENDPOINT
# -----------------------------
@app.route('/stats', methods=['GET'])
def get_stats():
    uptime_seconds = (datetime.utcnow() - datetime.fromisoformat(stats["start_time"])).seconds
    return jsonify({
        "active_users": stats["active_users"],
        "total_conversions": stats["total_conversions"],
        "active_conversions": stats["active_conversions"],
        "uptime_seconds": uptime_seconds
    })

@app.before_request
def before_request():
    stats["active_users"] += 1

@app.after_request
def after_request(response):
    stats["active_users"] = max(stats["active_users"] - 1, 0)
    return response

# -----------------------------
# 🖼 JPG → PDF
# -----------------------------
@app.route('/jpg_to_pdf', methods=['POST'])
def jpg_to_pdf():
    stats["active_conversions"] += 1
    try:
        files = request.files.getlist('files')
        if not files:
            return jsonify({"error": "No files uploaded"}), 400

        images = []
        for file in files:
            filename = str(int(time.time() * 1000)) + "_" + file.filename
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)

            try:
                im = Image.open(path)
                im.verify()  # Validate image
                im = Image.open(path).convert("RGB")
                images.append(im)
            except Exception as e:
                return jsonify({"error": f"Invalid image: {str(e)}"}), 400

        pdf_path = os.path.join(UPLOAD_FOLDER, f"{int(time.time())}_output.pdf")
        images[0].save(pdf_path, save_all=True, append_images=images[1:])
        stats["total_conversions"] += 1
        return send_file(pdf_path, as_attachment=True)

    finally:
        stats["active_conversions"] = max(stats["active_conversions"] - 1, 0)

# -----------------------------
# 🧹 DELETE OLD FILES
# -----------------------------
@app.after_request
def cleanup(response):
    now = time.time()
    for f in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, f)
        if os.path.isfile(path) and now - os.path.getmtime(path) > 180:
            try:
                os.remove(path)
            except:
                pass
    return response

# -----------------------------
# 🚀 START
# -----------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
