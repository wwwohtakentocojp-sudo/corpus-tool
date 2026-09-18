import pytest

from analyzers.english import EnglishAnalyzer
from corpus.models import tokens_to_frame
from stats.frequency import frequency_table


@pytest.fixture(scope="module")
def en():
    return EnglishAnalyzer()


def test_lemmatize_and_function_words(en):
    df = tokens_to_frame(en.process("The cats were running quickly. The cat runs.", 0, {}))
    ft = frequency_table(df, unit="lemma", include_function_words=False).set_index("word")
    assert ft.loc["cat", "freq"] == 2
    assert ft.loc["run", "freq"] == 2
    assert "the" not in ft.index  # DET は機能語
    assert df["sentence_id"].nunique() == 2


def test_lowercase_option(en):
    on = tokens_to_frame(en.process("Apple makes phones. I ate an apple.", 0, {"lowercase": True}))
    off = tokens_to_frame(en.process("Apple makes phones. I ate an apple.", 0, {"lowercase": False}))
    assert on[on["surface"].str.lower() == "apple"]["lemma"].nunique() == 1
    assert off[off["surface"].str.lower() == "apple"]["lemma"].nunique() == 2


def test_dependency_present(en):
    df = tokens_to_frame(en.process("She reads books.", 0, {}))
    assert en.supports_dependency()
    obj = df[df["surface"] == "books"].iloc[0]
    assert obj["dep"] in ("dobj", "obj")
    assert df.loc[df["position"] == obj["head"], "surface"].iloc[0] == "reads"
