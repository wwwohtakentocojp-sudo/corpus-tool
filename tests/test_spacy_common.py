from analyzers.spacy_common import split_chunks


def test_split_chunks_short_text_untouched():
    assert split_chunks("abc", max_chars=10) == ["abc"]


def test_split_chunks_by_paragraph_then_line_then_space():
    paras = ["a" * 40, "b" * 40, "c" * 40]
    chunks = split_chunks("\n\n".join(paras), max_chars=90)
    assert all(len(c) <= 90 for c in chunks)
    assert "".join(chunks).replace("\n", "") == "".join(paras)

    # 空行が無い長文（Leipzig の文ファイルのような形）でも上限を超えない
    lines = ["x" * 30 for _ in range(10)]
    chunks = split_chunks("\n".join(lines), max_chars=70)
    assert all(len(c) <= 70 for c in chunks)
    assert sum(c.count("x") for c in chunks) == 300

    # 1行が上限を超える場合は空白で切る
    long_line = " ".join(["word"] * 50)
    chunks = split_chunks(long_line, max_chars=60)
    assert all(len(c) <= 60 for c in chunks)
    assert " ".join(c.strip() for c in chunks).split() == ["word"] * 50
