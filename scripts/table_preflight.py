import json, sys
from pathlib import Path
from table_codec import read_delimited, serialize_rows, text_cells
def main():
    p=Path(sys.argv[1]); ext=p.suffix.lower()
    if ext in ('.csv','.tsv'):
        rows, delim=read_delimited(p); cols=max((len(r) for r in rows),default=0)
        extracted=serialize_rows(rows, delim)
        print(json.dumps({'text':extracted,'rows':len(rows),'columns':cols,'format':ext[1:],'replacementCharacters':extracted.count('�'),'formatPolicy':'table_cells_locked','warnings':[]},ensure_ascii=False)); return
    import openpyxl
    wb=openpyxl.load_workbook(p, data_only=False)
    cells=list(text_cells(wb))
    if any('\n' in cell.value or '\r' in cell.value for cell in cells):
        print(json.dumps({'error':'XLSX 含多行单元格；请先拆分单元格内换行后重试，以避免译文错位。'},ensure_ascii=False)); return
    text='\n'.join(cell.value for cell in cells)
    print(json.dumps({'text':text,'rows':sum(ws.max_row for ws in wb.worksheets),'columns':max((ws.max_column for ws in wb.worksheets),default=0),'translationUnits':len(cells),'format':'xlsx','replacementCharacters':text.count('�'),'formatPolicy':'table_cells_locked','warnings':['公式、数字、日期与空单元格已冻结；文本按工作表和单元格顺序翻译。']},ensure_ascii=False))
if __name__=='__main__': main()
