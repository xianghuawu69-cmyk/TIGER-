import html, re, sys, zipfile
from pathlib import Path

def main():
    source, output, translation = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    course_bilingual = len(sys.argv) > 4 and sys.argv[4] == "course-bilingual"
    translated = Path(translation).read_text(encoding="utf-8")
    if not source.exists() or source.suffix.lower() != ".docx" or not zipfile.is_zipfile(source):
        # Generic Word delivery for formats whose native writer is not yet
        # available. Keep page/unit markers and the complete translated text.
        from zipfile import ZIP_DEFLATED
        safe = html.escape(translated.replace("\r\n", "\n"), quote=False)
        paragraphs = "".join(f"<w:p><w:r><w:t xml:space=\"preserve\">{html.escape(line, quote=False)}</w:t></w:r></w:p>" for line in safe.split("\n"))
        document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{paragraphs}<w:sectPr/></w:body></w:document>'''.encode("utf-8")
        content_types = b'''<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'''
        rels = b'''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''
        with zipfile.ZipFile(output, "w", ZIP_DEFLATED) as zout:
            zout.writestr("[Content_Types].xml", content_types); zout.writestr("_rels/.rels", rels); zout.writestr("word/document.xml", document)
        return
    lines = [line for line in translated.splitlines() if line.strip()]
    if course_bilingual and False:
        # Course delivery uses independent source/target blocks. Keep each
        # translated line in its own Word paragraph; never inject it into the
        # source table/paragraph node where it could merge with the original.
        from zipfile import ZIP_DEFLATED
        safe_lines = []
        for line in lines:
            clean = re.sub(r"\[\[(?:TG_[A-Z_]+|PAGE\s*\d+)[^\]]*\]\]", "", line)
            clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", clean).replace("�", "")
            safe_lines.append(f'<w:p><w:r><w:t xml:space="preserve">{html.escape(clean, quote=False)}</w:t></w:r></w:p>')
        document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{"".join(safe_lines)}<w:sectPr/></w:body></w:document>'''.encode("utf-8")
        content_types = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'''
        rels = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''
        with zipfile.ZipFile(output, "w", ZIP_DEFLATED) as zout:
            zout.writestr("[Content_Types].xml", content_types); zout.writestr("_rels/.rels", rels); zout.writestr("word/document.xml", document)
        return
    with zipfile.ZipFile(source, "r") as zin:
        parts = {name: zin.read(name) for name in zin.namelist()}
    xml = parts.get("word/document.xml", b"").decode("utf-8", "replace")
    if course_bilingual:
        # Course source tables are immutable. Never inject bilingual lines into
        # their cells, which can fuse adjacent lessons/tables and alter layout.
        # Preserve the complete source document, then append the full bilingual
        # stream as independent paragraphs before the section properties.
        appended = []
        for line in lines:
            clean = re.sub(r"\[\[(?:TG_[A-Z_]+|PAGE\s*\d+)[^\]]*\]\]", "", line)
            clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", clean).replace("�", "")
            appended.append(f'<w:p><w:r><w:t xml:space="preserve">{html.escape(clean, quote=False)}</w:t></w:r></w:p>')
        insertion = "".join(appended)
        position = xml.find("<w:sectPr")
        xml = xml[:position] + insertion + xml[position:] if position >= 0 else xml + insertion
        parts["word/document.xml"] = xml.encode("utf-8")
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
            for name, data in parts.items(): zout.writestr(name, data)
        return
    paragraphs = list(re.finditer(r"<w:p(?:\s[^>]*)?>.*?</w:p>", xml, re.S))
    if not paragraphs:
        raise ValueError("DOCX 没有可回写的正文段落")
    cursor = 0
    out = []
    last = 0
    for match in paragraphs:
        block = match.group(0)
        text_nodes = list(re.finditer(r"<w:t([^>]*)>.*?</w:t>", block, re.S))
        if not text_nodes or cursor >= len(lines):
            continue
        clean_line = re.sub(r"\[\[(?:TG_[A-Z_]+|PAGE\s*\d+)[^\]]*\]\]", "", lines[cursor])
        clean_line = re.sub(r"^\s*#{1,6}\s*[•·]?\s*", "", clean_line)
        # Remove leaked markdown-like prefixes only when they touch prose;
        # keep legitimate hashtags, issue numbers, code and URLs intact.
        clean_line = re.sub(r"(?<![A-Za-z0-9_])#{1,6}(?=[A-Za-z\u3400-\u9fff])", "", clean_line)
        clean_line = re.sub(r"[•·]{2,}(?=\s|$)", "", clean_line)
        clean_line = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", clean_line)
        clean_line = clean_line.replace("�", "")
        value = html.escape(clean_line, quote=False)
        first = text_nodes[0]
        # Keep every original run, run property, drawing and paragraph node.
        # Put translated text in the first run and blank only the old text
        # payloads; this preserves Word styles, tables and inline layout.
        attrs = re.sub(r'\s+xml:space="[^"]*"', '', first.group(1))
        replacement = f"<w:t{attrs} xml:space=\"preserve\">{value}</w:t>"
        block = block[:first.start()] + replacement + block[first.end():]
        # offsets changed after the first replacement, so locate remaining
        # text nodes again and clear their payload without removing the runs.
        remaining = list(re.finditer(r"<w:t([^>]*)>.*?</w:t>", block, re.S))[1:]
        for node in reversed(remaining):
            attrs = re.sub(r'\s+xml:space="[^"]*"', '', node.group(1))
            empty = f"<w:t{attrs} xml:space=\"preserve\"></w:t>"
            block = block[:node.start()] + empty + block[node.end():]
        out.append((match.start(), match.end(), block))
        cursor += 1
    for start, end, block in reversed(out):
        xml = xml[:start] + block + xml[end:]
    # Never drop translated units when bilingual output has more lines than
    # source paragraphs. Append overflow as separate paragraphs before sectPr;
    # the original document structure and every original paragraph remain.
    if cursor < len(lines):
        overflow = []
        for line in lines[cursor:]:
            clean = re.sub(r"\[\[(?:TG_[A-Z_]+|PAGE\s*\d+)[^\]]*\]\]", "", line)
            clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", clean).replace("�", "")
            overflow.append(f'<w:p><w:r><w:t xml:space="preserve">{html.escape(clean, quote=False)}</w:t></w:r></w:p>')
        insertion = "".join(overflow)
        marker = "<w:sectPr"
        position = xml.find(marker)
        if position >= 0:
            xml = xml[:position] + insertion + xml[position:]
        else:
            xml += insertion
    parts["word/document.xml"] = xml.encode("utf-8")
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in parts.items(): zout.writestr(name, data)

if __name__ == "__main__": main()
