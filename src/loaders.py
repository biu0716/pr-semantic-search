from pathlib import Path
from docx import Document

def read_docx(path: Path) -> str:
    doc = Document(str(path))
    texts = []

    for p in doc.paragraphs:
        if p.text.strip():
            texts.append(p.text.strip())

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    texts.append(cell.text.strip())

    for element in doc.element.body.iter():
        if element.text and element.text.strip():
            texts.append(element.text.strip())

    texts = list(dict.fromkeys(texts))
    return "\n".join(texts)