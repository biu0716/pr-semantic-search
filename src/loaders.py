from pathlib import Path
from docx import Document
from docx.oxml.ns import qn

# wps 命名空间的完整 URI
# python-docx 默认不注册这个前缀，所以不能用 qn("wps:txbx")
# 直接用完整字符串代替
WPS_TXBX = "{http://schemas.microsoft.com/office/word/2010/wordprocessingShape}txbx"


def _read_textboxes(doc) -> list[str]:
    """
    读取 docx 里的文本框内容。
    用完整命名空间 URI 代替 qn("wps:txbx")，避免 'wps' 未注册报错。
    """
    texts = []
    for txbx in doc.element.body.iter(WPS_TXBX):
        for para in txbx.iter(qn("w:p")):
            text = "".join(t.text for t in para.iter(qn("w:t")) if t.text).strip()
            if text:
                texts.append(text)
    return texts


def read_docx(path: Path) -> str:
    doc = Document(str(path))
    texts = []

    for child in doc.element.body:
        tag = child.tag

        # 段落
        if tag == qn("w:p"):
            text = "".join(
                t.text for t in child.iter(qn("w:t")) if t.text
            ).strip()
            if text:
                texts.append(text)

        # 表格
        elif tag == qn("w:tbl"):
            for row in child.iter(qn("w:tr")):
                row_cells = []
                for cell in row.iter(qn("w:tc")):
                    cell_text = "".join(
                        t.text for t in cell.iter(qn("w:t")) if t.text
                    ).strip()
                    if cell_text:
                        row_cells.append(cell_text)
                if row_cells:
                    texts.append("\t".join(row_cells))

    # 文本框
    textbox_texts = _read_textboxes(doc)
    texts.extend(textbox_texts)

    return "\n".join(texts)