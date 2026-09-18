from corpus.models import Token, tokens_to_frame
from stats.network import build_network, pair_counts


def _tokens():
    sents = [["猫", "魚", "食べる"], ["猫", "魚"], ["犬", "走る"], ["猫", "走る"]]
    toks = []
    for s, words in enumerate(sents):
        for i, w in enumerate(words):
            toks.append(Token(w, w, "内容", 0, s * 10 + i, s))
    return tokens_to_frame(toks)


def test_pair_counts_sentence():
    edges, unit_freq = pair_counts(_tokens(), ["猫", "魚", "食べる", "犬", "走る"], method="sentence")
    e = edges.set_index(["a", "b"])["cooccur"]
    assert e[("猫", "魚")] == 2
    assert e[("猫", "走る")] == 1
    assert unit_freq["猫"] == 3


def test_build_network_centrality_and_threshold():
    g, edges, nodes = build_network(_tokens(), unit="lemma", include_function_words=True, top_n=10,
                                    method="sentence", min_log_dice=0.0, min_cooccur=1)
    assert g.has_edge("猫", "魚")
    top = nodes.iloc[0]
    assert top["word"] == "猫"  # 最も多くの語とつながる
    # 閾値を上げると辺が減る
    g2, edges2, _ = build_network(_tokens(), unit="lemma", include_function_words=True, top_n=10,
                                  method="sentence", min_log_dice=13.5, min_cooccur=1)
    assert edges2.shape[0] < edges.shape[0]
