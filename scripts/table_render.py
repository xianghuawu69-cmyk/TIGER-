import csv, io, sys
from pathlib import Path
from table_codec import read_delimited, serialize_rows, text_cells

source, output, translation = map(Path, sys.argv[1:4])
text = translation.read_text(encoding='utf-8')
if source.suffix.lower() == '.xlsx':
    import openpyxl
    wb = openpyxl.load_workbook(source)
    cells = list(text_cells(wb))
    lines = text.splitlines()
    if len(lines) != len(cells):
        raise ValueError(f'表格译文单元数不一致：需要 {len(cells)}，收到 {len(lines)}；未生成错位文件，请重新翻译。')
    for cell, value in zip(cells, lines):
        cell.value = value
        cell.data_type = 's'  # Translated prose must never become an executable formula.
    wb.save(output)
else:
    rows, delim = read_delimited(source)
    translated = list(csv.reader(io.StringIO(text, newline=''), delimiter=delim))
    if len(rows) != len(translated) or any(len(a) != len(b) for a,b in zip(rows, translated)):
        raise ValueError('表格译文行列数与原文不一致；未生成错位文件，请重新翻译。')
    for row, target in zip(rows, translated):
        for j, value in enumerate(row):
            if value.strip(): row[j] = target[j]
    output.write_text(serialize_rows(rows, delim), encoding='utf-8-sig')
