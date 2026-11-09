from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

out = str(Path(__file__).resolve().parents[1] / '课件翻译测试样本_基础英语.docx')
doc = Document()
sec = doc.sections[0]
sec.top_margin = Inches(0.8); sec.bottom_margin = Inches(0.8); sec.left_margin = Inches(0.9); sec.right_margin = Inches(0.9)
styles = doc.styles
normal = styles['Normal']; normal.font.name = 'Calibri'; normal.font.size = Pt(11)
normal.paragraph_format.space_after = Pt(6); normal.paragraph_format.line_spacing = 1.25
for name, size, color in [('Title', 24, '1F4D78'), ('Heading 1', 16, '2E74B5'), ('Heading 2', 13, '2E74B5'), ('Heading 3', 12, '1F4D78')]:
    s = styles[name]; s.font.name = 'Calibri'; s.font.size = Pt(size); s.font.color.rgb = RGBColor.from_string(color)

def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement('w:shd'); shd.set(qn('w:fill'), fill); tcPr.append(shd)

def add_bullet(text):
    doc.add_paragraph(text, style='List Bullet')

title = doc.add_paragraph(style='Title'); title.alignment = WD_ALIGN_PARAGRAPH.CENTER; title.add_run('基础英语：从字母到句子').bold = True
sub = doc.add_paragraph(); sub.alignment = WD_ALIGN_PARAGRAPH.CENTER; sub.add_run('课件翻译测试样本｜正文、字母讲解、习题与解析').italic = True
doc.add_paragraph('教学目标', style='Heading 1')
doc.add_paragraph('完成本单元后，学习者能够识别英文字母，理解元音与辅音的基本区别，并用简单句介绍自己。教师可将正文、讲解、习题和解析分别路由到不同目标语言。')

doc.add_paragraph('一、正文：认识字母与问候', style='Heading 1')
doc.add_paragraph('英语字母表共有 26 个字母，分为大写和小写两种形式。字母是构成单词的基本单位，单词组合成短语和句子。学习时应注意字母的书写方向、大小写和发音。')
doc.add_paragraph('Hello! My name is Lina. I am a student. I like reading and music. Nice to meet you.')
doc.add_paragraph('你好！我叫莉娜。我是一名学生。我喜欢阅读和音乐。很高兴认识你。', style='Intense Quote')

doc.add_paragraph('二、字母与讲解', style='Heading 1')
table = doc.add_table(rows=1, cols=4); table.alignment = WD_TABLE_ALIGNMENT.CENTER; table.style = 'Table Grid'
headers = ['字母', '名称', '示例单词', '讲解']
for i, h in enumerate(headers):
    c = table.rows[0].cells[i]; c.text = h; shade(c, 'E8EEF5'); c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
rows = [
    ('A a', 'A', 'apple', 'A 是元音字母，常见发音包括 /æ/。'),
    ('B b', 'B', 'book', 'B 是辅音字母，发音时双唇先闭合再打开。'),
    ('C c', 'C', 'cat', 'C 在 cat 中发 /k/ 音，在 city 中可能发 /s/ 音。'),
    ('E e', 'E', 'egg', 'E 是元音字母，注意短音和长音的区别。'),
    ('M m', 'M', 'music', 'M 是辅音字母，发音时双唇闭合并振动声带。'),
]
for row in rows:
    cells = table.add_row().cells
    for i, value in enumerate(row): cells[i].text = value

doc.add_paragraph('三、课堂活动', style='Heading 1')
for text in ['教师朗读 A、B、C、E、M，学生跟读并指出大小写。', '学生两人一组，用英文完成自我介绍。', '教师展示 apple、book、cat、egg、music 图片或卡片，让学生匹配单词。']:
    add_bullet(text)

doc.add_paragraph('四、习题', style='Heading 1')
doc.add_paragraph('1. 选择题：下列哪一个是元音字母？\nA. B    B. C    C. E    D. M')
doc.add_paragraph('2. 填空题：补全句子：My name ___ Lina.')
doc.add_paragraph('3. 连线题：将字母与单词连线：A—apple；B—book；M—music。')
doc.add_paragraph('4. 输出题：用两句话介绍你的姓名和一个兴趣。')

doc.add_paragraph('五、习题解析', style='Heading 1')
doc.add_paragraph('第 1 题答案：C。E 是元音字母，B、C、M 是辅音字母。')
doc.add_paragraph('第 2 题答案：is。完整句子为 “My name is Lina.”')
doc.add_paragraph('第 3 题解析：A 对应 apple，B 对应 book，M 对应 music；先看首字母，再核对单词含义。')
doc.add_paragraph('第 4 题示例：My name is Wei. I like music. 评分重点是句子完整、首字母大写和句末标点。')

doc.add_paragraph('教师备注（可选择保持原文或单独翻译）', style='Heading 2')
doc.add_paragraph('本样本用于测试课程单元错位翻译：正文、字母讲解、习题、解析和教师备注应保持单元边界；教师可为不同类别选择不同目标语言，或保留原文对照。')
doc.save(out)
print(out)
