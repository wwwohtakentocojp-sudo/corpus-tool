from corpus.cleaners import clean_aozora, looks_like_aozora
from corpus.loaders import decode_bytes


def test_clean_aozora_removes_ruby_and_notes():
    text = (
        "こころ\n夏目漱石\n\n"
        "-------------------------------------------------------\n"
        "【テキスト中に現れる記号について】\n"
        "-------------------------------------------------------\n"
        "私《わたくし》はその人を常に先生と呼んでいた。［＃「呼んでいた」は底本では「呼んでゐた」］\n"
        "｜先生《せんせい》は言った。\n"
        "底本：「こころ」新潮文庫\n"
    )
    out = clean_aozora(text)
    assert "《" not in out and "》" not in out
    assert "［＃" not in out
    assert "｜" not in out
    assert "底本" not in out
    assert "テキスト中に現れる記号" not in out
    assert "私はその人を常に先生と呼んでいた。" in out
    assert "先生は言った。" in out


def test_looks_like_aozora():
    assert looks_like_aozora("私《わたくし》は")
    assert not looks_like_aozora("ただの文章です。")


def test_decode_prefers_utf8_then_cp932():
    assert decode_bytes("日本語".encode("utf-8")).encoding == "utf-8"
    assert decode_bytes("日本語".encode("utf-8-sig")).encoding == "utf-8-sig"
    d = decode_bytes("日本語".encode("cp932"))
    assert d.text == "日本語" and d.encoding == "cp932"
