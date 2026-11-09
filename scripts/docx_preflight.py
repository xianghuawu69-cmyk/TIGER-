import html
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ebook_translator as translator


def count(pattern, text):
    return len(re.findall(pattern, text, flags=re.I | re.S))


def main():
    path = Path(sys.argv[1])
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise ValueError("文件不是有效的 DOCX 文档。")
            parts = {
                name: translator.decode_xml_payload(archive.read(name))[0]
                for name in names
                if name.endswith(".xml") and (name.startswith("word/") or name.startswith("docProps/"))
            }
    except (zipfile.BadZipFile, KeyError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 2

    word_xml = "\n".join(value for name, value in parts.items() if name.startswith("word/"))
    visible_parts = [
        html.unescape(value)
        for pattern in (r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", r"<a:t(?:\s[^>]*)?>(.*?)</a:t>")
        for value in re.findall(pattern, word_xml, flags=re.S)
    ]
    visible_text = "\n".join(part for part in visible_parts if part.strip())
    numbering = parts.get("word/numbering.xml", "")
    numbering_templates = [html.unescape(value) for value in re.findall(r'<w:lvlText[^>]*w:val="([^"]+)"', numbering)]
    cjk_numbering = [value for value in numbering_templates if re.search(r"[\u3400-\u9fff]", value)]
    normalized_numbering = translator.localize_word_numbering(numbering, "English") if numbering else ""
    normalized_leftovers = translator.docx_visible_cjk_samples(
        {"word/numbering.xml": normalized_numbering.encode("utf-8")}
    ) if normalized_numbering else []
    warnings = []
    if cjk_numbering:
        warnings.append(f"检测到 {len(cjk_numbering)} 个中文自动编号模板；英文任务会在输出前自动本地化。")
    if normalized_leftovers:
        warnings.append("自动编号仍包含目标语言之外文字，任务启动前需要阻止并修复。")
    replacement_chars = visible_text.count("�")
    if replacement_chars:
        warnings.append(f"检测到 {replacement_chars} 个损坏字符，需要先修复源文件编码。")

    print(json.dumps({
        "text": visible_text,
        "characters": len(re.sub(r"\s+", "", visible_text)),
        "paragraphs": count(r"<w:p(?:\s|>)", word_xml),
        "textRuns": count(r"<w:t(?:\s|>)", word_xml),
        "tables": count(r"<w:tbl(?:\s|>)", word_xml),
        "drawings": count(r"<w:drawing(?:\s|>)", word_xml),
        "headers": len([name for name in names if re.fullmatch(r"word/header\d+\.xml", name)]),
        "footers": len([name for name in names if re.fullmatch(r"word/footer\d+\.xml", name)]),
        "footnotes": "word/footnotes.xml" in names,
        "endnotes": "word/endnotes.xml" in names,
        "comments": any(name.startswith("word/comments") and name.endswith(".xml") for name in names),
        "equations": count(r"<m:oMath(?:\s|>)", word_xml),
        "numberingTemplates": len(numbering_templates),
        "cjkNumberingTemplates": len(cjk_numbering),
        "numberingNormalizationPassed": not normalized_leftovers,
        "replacementCharacters": replacement_chars,
        "warnings": warnings,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
