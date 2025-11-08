from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from PIL import Image
import io
import fitz  # PyMuPDF
import threading
import time

app = Flask(__name__)
CORS(app, origins=["https://neunovapdfneunovapdf-org.web.app",
  "https://neunovapdf-backend.onrender.com",
  "http://localhost:5000"])

# ==========================
#   GLOBAL VARIABLES
# ==========================
stats = {
    "active_users": 0,
    "total_conversions": 0,
    "active_conversions": 0
}

# Dictionary to track user activity
user_activity = {}


# ==========================
#   CLEANUP FUNCTION
# ==========================
def cleanup_inactive_users():
    """Removes users inactive for >60s from the counter"""
    while True:
        now = time.time()
        inactive_users = [
            user for user, last_seen in user_activity.items() if now - last_seen > 60
        ]
        for user in inactive_users:
            user_activity.pop(user, None)
        stats["active_users"] = len(user_activity)
        time.sleep(30)


# Run cleanup thread in background
threading.Thread(target=cleanup_inactive_users, daemon=True).start()


# ==========================
#   ROUTES
# ==========================
@app.route("/")
def home():
    return jsonify({"status": "NeunovaPDF backend running"})


@app.route("/jpg-to-pdf", methods=["POST"])
def jpg_to_pdf():
    try:
        stats["active_conversions"] += 1
        user_ip = request.remote_addr
        user_activity[user_ip] = time.time()
        stats["active_users"] = len(user_activity)

        # Retrieve quality setting
        quality = request.form.get("quality", "medium")
        quality_map = {
            "low": 50,
            "medium": 70,
            "high": 85,
            "very_high": 100
        }
        quality_value = quality_map.get(quality, 100)

        # Process images
        images = request.files.getlist("images")
        if not images:
            stats["active_conversions"] -= 1
            return jsonify({"error": "No images uploaded"}), 400

        pdf_bytes = io.BytesIO()
        pdf = fitz.open()

        for img_file in images:
            img = Image.open(img_file.stream).convert("RGB")

            # Compress image quality
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="JPEG", quality=quality_value)
            img_bytes.seek(0)

            # Add to PDF
            pdf_page = pdf.new_page(width=img.width, height=img.height)
            rect = fitz.Rect(0, 0, img.width, img.height)
            pdf_page.insert_image(rect, stream=img_bytes.getvalue())

        pdf.save(pdf_bytes)
        pdf_bytes.seek(0)
        pdf.close()

        stats["total_conversions"] += 1
        stats["active_conversions"] -= 1

        return send_file(
            pdf_bytes,
            as_attachment=True,
            download_name="converted.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        stats["active_conversions"] = max(0, stats["active_conversions"] - 1)
        return jsonify({"error": str(e)}), 500


@app.route("/stats", methods=["GET"])
def get_stats():
    """Returns live usage statistics"""
    return jsonify(stats)


# ==========================
#   MAIN ENTRY
# ==========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
