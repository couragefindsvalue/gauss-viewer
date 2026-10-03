import re
import json
import gc
import pdfplumber
from pathlib import Path

# ================= 配置 =================
SCRIPT_DIR = Path(__file__).parent
PDF_QUESTIONS_DIR = SCRIPT_DIR / "pdfs"
PDF_SOLUTIONS_DIR = SCRIPT_DIR / "pdfs" / "solutions"
OUTPUT_BASE_DIR = SCRIPT_DIR / "data" / "gauss"

# ★ 图片输出分辨率（DPI）：150 手机够用，300 电视清晰，400 超大屏
RESOLUTION = 300

# ★ 图片格式：png（无损，文件大）或 webp（有损，文件小约 70%，清晰度几乎无损）
IMAGE_FORMAT = "webp"
WEBP_QUALITY = 92   # webp 质量（1-100），92 是肉眼无损的甜点


# ================= 自动检测跳过页数 =================
def detect_skip_pages(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
            for w in words:
                text = w['text'].strip()
                if re.match(r'^\d{1,2}\.$', text) and w['x0'] < 80:
                    return page_num
    return 0


# ================= 核心解析函数 =================
def convert_pdf_to_images(pdf_path, output_dir, resolution=RESOLUTION, skip_pages=0):
    image_paths = {}
    output_dir.mkdir(parents=True, exist_ok=True)
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            if page_num < skip_pages:
                continue
            img = None
            try:
                img = page.to_image(resolution=resolution)
                new_idx = page_num - skip_pages

                if IMAGE_FORMAT == "webp":
                    # WebP 格式：需要先保存为 PNG 再转，或用 PIL 直接转
                    filename = f"page_{new_idx+1:02d}.webp"
                    save_path = output_dir / filename
                    # pdfplumber 内部是 PIL Image，直接转换成 webp
                    img.save(str(save_path), format="WEBP", quality=WEBP_QUALITY, method=6)
                else:
                    filename = f"page_{new_idx+1:02d}.png"
                    save_path = output_dir / filename
                    img.save(str(save_path))

                image_paths[new_idx] = f"{output_dir.name}/{filename}"
            except Exception as e:
                print(f"    ❌ 切图失败 原第{page_num+1}页: {e}")
            finally:
                if img is not None:
                    try: img.close()
                    except Exception: pass
    gc.collect()
    return image_paths


def extract_anchors(pdf_path, max_questions=30, skip_pages=0):
    anchors = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            if page_num < skip_pages:
                continue
            words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
            sorted_words = sorted(words, key=lambda w: (round(w['top'] / 5), w['x0']))
            for i, word in enumerate(sorted_words):
                text = word['text'].strip()
                q_match = re.match(r'^(\d{1,2})\.$', text)
                if q_match and word['x0'] < 80:
                    q_num = int(q_match.group(1))
                    if 1 <= q_num <= max_questions:
                        look_ahead = " ".join([w['text'] for w in sorted_words[i+1:i+4]])
                        if re.match(r'^[\d\s\+\-\*\/\=\.\,]+$', look_ahead.strip()):
                            continue
                        anchors.append({
                            'number': q_num,
                            'page': page_num - skip_pages,
                            'top': word['top']
                        })
    seen = {}
    for a in anchors:
        if a['number'] not in seen:
            seen[a['number']] = a
    return sorted(seen.values(), key=lambda x: x['number'])


def get_page_dimensions(pdf_path, skip_pages=0):
    dims = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            if page_num < skip_pages:
                continue
            new_idx = page_num - skip_pages
            dims[new_idx] = {"width": page.width, "height": page.height}
    return dims


def extract_year(name):
    m = re.search(r'(\d{4})', name)
    return m.group(1) if m else None


# ================= 处理单个 PDF =================
def process_pdf(pdf_path, output_type="questions"):
    year = extract_year(pdf_path.stem)
    if not year:
        print(f"  ⚠️ 跳过 {pdf_path.name}: 文件名中找不到年份")
        return None

    skip = detect_skip_pages(pdf_path)
    print(f"  📄 解析 {output_type}: {pdf_path.name} -> {year}")
    print(f"    🔍 跳过前 {skip} 页 | 分辨率 {RESOLUTION} DPI | 格式 {IMAGE_FORMAT.upper()}")

    base_dir = OUTPUT_BASE_DIR / year
    images_dir = base_dir / output_type

    image_paths = convert_pdf_to_images(pdf_path, images_dir, skip_pages=skip)
    anchors = extract_anchors(pdf_path, skip_pages=skip)
    page_dims = get_page_dimensions(pdf_path, skip_pages=skip)

    print(f"    ✅ 切图 {len(image_paths)} 页，找到 {len(anchors)} 道题")

    return {
        "year": year,
        "anchors": anchors,
        "page_dimensions": page_dims,
        "image_paths": image_paths
    }


# ================= 主流程 =================
def main():
    question_data = {}
    solution_data = {}

    if PDF_QUESTIONS_DIR.exists():
        for pdf_path in sorted(PDF_QUESTIONS_DIR.glob("*.pdf")):
            res = process_pdf(pdf_path, "questions")
            if res:
                question_data[res["year"]] = res

    if PDF_SOLUTIONS_DIR.exists():
        for pdf_path in sorted(PDF_SOLUTIONS_DIR.glob("*.pdf")):
            res = process_pdf(pdf_path, "solutions")
            if res:
                solution_data[res["year"]] = res

    all_years = set(question_data.keys()) | set(solution_data.keys())
    for year in sorted(all_years):
        base_dir = OUTPUT_BASE_DIR / year
        base_dir.mkdir(parents=True, exist_ok=True)

        q = question_data.get(year, {})
        s = solution_data.get(year, {})

        metadata = {
            "year": year,
            "questions": q.get("anchors", []),
            "solutions": s.get("anchors", []),
            "page_dimensions": q.get("page_dimensions", {}),
            "question_images": q.get("image_paths", {}),
            "solution_images": s.get("image_paths", {})
        }

        metadata_path = base_dir / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 已生成: {metadata_path}")


if __name__ == "__main__":
    main()