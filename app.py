from flask import Flask, jsonify, render_template
from pathlib import Path
import json

BASE_DIR = Path(__file__).parent
# 必须是 public/data/gauss
GAUSS_DIR = BASE_DIR / "public" / "data" / "gauss"

app = Flask(__name__)

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

# 不要加 serve_image 路由！Vercel 会自动处理图片

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)