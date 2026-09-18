import re

import pytest

from app_config import load_config
from interpretations import glossary
from interpretations.glossary import GlossaryTemplateError, fmt_threshold, render_template, template_variables


def test_all_required_metrics_present():
    g = glossary.load_glossary()
    missing = [k for k in glossary.REQUIRED_KEYS if k not in g]
    assert missing == [], f"用語辞書に欠けている指標: {missing}"


def test_every_entry_has_label_what_caution():
    g = glossary.load_glossary()
    for key, e in g.items():
        assert e.get("label"), f"{key}: label が空"
        assert e.get("what"), f"{key}: what が空"
        assert str(e.get("caution", "")).strip(), f"{key}: caution が空（必ず書くこと）"


def test_all_template_variables_resolved():
    """辞書の全本文で {変数} が残っていない（= config.yaml で全て解決できる）。"""
    g = glossary.load_glossary()
    leftovers = []
    for key, e in g.items():
        for field in ("what", "high", "low", "caution", "range", "example"):
            text = str(e.get(field, "") or "")
            if re.search(r"\{[a-z_]+\}", text):
                leftovers.append(f"{key}.{field}")
    assert leftovers == [], f"未解決のテンプレート変数が残っています: {leftovers}"


def test_template_values_come_from_config():
    cfg = load_config()
    th = cfg["thresholds"]
    assert f"{th['low_freq']} 回未満" in glossary.entry("frequency")["caution"]
    assert f"{th['low_cooccur_threshold']} 回未満" in glossary.entry("mi_score")["caution"]
    assert fmt_threshold(th["g2_significant"]) in glossary.entry("log_likelihood")["range"]
    assert f"{cfg['basic_stats']['sttr_window']:,} 語" in glossary.entry("ttr_standardized")["what"]


def test_undefined_variable_raises():
    with pytest.raises(GlossaryTemplateError) as ei:
        render_template("目安は {no_such_threshold} です", {"low_freq": "5"}, where="x.caution")
    assert "no_such_threshold" in str(ei.value)


def test_load_with_incomplete_config_raises(tmp_path):
    bad = tmp_path / "g.yaml"
    bad.write_text("x:\n  label: a\n  what: '{corpus_min_tokens} と {missing_key}'\n  caution: c\n", encoding="utf-8")
    with pytest.raises(GlossaryTemplateError):
        glossary.load_glossary(bad, config={"thresholds": {"corpus_min_tokens": 1}})


def test_fmt_threshold():
    assert fmt_threshold(10000) == "10,000"
    assert fmt_threshold(3.0) == "3"
    assert fmt_threshold(6.63) == "6.63"
    assert fmt_threshold(0.5) == "0.5"


def test_template_variables_derived():
    v = template_variables({"thresholds": {"high_freq_top_ratio": 0.01, "log_ratio_min": 1.0}})
    assert v["high_freq_top_percent"] == "1" and v["log_ratio_times"] == "2"


def test_join_lines_no_space_at_line_breaks():
    assert glossary.join_lines("利点ですが、\n元の出現回数が\n\n次の段落") == "利点ですが、元の出現回数が\n\n次の段落"
    head = glossary.caution_head("pmw")
    assert "、 " not in head and "\n" not in head


def test_log_dice_caution_mentions_both_high_frequency():
    assert "よく使われる語どうし" in glossary.entry("log_dice")["caution"]


def test_t_score_caution_no_longer_limited_to_function_words():
    c = glossary.entry("t_score")["caution"]
    assert "よく使われる語が隣にあるだけ" in c
    assert "機能語が上位に来たときは" not in c


def test_tooltip_and_full_text_render():
    for key in glossary.REQUIRED_KEYS:
        assert glossary.tooltip(key)
        assert glossary.label(key) in glossary.full_text(key)
