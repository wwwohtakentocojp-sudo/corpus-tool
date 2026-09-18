import io
import zipfile

import pandas as pd

from corpus.loaders import (
    guess_group_columns,
    guess_text_column,
    read_folder_txt,
    read_table,
    read_zip_txt,
    table_to_documents,
)


def test_read_csv_and_guess_columns():
    csv = (
        "id,year,genre,text\n"
        "1,2000,news,これは長い本文です。とても長い本文です。\n"
        "2,2000,novel,別の本文。\n"
        "3,2020,news,三つ目の本文。\n"
        "4,2020,novel,四つ目の本文。\n"
    )
    df = read_table("data.csv", csv.encode("utf-8"))
    assert list(df.columns) == ["id", "year", "genre", "text"]
    assert guess_text_column(df) == "text"
    # id は行ごとに異なるのでグループ列の候補にしない
    assert guess_group_columns(df, "text") == ["year", "genre"]
    docs = table_to_documents(df, "text", ["year", "genre"], name_col="id")
    assert len(docs) == 4
    assert docs[0].meta == {"year": "2000", "genre": "news"}
    assert docs[1].name == "2"


def test_read_csv_cp932():
    csv = "本文,年\nテスト本文,1999\n".encode("cp932")
    df = read_table("x.csv", csv)
    assert df.iloc[0]["本文"] == "テスト本文"


def test_read_excel_roundtrip():
    src = pd.DataFrame({"text": ["Hallo Welt", "Guten Tag", "Grüezi", "Servus"], "region": ["DE", "DE", "CH", "AT"]})
    buf = io.BytesIO()
    src.to_excel(buf, index=False)
    df = read_table("x.xlsx", buf.getvalue())
    assert df["text"].tolist() == ["Hallo Welt", "Guten Tag", "Grüezi", "Servus"]
    assert guess_group_columns(df, "text") == ["region"]


def test_read_zip_txt_skips_non_txt_and_mac_junk():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("b.txt", "bbb".encode("utf-8"))
        zf.writestr("a.txt", "日本語の本文".encode("cp932"))
        zf.writestr("__MACOSX/._a.txt", b"junk")
        zf.writestr("readme.md", b"nope")
    out = read_zip_txt(buf.getvalue())
    assert [o[0] for o in out] == ["a", "b"]
    assert out[0][1] == "日本語の本文" and out[0][2] == "cp932"


def test_read_folder_txt(tmp_path):
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "y.txt").write_text("y", encoding="utf-8")
    out = read_folder_txt(tmp_path)
    assert sorted(o[0] for o in out) == ["x", "y"]
