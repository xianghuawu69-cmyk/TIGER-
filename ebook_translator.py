"""Minimal helpers used by scripts/docx_preflight.py.

The original desktop `ebook_translator` module was not included in the migration
package; these functions reproduce the behaviour the web preflight relies on.
"""
import html
import re

_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")

_CN_NUMBERING = {
    "第%1章": "Chapter %1", "第%1节": "Section %1", "第%1条": "Article %1",
    "第%1部分": "Part %1", "第%1篇": "Part %1", "第%1页": "Page %1",
    "（%1）": "(%1)", "%1、": "%1.", "%1．": "%1.", "【%1】": "[%1]",
}


def decode_xml_payload(raw: bytes):
    for encoding in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8"


def localize_word_numbering(numbering_xml: str, target_language: str) -> str:
    if not target_language.lower().startswith("en"):
        return numbering_xml

    def replace(match):
        value = html.unescape(match.group(2))
        localized = _CN_NUMBERING.get(value)
        if localized is None:
            localized = _CJK.sub("", value).strip() or "%1."
        return f'{match.group(1)}{html.escape(localized, quote=True)}"'

    xml = re.sub(r'(<w:lvlText[^>]*w:val=")([^"]*)"', replace, numbering_xml)
    # Chinese counting formats become decimal for English output.
    return re.sub(r'(<w:numFmt[^>]*w:val=")(chineseCounting\w*|ideograph\w*|japaneseCounting)"', r'\1decimal"', xml)


def docx_visible_cjk_samples(parts: dict, limit: int = 20):
    samples = []
    for raw in parts.values():
        text = decode_xml_payload(raw)[0] if isinstance(raw, (bytes, bytearray)) else str(raw)
        for value in re.findall(r'w:val="([^"]*)"|<w:t(?:\s[^>]*)?>(.*?)</w:t>', text, flags=re.S):
            candidate = html.unescape(value[0] or value[1])
            if _CJK.search(candidate):
                samples.append(candidate)
                if len(samples) >= limit:
                    return samples
    return samples
