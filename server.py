"""Tiger document service: Word / PDF / image / table preflight and render.

Mirrors the original /api/documents/* contracts. The web app forwards the
browser's multipart request here with `Authorization: Bearer DOCUMENT_SERVICE_SECRET`.
"""
import hmac
import json
import os
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
MB = 1024 * 1024
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
MIME = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "bmp": "image/bmp", "tif": "image/tiff", "tiff": "image/tiff", "png": "image/png",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "csv": "text/csv; charset=utf-8", "tsv": "text/tab-separated-values; charset=utf-8"}

app = FastAPI(title="Tiger Document Service", docs_url=None, redoc_url=None)


@app.middleware("http")
async def require_secret(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    secret = os.environ.get("DOCUMENT_SERVICE_SECRET", "").strip()
    supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not secret or not hmac.compare_digest(secret, supplied):
        return JSONResponse({"error": "未授权"}, status_code=401)
    return await call_next(request)


@app.get("/health")
def health():
    return {"ok": True}


def err(message, status=400, **extra):
    return JSONResponse({"error": message, **extra}, status_code=status)


def run(script, *args, timeout=120):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)], capture_output=True, text=True, encoding="utf-8", timeout=timeout, env=env)
    if proc.returncode not in (0, 2, 3):
        raise RuntimeError((proc.stderr or "处理失败").strip().splitlines()[-1][:300])
    return proc.stdout


def ext_of(name):
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


async def save(file: UploadFile, folder: Path, stem: str):
    data = await file.read()
    path = folder / f"{stem}.{ext_of(file.filename or '')}"
    path.write_bytes(data)
    return path, data


@app.post("/api/documents/docx/preflight")
async def docx_preflight(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".docx"):
        return err("请上传有效的 DOCX 文件。")
    with tempfile.TemporaryDirectory(prefix="tiger-docx-") as d:
        path, data = await save(file, Path(d), "input")
        if not 1 <= len(data) <= 50 * MB:
            return err("DOCX 在线预检支持 1 字节至 50 MB。", 413)
        if data[:2] != b"PK":
            return err("文件内容不是有效的 DOCX。")
        result = json.loads(run("docx_preflight.py", path))
    if result.get("error"):
        return JSONResponse(result, status_code=400)
    result.setdefault("warnings", [])
    if result.get("numberingNormalizationPassed") is False:
        result["warnings"].append("自动编号存在语言模板差异，已保留文档正文并在输出复核中提示。")
    return result


@app.post("/api/documents/docx/render")
async def docx_render(translation: str = Form(""), courseBilingual: str = Form(""), file: UploadFile | None = File(None)):
    if not translation:
        return err("Word 输出内容为空")
    with tempfile.TemporaryDirectory(prefix="tiger-docx-render-") as d:
        d = Path(d)
        source, output, text = d / "source.docx", d / "translated.docx", d / "translation.txt"
        source.write_bytes(await file.read() if file else b"")
        text.write_text(translation, encoding="utf-8")
        run("docx_render.py", source, output, text, "course-bilingual" if courseBilingual == "1" else "standard")
        with zipfile.ZipFile(output) as z:
            names = z.namelist()
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise RuntimeError("生成的 Word 文件结构无效")
            ET.fromstring(z.read("word/document.xml"))
        body = output.read_bytes()
    return Response(body, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": 'attachment; filename="translated.docx"'})


@app.post("/api/documents/pdf/preflight")
async def pdf_preflight(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        return err("请上传有效的 PDF 文件。")
    with tempfile.TemporaryDirectory(prefix="tiger-pdf-") as d:
        path, data = await save(file, Path(d), "input")
        if not 1 <= len(data) <= 50 * MB:
            return err("PDF 预检支持 1 字节至 50 MB。", 413)
        if data[:5] != b"%PDF-":
            return err("文件内容不是有效的 PDF。")
        result = json.loads(run("pdf_preflight.py", path))
    if result.get("extractable") is False and result.get("scannedPages"):
        result["warnings"] = [*result.get("warnings", []), "扫描页 OCR 未提取到文字；请确认 PDF 页面清晰、未被 DRM 保护。"]
    if result.get("error"):
        return JSONResponse(result, status_code=422 if result.get("encrypted") else 400)
    return result


@app.post("/api/documents/image/preflight")
async def image_preflight(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(IMAGE_EXT):
        return err("请上传 PNG、JPG、WEBP、BMP 或 TIFF 图片。")
    with tempfile.TemporaryDirectory(prefix="tiger-image-") as d:
        path, data = await save(file, Path(d), "source")
        if not 1 <= len(data) <= 100 * MB:
            return err("图片 OCR 支持 1 字节至 100 MB。", 413)
        result = json.loads(run("image_preflight.py", path, timeout=150))
    if result.get("error"):
        return JSONResponse({**result, "ocrAvailable": False}, status_code=400)
    return {**result, "formatPolicy": "ocr_reading_order_locked"}


@app.post("/api/documents/image/render")
async def image_render(translation: str = Form(""), file: UploadFile = File(...)):
    name = file.filename or ""
    if not translation.strip():
        return err("图片原文件或译文为空。")
    if not name.lower().endswith(IMAGE_EXT):
        return err("仅支持 PNG、JPG、WEBP、BMP、TIFF 图片回写。")
    ext = ext_of(name)
    with tempfile.TemporaryDirectory(prefix="tiger-image-render-") as d:
        d = Path(d)
        source, data = await save(file, d, "source")
        if not 1 <= len(data) <= 100 * MB or len(translation) > 4_000_000:
            return err("图片或译文超过大小限制。", 413)
        output, text = d / f"translated.{ext}", d / "translation.txt"
        text.write_text(translation, encoding="utf-8")
        run("image_render.py", source, output, text)
        body = output.read_bytes()
    return Response(body, media_type=MIME.get(ext, "image/png"), headers={"Content-Disposition": f'attachment; filename="translated.{ext}"'})


@app.post("/api/documents/table/preflight")
async def table_preflight(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith((".csv", ".tsv", ".xlsx")):
        return err("请上传 CSV、TSV 或 XLSX 文件。")
    with tempfile.TemporaryDirectory(prefix="tiger-table-") as d:
        path, data = await save(file, Path(d), "source")
        if not 1 <= len(data) <= 50 * MB:
            return err("表格文件支持 1 字节至 50 MB。", 413)
        result = json.loads(run("table_preflight.py", path))
        if result.get("error"):
            return JSONResponse(result, status_code=422)
        return result


@app.post("/api/documents/table/render")
async def table_render(translation: str = Form(""), file: UploadFile = File(...)):
    name = file.filename or ""
    if not translation.strip():
        return err("表格原文件或译文为空。")
    if not name.lower().endswith((".csv", ".tsv", ".xlsx")):
        return err("仅支持 CSV、TSV、XLSX 表格回写。")
    ext = ext_of(name)
    with tempfile.TemporaryDirectory(prefix="tiger-table-render-") as d:
        d = Path(d)
        source, data = await save(file, d, "source")
        if not 1 <= len(data) <= 50 * MB:
            return err("表格文件超过大小限制。", 413)
        output, text = d / f"translated.{ext}", d / "translation.txt"
        text.write_text(translation, encoding="utf-8")
        run("table_render.py", source, output, text)
        body = output.read_bytes()
    return Response(body, media_type=MIME[ext], headers={"Content-Disposition": f'attachment; filename="translated.{ext}"'})


@app.exception_handler(Exception)
async def crash(_request, exc):
    return JSONResponse({"error": str(exc)[:300] or "文档处理失败"}, status_code=500)
