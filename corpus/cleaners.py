"""読み込んだテキストの整形。言語非依存の範囲のみ扱う。

青空文庫形式の注記除去はここに置く（日本語データに多いが、形式は言語ではなく
配布元に固有のものなので analyzers/ には入れない）。
"""
from __future__ import annotations

import re

# 青空文庫の注記
_AOZORA_RUBY = re.compile(r"《[^》]*》")            # ルビ
_AOZORA_RUBY_START = re.compile(r"｜")               # ルビ開始記号
_AOZORA_NOTE = re.compile(r"［＃[^］]*］")            # 編集注記
_AOZORA_SEPARATOR = re.compile(r"^-{10,}\s*$", re.MULTILINE)
_AOZORA_FOOTER = re.compile(r"^(底本：|底本:)", re.MULTILINE)


def looks_like_aozora(text: str) -> bool:
    head = text[:5000]
    return ("《" in head and "》" in head) or "［＃" in head or "底本：" in text[-3000:]


def clean_aozora(text: str) -> str:
    """青空文庫の注記・ルビ・冒頭の凡例・末尾の底本情報を除去する。"""
    # 冒頭の凡例（---- で囲まれた部分）を除去
    seps = list(_AOZORA_SEPARATOR.finditer(text))
    if len(seps) >= 2:
        text = text[: seps[0].start()] + text[seps[1].end():]
    # 末尾の底本情報
    m = _AOZORA_FOOTER.search(text)
    if m:
        text = text[: m.start()]
    text = _AOZORA_NOTE.sub("", text)
    text = _AOZORA_RUBY.sub("", text)
    text = _AOZORA_RUBY_START.sub("", text)
    return text.strip()


def apply_cleaning(text: str, options: dict) -> str:
    if options.get("aozora"):
        text = clean_aozora(text)
    return text
