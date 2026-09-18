"""共起ネットワーク。

頻度上位 N 語（内容語）を節点とし、同じ単位（文、または前後 n 語）に一緒に出た回数から
logDice を計算して、閾値以上の組を線で結ぶ。
中心性（次数・媒介）は networkx で計算する。

★ 設定（語数・閾値・単位）で図の見た目は大きく変わる。論文には設定値を明記すること。
"""
from __future__ import annotations

import math
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd

from stats.basic import select_tokens


def pair_counts(tokens: pd.DataFrame, words: list[str], unit: str = "lemma", method: str = "sentence",
                window: int = 5) -> tuple[pd.DataFrame, pd.Series]:
    """語の組ごとの共起回数と、各語の「単位数」（その語を含む文の数など）。"""
    wset = set(words)
    sub = tokens[tokens[unit].isin(wset)]
    if method == "sentence":
        key = (sub["doc_id"].to_numpy(dtype=np.int64) << 32) + sub["sentence_id"].to_numpy(dtype=np.int64)
        groups = sub.assign(_k=key).groupby("_k")[unit].agg(lambda s: sorted(set(s)))
        unit_freq = pd.Series(0, index=words, dtype=int)
        pairs: dict[tuple[str, str], int] = {}
        for members in groups:
            for w in members:
                unit_freq[w] += 1
            for a, b in combinations(members, 2):
                pairs[(a, b)] = pairs.get((a, b), 0) + 1
    else:  # fixed window: 前方 window 語以内に出た組を数える（各出現を1単位とみなす）
        sub = sub.sort_values(["doc_id", "position"])
        doc = sub["doc_id"].to_numpy()
        pos = sub["position"].to_numpy()
        wv = sub[unit].to_numpy(dtype=object)
        unit_freq = sub[unit].value_counts().reindex(words, fill_value=0)
        pairs = {}
        n = len(sub)
        for i in range(n):
            j = i + 1
            while j < n and doc[j] == doc[i] and pos[j] - pos[i] <= window:
                if wv[i] != wv[j]:
                    a, b = sorted((wv[i], wv[j]))
                    pairs[(a, b)] = pairs.get((a, b), 0) + 1
                j += 1
    rows = [{"a": a, "b": b, "cooccur": c} for (a, b), c in pairs.items()]
    return pd.DataFrame(rows, columns=["a", "b", "cooccur"]), unit_freq


def build_network(tokens: pd.DataFrame, unit: str = "lemma", include_function_words: bool = False,
                  top_n: int = 60, method: str = "sentence", window: int = 5,
                  min_log_dice: float = 7.0, min_cooccur: int = 2) -> tuple[nx.Graph, pd.DataFrame, pd.DataFrame]:
    """(グラフ, 辺の表, 節点の中心性表) を返す。"""
    sel = select_tokens(tokens, include_function_words)
    top = sel[unit].value_counts().head(top_n)
    words = top.index.tolist()
    edges, unit_freq = pair_counts(tokens, words, unit, method, window)
    if not edges.empty:
        edges["log_dice"] = edges.apply(
            lambda r: 14 + math.log2(2 * r["cooccur"] / (unit_freq[r["a"]] + unit_freq[r["b"]])) if (unit_freq[r["a"]] + unit_freq[r["b"]]) > 0 else float("nan"),
            axis=1,
        )
        edges = edges[(edges["log_dice"] >= min_log_dice) & (edges["cooccur"] >= min_cooccur)]
    g = nx.Graph()
    label_col = "lemma_label" if unit == "lemma" and "lemma_label" in tokens.columns else unit
    labels = tokens.groupby(unit)[label_col].first()
    for w in words:
        g.add_node(w, freq=int(top[w]), label=str(labels.get(w, w)))
    for r in edges.itertuples(index=False):
        g.add_edge(r.a, r.b, weight=float(r.log_dice), cooccur=int(r.cooccur))
    g.remove_nodes_from([n for n in list(g.nodes) if g.degree(n) == 0])

    deg = nx.degree_centrality(g) if g.number_of_nodes() > 1 else {}
    btw = nx.betweenness_centrality(g, weight=None) if g.number_of_nodes() > 2 else {}
    nodes = pd.DataFrame(
        [{"word": n, "label": g.nodes[n]["label"], "freq": g.nodes[n]["freq"], "degree": g.degree(n),
          "degree_centrality": deg.get(n, 0.0), "betweenness": btw.get(n, 0.0)} for n in g.nodes],
        columns=["word", "label", "freq", "degree", "degree_centrality", "betweenness"],
    ).sort_values("degree_centrality", ascending=False).reset_index(drop=True)
    return g, edges.reset_index(drop=True), nodes


def network_html(g: nx.Graph, height: str = "600px") -> str:
    """pyvis で HTML 文字列にする（外部送信なし。JS ライブラリは CDN 参照）。"""
    from pyvis.network import Network

    net = Network(height=height, width="100%", notebook=False, cdn_resources="remote")
    max_freq = max([g.nodes[n]["freq"] for n in g.nodes], default=1)
    for n in g.nodes:
        size = 10 + 30 * (g.nodes[n]["freq"] / max_freq)
        net.add_node(n, label=g.nodes[n]["label"], size=size, title=f"{g.nodes[n]['label']}: {g.nodes[n]['freq']} 回")
    for a, b, d in g.edges(data=True):
        net.add_edge(a, b, value=d.get("weight", 1.0), title=f"logDice {d.get('weight', 0):.2f} / 共起 {d.get('cooccur', 0)} 回")
    net.repulsion(node_distance=150, spring_length=150)
    return net.generate_html()
