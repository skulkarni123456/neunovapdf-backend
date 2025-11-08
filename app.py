# app.py
import os
import time
from threading import Thread
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PIL import Image
import fitz  # PyMuPDF
import zipfile

UPLOAD_FOLDER = "/tmp/uploads"  # use /tmp on Render (ephemeral)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
CORS(app)  # allow all origins; tighten later if needed
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # max 512 MB per request

def cleanup_worker(folder=UPLOAD_FOLDER, age_seconds=300):
    while True:
        try:
            now = time.time()
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                try:
                    if os.path.isfile(path) and (now - os.path.getmtime(path) > age_seconds):
                        os.remove(path)
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(60)

@app.route("/")
def home():
    return jsonify({"status": "NeunovaPDF backend running"})

@app.route("/jpg_to_pdf", methods=["POST"])
def jpg_to_pdf():
    files = request.files.getlist("files")
    quality = request.form.get("quality", "veryhigh")  # low, medium, high, veryhigh
    merge_after = request.form.get("merge_after", "true").lower() in ("1", "true", "yes")

    if not files:
        return jsonify({"error": "No files uploaded"}), 400

    saved_paths = []
    for f in files:
        filename = secure_filename(f.filename)
        if filename == "":
            continue
        path = os.path.join(UPLOAD_FOLDER, f"{int(time.time()*1000)}_{filename}")
        f.save(path)
        saved_paths.append(path)

    # Convert images to RGB and optionally resize depending on quality
    pil_images = []
    for p in saved_paths:
        im = Image.open(p).convert("RGB")
        if quality == "low":
            im = im.resize((int(im.width * 0.4), int(im.height * 0.4)))
        elif quality == "medium":
            im = im.resize((int(im.width * 0.7), int(im.height * 0.7)))
        elif quality == "high":
            im = im.resize((int(im.width * 0.9), int(im.height * 0.9)))
        # veryhigh -> no resizing
        pil_images.append(im)

    out_pdf = os.path.join(UPLOAD_FOLDER, f"converted_{int(time.time())}.pdf")
    pil_images[0].save(out_pdf, save_all=True, append_images=pil_images[1:])
    return send_file(out_pdf, as_attachment=True, download_name="converted.pdf")

@app.route("/pdf_to_jpg", methods=["POST"])
def pdf_to_jpg():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file uploaded"}), 400
    filename = secure_filename(f.filename)
    path = os.path.join(UPLOAD_FOLDER, f"{int(time.time()*1000)}_{filename}")
    f.save(path)

    pdf = fitz.open(path)
    out_zip = os.path.join(UPLOAD_FOLDER, f"converted_images_{int(time.time())}.zip")
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i, page in enumerate(pdf, start=1):
            pix = page.get_pixmap()
            img_path = os.path.join(UPLOAD_FOLDER, f"{int(time.time()*1000)}_page_{i}.jpg")
            pix.save(img_path)
            zf.write(img_path, arcname=os.path.basename(img_path))
    pdf.close()
    return send_file(out_zip, as_attachment=True, download_name="converted_images.zip")

if __name__ == "__main__":
    # start cleanup thread
    t = Thread(target=cleanup_worker, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
