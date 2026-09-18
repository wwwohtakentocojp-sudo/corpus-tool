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


def test_tooltip_and_full_text_render():
    for key in glossary.REQUIRED_KEYS:
        assert glossary.tooltip(key)
        assert glossary.label(key) in glossary.full_text(key)
