import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pdfplumber
from pypdf import PdfReader


def main():
    path = Path(sys.argv[1])
    reader = PdfReader(path)
    if reader.is_encrypted:
        try:
            unlocked = reader.decrypt("")
        except Exception:
            unlocked = 0
        if not unlocked:
            print(json.dumps({"encrypted": True, "error": "PDF 已加密，需要先解除密码保护。"}, ensure_ascii=False))
            return 3

    pages = []
    fonts = set()
    scanned_pages = []
    unresolved_pages = []
    ocr_pages = []
    text_parts = []
    for index, page in enumerate(reader.pages):
        page_fonts = set()

        def visitor(text, _cm, _tm, font_dict, _font_size):
            if text and font_dict:
                name = str(font_dict.get("/BaseFont", "")).lstrip("/")
                if name:
                    page_fonts.add(name)

        text = page.extract_text(visitor_text=visitor) or ""
        normalized = text.strip()
        # Embedded PDF font maps frequently return mojibake/private-use glyphs
        # even when the page has plenty of extracted characters. Treat those
        # pages as OCR candidates instead of sending corrupted text to models.
        corrupt_glyphs = sum(1 for char in normalized if char == "�" or "\ue000" <= char <= "\uf8ff")
        unresolved = not normalized or corrupt_glyphs > 0
        if unresolved:
            unresolved_pages.append(index + 1)
        if len(normalized) < 20 or corrupt_glyphs >= 2 or (len(normalized) > 30 and corrupt_glyphs / max(1, len(normalized)) > 0.02):
            scanned_pages.append(index + 1)
        fonts.update(page_fonts)
        pages.append({"page": index + 1, "characters": len(normalized), "fonts": sorted(page_fonts)[:20], "extractionStatus": "unresolved" if unresolved else "text"})
        text_parts.append(f"[[PAGE {index + 1}]]\n{normalized}")

    table_count = 0
    with pdfplumber.open(path) as document:
        for page in document.pages[:100]:
            try:
                table_count += len(page.find_tables())
            except Exception:
                pass

    extracted = "\n\n".join(text_parts)
    warnings = []
    if any("�" in part or any("\ue000" <= char <= "\uf8ff" for char in part) for part in text_parts):
        warnings.append("检测到 PDF 字体映射异常，已将相关页面转入 OCR，禁止乱码进入翻译。")
    if scanned_pages:
        warnings.append(f"{len(scanned_pages)} 页文字过少，可能是扫描页，需要 OCR。")
    if len(fonts) > 12:
        warnings.append("检测到较多字体，输出时需要字体替代与缺字检查。")
    if table_count:
        warnings.append(f"检测到约 {table_count} 个表格区域，需要按单元格顺序翻译。")

    # Scanned/image-only PDFs must not stop at preflight. Render only pages with
    # too little text and run the local OCR engine, preserving page markers.
    if scanned_pages:
        # Keep this portable: deployments may provide Poppler through PATH or
        # explicitly point at it. Never bake a developer-machine path into the
        # migration package.
        configured_pdftoppm = os.environ.get("PDFTOPPM_EXECUTABLE")
        configured_tesseract = os.environ.get("TESSERACT_EXECUTABLE")
        pdftoppm = configured_pdftoppm if configured_pdftoppm and Path(configured_pdftoppm).is_file() else shutil.which(configured_pdftoppm or "pdftoppm")
        tesseract = configured_tesseract if configured_tesseract and Path(configured_tesseract).is_file() else shutil.which(configured_tesseract or "tesseract")
        if pdftoppm and tesseract:
            with tempfile.TemporaryDirectory(prefix="tiger-pdf-ocr-") as temp:
                for page_number in scanned_pages[:100]:
                    prefix = str(Path(temp) / f"page-{page_number}")
                    rendered = subprocess.run([pdftoppm, "-f", str(page_number), "-l", str(page_number), "-singlefile", "-png", "-r", "180", str(path), prefix], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
                    image_path = Path(prefix + ".png")
                    if rendered.returncode != 0 or not image_path.exists():
                        continue
                    recognized = subprocess.run([tesseract, str(image_path), prefix, "-l", "chi_sim+chi_tra+jpn+eng", "--psm", "3"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
                    txt_path = Path(prefix + ".txt")
                    if recognized.returncode == 0 and txt_path.exists():
                        ocr_text = txt_path.read_text(encoding="utf-8", errors="replace").strip()
                        # OCR replaces a corrupted embedded text layer only
                        # when it produced usable text. Never discard a good
                        # extracted page because OCR was empty or shorter.
                        existing_text = text_parts[page_number - 1].split("\n", 1)[-1].strip()
                        ocr_corrupt = ocr_text.count("�") + sum(1 for char in ocr_text if "\ue000" <= char <= "\uf8ff")
                        if ocr_text and ocr_corrupt == 0 and (not existing_text or len(ocr_text) >= max(8, int(len(existing_text) * 0.35))):
                            text_parts[page_number - 1] = f"[[PAGE {page_number}]]\n{ocr_text}"
                            ocr_pages.append(page_number)
                            if page_number in unresolved_pages:
                                unresolved_pages.remove(page_number)
                            pages[page_number - 1].update(characters=len(ocr_text), extractionStatus="ocr")
            extracted = "\n\n".join(text_parts)
            if ocr_pages:
                warnings.append("扫描页已通过本地 OCR 提取；识别不确定内容会进入翻译复核。")
        else:
            missing = "Poppler (pdftoppm)" if not pdftoppm else "Tesseract"
            warnings.append(f"检测到扫描页，但本机没有 {missing}；请安装后重试。")

    if unresolved_pages:
        warnings.append(f"第 {', '.join(map(str, unresolved_pages))} 页尚未提取到可靠文字；请提供清晰页面或完成 OCR 后重试，避免漏译。")
    has_text = bool(any(part.split("\n", 1)[-1].strip() for part in text_parts))
    print(json.dumps({
        "encrypted": False,
        "pageCount": len(reader.pages),
        "characters": len(extracted),
        "extractable": has_text and not unresolved_pages,
        "partialExtraction": has_text and bool(unresolved_pages),
        "unresolvedPages": unresolved_pages,
        "ocrPages": ocr_pages,
        "scannedPages": scanned_pages,
        "fonts": sorted(fonts)[:80],
        "tableCount": table_count,
        "pages": pages,
        "warnings": warnings,
        "text": extracted[:2_000_000],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
