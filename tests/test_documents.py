import csv
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import openpyxl
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import app


def script(name, *args, env=None):
    return subprocess.run([sys.executable, str(ROOT / 'scripts' / name), *map(str, args)],
                          capture_output=True, text=True, env=env)


def test_xlsx_extracts_inline_strings_and_freezes_formulas(tmp_path):
    path = tmp_path / 'source.xlsx'
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['中文 & 商品', 42, '=B1*2', None, '说明'])
    wb.create_sheet('第二页').append(['尾页'])
    wb.save(path)
    result = json.loads(script('table_preflight.py', path).stdout)
    assert result['text'] == '中文 & 商品\n说明\n尾页'
    assert result['translationUnits'] == 3
    text = tmp_path / 'target.txt'
    text.write_text('Product & name\n\nFinal', encoding='utf-8')
    output = tmp_path / 'target.xlsx'
    assert script('table_render.py', path, output, text).returncode == 0
    rendered = openpyxl.load_workbook(output)
    assert rendered.active['A1'].value == 'Product & name'
    assert rendered.active['B1'].value == 42
    assert rendered.active['C1'].value == '=B1*2'
    assert rendered.active['E1'].value is None
    assert rendered['第二页']['A1'].value == 'Final'


def test_xlsx_rejects_missing_units_and_locks_translated_formulas(tmp_path):
    path, text, output = (tmp_path / x for x in ['source.xlsx', 'target.txt', 'target.xlsx'])
    wb = openpyxl.Workbook(); wb.active.append(['一', '二']); wb.save(path)
    text.write_text('Only one', encoding='utf-8')
    assert script('table_render.py', path, output, text).returncode != 0
    assert not output.exists()
    text.write_text('=HYPERLINK("unsafe")\nSecond', encoding='utf-8')
    assert script('table_render.py', path, output, text).returncode == 0
    assert openpyxl.load_workbook(output).active['A1'].data_type == 's'


def test_csv_roundtrip_preserves_quoted_multiline_and_empty_cells(tmp_path):
    source, text, output = (tmp_path / x for x in ['source.csv', 'target.txt', 'target.csv'])
    source.write_text('"商品,名称",,"第一行\n第二行"\n说明,备注,结尾\n', encoding='utf-8')
    preflight = json.loads(script('table_preflight.py', source).stdout)
    assert list(csv.reader(io.StringIO(preflight['text']))) == [['商品,名称', '', '第一行\n第二行'], ['说明','备注','结尾']]
    text.write_text('"Product,name",,"Line one\nLine two"\nDescription,,End\n', encoding='utf-8')
    assert script('table_render.py', source, output, text).returncode == 0
    with output.open(encoding='utf-8-sig', newline='') as stream:
        assert list(csv.reader(stream)) == [['Product,name', '', 'Line one\nLine two'], ['Description', '', 'End']]
    text.write_text('Wrong,shape\n', encoding='utf-8')
    assert script('table_render.py', source, tmp_path / 'invalid.csv', text).returncode != 0


def test_encrypted_pdf_returns_validation_error_and_service_requires_secret(tmp_path, monkeypatch):
    writer = PdfWriter(); writer.add_blank_page(width=100, height=100); writer.encrypt('protected')
    pdf = tmp_path / 'encrypted.pdf'
    with pdf.open('wb') as stream: writer.write(stream)
    monkeypatch.setenv('DOCUMENT_SERVICE_SECRET', 'test-only-document-secret')
    with TestClient(app) as client:
        assert client.get('/health').json() == {'ok': True}
        assert client.post('/api/documents/pdf/preflight', files={'file': ('encrypted.pdf', pdf.read_bytes())}).status_code == 401
        response = client.post('/api/documents/pdf/preflight', headers={'Authorization':'Bearer test-only-document-secret'}, files={'file': ('encrypted.pdf', pdf.read_bytes())})
        assert response.status_code == 422
        assert response.json()['encrypted'] is True


def test_mixed_pdf_does_not_claim_unresolved_pages_are_complete(tmp_path):
    pdf = tmp_path / 'mixed.pdf'
    c = canvas.Canvas(str(pdf)); c.drawString(40, 800, 'This page has reliably extractable source text.'); c.showPage(); c.showPage(); c.save()
    env = {**os.environ, 'PATH': '', 'TESSERACT_EXECUTABLE': '/missing', 'PDFTOPPM_EXECUTABLE': '/missing'}
    result = json.loads(script('pdf_preflight.py', pdf, env=env).stdout)
    assert result['extractable'] is False
    assert result['partialExtraction'] is True
    assert result['unresolvedPages'] == [2]
    assert result['pages'][0]['extractionStatus'] == 'text'
    assert result['pages'][1]['extractionStatus'] == 'unresolved'


def test_image_rejects_overflow_and_preserves_tiff_dimensions(tmp_path):
    source, text, output = (tmp_path / x for x in ['source.tif', 'target.txt', 'target.tif'])
    Image.new('RGB', (640, 480), 'white').save(source)
    text.write_text('too much text\n' * 100, encoding='utf-8')
    env = {**os.environ, 'TIGER_IMAGE_FONT':'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'}
    result = script('image_render.py', source, output, text, env=env)
    assert result.returncode != 0
    assert '未生成截断图片' in result.stderr
    assert not output.exists()
    text.write_text('Translated image', encoding='utf-8')
    assert script('image_render.py', source, output, text, env=env).returncode == 0
    with Image.open(output) as im:
        assert im.size == (640, 480)
        assert im.format == 'TIFF'