"""Shared extraction/write-back order; formulas and non-text XLSX cells stay locked."""
import csv
import io


def read_delimited(path):
    delimiter = '\t' if path.suffix.lower() == '.tsv' else ','
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.reader(stream, delimiter=delimiter)), delimiter


def serialize_rows(rows, delimiter):
    stream = io.StringIO(newline='')
    csv.writer(stream, delimiter=delimiter, lineterminator='\n').writerows(rows)
    return stream.getvalue()


def text_cells(workbook):
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if cell.data_type != 'f' and isinstance(cell.value, str) and cell.value.strip():
                    yield cell