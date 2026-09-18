from types import SimpleNamespace

from interpretations.flags import make_flag
from interpretations.narrator import (
    HEADINGS,
    NarrationInput,
    build_user_message,
    fallback_text,
    narrate,
    substitute,
    validate_structure,
)


def _inp(flags=None, screen="collocation"):
    return NarrationInput(
        screen=screen,
        language="ja",
        metrics={"cooccur": 12, "freq_node": 644, "freq_collocate": 30, "mi": 9.8, "t": 3.4, "log_dice": 8.1, "g2": 45.2, "p": 0.0001},
        flags=flags or [],
        placeholders={"WORD": "先生", "COLLOCATE": "奥さん"},
        settings={"window_label": "同一文内"},
    )


def test_substitute_keeps_japanese_natural():
    assert substitute("『{WORD}』という語と『{COLLOCATE}』という語", {"WORD": "先生", "COLLOCATE": "奥さん"}) == "『先生』という語と『奥さん』という語"


def test_user_message_never_contains_actual_words():
    msg = build_user_message(_inp([make_flag("MI_HIGH_LOW_FREQ", mi=9.8, cooccur=12, threshold=20)]))
    assert "先生" not in msg and "奥さん" not in msg
    assert "MI_HIGH_LOW_FREQ" in msg


def test_fallback_has_four_headings_and_all_flags():
    flags = [
        make_flag("MI_HIGH_LOW_FREQ", mi=9.8, cooccur=12, threshold=20),
        make_flag("T_ONLY_FUNCTION_WORD", t=3.4, mi=1.0),
    ]
    text = fallback_text(_inp(flags))
    assert validate_structure(text)
    for f in flags:
        assert f.message in text
    out = narrate(_inp(flags), {}, use_api=False)
    assert out.source == "template"
    assert "『先生』という語" in out.text and "{WORD}" not in out.text


def test_validate_structure_rejects_wrong_order_or_extra_text():
    good = "\n".join(HEADINGS)
    assert validate_structure(good)
    assert not validate_structure("前置き\n" + good)
    assert not validate_structure("\n".join(reversed(HEADINGS)))
    assert not validate_structure("\n".join(HEADINGS[:3]))


class _FakeClient:
    def __init__(self, text):
        self._text = text
        self.messages = SimpleNamespace(create=self._create)
        self.last_kwargs = None

    def _create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=self._text)])


def test_api_path_substitutes_and_validates():
    flags = [make_flag("MI_HIGH_LOW_FREQ", mi=9.8, cooccur=12, threshold=20)]
    good = (
        "【この数字が言っていること】\n『{WORD}』という語と『{COLLOCATE}』という語は12回一緒に出ました。\n"
        "【論文に書くなら】\n…\n【言ってはいけないこと】\n回数が少ないので用例を全て確認してください。\n【次に確認すべきこと】\nKWIC で用例を見る。"
    )
    client = _FakeClient(good)
    out = narrate(_inp(flags), {"narrator": {"model": "claude-sonnet-5"}}, client=client)
    assert out.source == "api"
    assert "『先生』という語と『奥さん』という語" in out.text
    # 送ったメッセージに実際の語が含まれていない
    sent = client.last_kwargs["messages"][0]["content"]
    assert "先生" not in sent and "奥さん" not in sent
    assert client.last_kwargs["model"] == "claude-sonnet-5"


def test_api_bad_structure_falls_back_with_flags_intact():
    flags = [make_flag("MI_HIGH_LOW_FREQ", mi=9.8, cooccur=12, threshold=20)]
    out = narrate(_inp(flags), {}, client=_FakeClient("見出しのない返答"))
    assert out.source == "template"
    assert flags[0].message in out.text


def test_api_missing_flag_is_appended():
    flags = [make_flag("DISPERSION_SKEWED", word="x", freq=100, dp=0.7, threshold=0.5)]
    text_without_flag = "\n".join(HEADINGS)  # 4見出しはあるがフラグの内容が無い
    out = narrate(_inp(flags, screen="frequency"), {}, client=_FakeClient(text_without_flag))
    assert out.source == "api" and flags[0].message in out.text
