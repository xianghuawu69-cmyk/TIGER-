import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
source, output, translation = map(Path, sys.argv[1:4])
text = translation.read_text(encoding='utf-8').strip()
with Image.open(source) as im:
    im = im.convert('RGBA'); w,h=im.size
    font_candidates = [
        os.environ.get('TIGER_IMAGE_FONT'),
        str(Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts' / 'msyh.ttc'),
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
    ]
    font_path = next((candidate for candidate in font_candidates if candidate and Path(candidate).is_file()), None)
    if not font_path:
        raise RuntimeError('未找到中文字体，请设置 TIGER_IMAGE_FONT 指向可用的 CJK 字体文件')
    available_width = w - 36
    max_panel = h // 2
    for size in range(max(18, min(42, w//32)), 11, -1):
        font = ImageFont.truetype(font_path, size)
        lines=[]
        for raw in text.splitlines():
            line=''
            for char in raw:
                if font.getlength(char) > available_width:
                    raise ValueError('图片宽度不足以容纳译文；请使用更大的原图。')
                if line and font.getlength(line + char) > available_width:
                    lines.append(line); line=''
                line += char
            lines.append(line)
        line_h=font.size+10
        panel_h=line_h*(len(lines)+1)+28
        if panel_h <= max_panel:
            break
    else:
        raise ValueError('译文超出原图片可容纳范围；未生成截断图片，请缩短译文或使用更大的原图。')
    y=h-panel_h
    overlay=Image.new('RGBA',(w,panel_h),(255,255,255,235)); im.alpha_composite(overlay,(0,y)); draw=ImageDraw.Draw(im)
    draw.text((18,y+14),'译文',font=font,fill=(25,55,75,255))
    for i,line in enumerate(lines): draw.text((18,y+22+(i+1)*line_h),line,font=font,fill=(20,20,20,255))
    ext=source.suffix[1:].lower()
    save_kwargs={'format': {'tif':'TIFF','tiff':'TIFF','jpg':'JPEG','jpeg':'JPEG'}.get(ext, ext.upper())}
    if output.suffix.lower() in ('.jpg','.jpeg'): im.convert('RGB').save(output,quality=95)
    else: im.save(output, **save_kwargs)
