"""PDF の文字取り出しと整形。"""
import io
import zipfile

from corpus.loaders import clean_pdf_text, read_pdf_bytes, read_zip_txt


def _minimal_pdf(lines: list[str]) -> bytes:
    """フォント Helvetica の1ページ PDF を手書きで作る（ASCII のみ）。"""
    content_lines = ["BT", "/F1 12 Tf", "72 720 Td", "14 TL"]
    for i, ln in enumerate(lines):
        esc = ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content_lines.append(f"({esc}) Tj" if i == 0 else f"T* ({esc}) Tj")
    content_lines.append("ET")
    content = "\n".join(content_lines).encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + o + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def test_clean_pdf_text_dehyphenates_and_joins_lines():
    raw = "Die Sprach-\nwissenschaft untersucht\nSprache.\n\n12\n\nZweiter Absatz\nhier."
    out = clean_pdf_text(raw)
    assert "Sprachwissenschaft untersucht Sprache." in out
    assert "\n12\n" not in out and out.count("12") == 0      # ページ番号の行は落ちる
    assert "Zweiter Absatz hier." in out
    assert out.count("\n\n") == 1                             # 段落は2つ


def test_clean_pdf_text_keeps_proper_noun_hyphen():
    assert clean_pdf_text("Nord-\nOstsee") == "Nord- Ostsee"   # 大文字始まりはつながない


def test_clean_pdf_text_japanese_joins_without_space():
    raw = "私はその人を常に\n先生と呼んでいた。\n\n次の段落。"
    out = clean_pdf_text(raw)
    assert "私はその人を常に先生と呼んでいた。" in out
    assert "次の段落。" in out


def test_read_pdf_bytes_extracts_text():
    pdf = _minimal_pdf(["Hello corpus", "linguis-", "tics is fun.", "3"])
    name, text, kind = read_pdf_bytes("paper.pdf", pdf)
    assert name == "paper"
    assert kind.startswith("PDF")
    assert "Hello corpus linguistics is fun." in text
    assert "\n3" not in text


def test_zip_includes_pdf():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.txt", "plain".encode("utf-8"))
        zf.writestr("b.pdf", _minimal_pdf(["From PDF"]))
    out = read_zip_txt(buf.getvalue())
    assert [o[0] for o in out] == ["a", "b"]
    assert "From PDF" in out[1][1]
