from interpretations import glossary


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


def test_join_lines_no_space_at_line_breaks():
    assert glossary.join_lines("利点ですが、\n元の出現回数が\n\n次の段落") == "利点ですが、元の出現回数が\n\n次の段落"
    head = glossary.caution_head("pmw")
    assert "、 " not in head and "\n" not in head


def test_log_dice_caution_mentions_both_high_frequency():
    assert "よく使われる語どうし" in glossary.entry("log_dice")["caution"]


def test_tooltip_and_full_text_render():
    for key in glossary.REQUIRED_KEYS:
        assert glossary.tooltip(key)
        assert glossary.label(key) in glossary.full_text(key)
