import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image
except Exception:
    Image = None

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

def main():
    path = Path(sys.argv[1])
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError("图片格式不支持")
    if Image is None:
        raise RuntimeError("本机缺少 Pillow 图像处理库")
    with Image.open(path) as image:
        width, height = image.size
        image.verify()
    configured_tesseract = os.environ.get("TESSERACT_EXECUTABLE")
    tesseract = configured_tesseract if configured_tesseract and Path(configured_tesseract).is_file() else shutil.which(configured_tesseract or "tesseract")
    if not tesseract:
        raise RuntimeError("本机未安装 OCR 引擎")
    with tempfile.TemporaryDirectory(prefix="tiger-ocr-") as temp:
        output = Path(temp) / "ocr"
        completed = subprocess.run([tesseract, str(path), str(output), "-l", "chi_sim+chi_tra+jpn+eng", "--psm", "3"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or "OCR 识别失败").strip())
        text = output.with_suffix(".txt").read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    warnings = []
    if not text:
        warnings.append("图片未识别到可翻译文字；请确认图片清晰且包含文字")
    if "�" in text:
        warnings.append("OCR 结果包含损坏字符，已保留并进入复核")
    print(json.dumps({"text": text, "characters": len(re.sub(r"\s+", "", text)), "width": width, "height": height, "format": path.suffix[1:].lower(), "ocrAvailable": True, "ocrLanguage": "chi_sim+chi_tra+jpn+eng", "warnings": warnings}, ensure_ascii=False))

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"error": str(error), "ocrAvailable": False}, ensure_ascii=False))
        raise SystemExit(2)
