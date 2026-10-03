from flask import Flask, jsonify, render_template, send_from_directory
from pathlib import Path
import json

BASE_DIR = Path(__file__).parent
GAUSS_DIR = BASE_DIR / "data" / "gauss"

app = Flask(__name__, static_folder='static')

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/gauss/years")
def list_years():
    if not GAUSS_DIR.exists():
        return jsonify([])
    years = []
    for folder in sorted(GAUSS_DIR.iterdir(), reverse=True):
        if folder.is_dir() and (folder / "metadata.json").exists():
            years.append(folder.name)
    return jsonify(years)

@app.route("/api/gauss/<year>")
def get_gauss_metadata(year):
    metadata_path = GAUSS_DIR / year / "metadata.json"
    if not metadata_path.exists():
        return jsonify({"error": f"metadata not found for year {year}"}), 404
    with open(metadata_path, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))

@app.route("/data/gauss/<year>/<folder>/<filename>")
def serve_image(year, folder, filename):
    image_dir = GAUSS_DIR / year / folder
    if not image_dir.exists() or not (image_dir / filename).exists():
        return jsonify({"error": "image not found"}), 404
    return send_from_directory(image_dir, filename)

# Vercel 需要这个变量
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)