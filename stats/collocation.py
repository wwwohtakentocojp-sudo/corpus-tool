"""コロケーション分析。

ウィンドウ方式（3種類）:
  fixed      : 前後 n 語（固定ウィンドウ）。文書境界はまたがない。
  sentence   : 同一文内。語順が動く言語（日本語・ドイツ語）の既定。
  dependency : 係り受けで直接つながる語（係り先と係り元）。

指標（O = 共起頻度, f(n) = 中心語の頻度, f(c) = 共起語の頻度, N = 全トークン数, W = 1回あたりの窓の広さ）:
  期待値   E = f(n) · f(c) · W / N
  MI       = log2(O / E)
  Tスコア  = (O − E) / sqrt(O)
  logDice  = 14 + log2(2·O / (f(n) + f(c)))
  G²       = 2 Σ o·ln(o/e) （2×2 分割表: a=O, b=f(c)−O, c=f(n)·W−O, d=N−a−b−c）

W は fixed なら 2n、sentence なら「中心語が出た文の長さ−1」の平均、
dependency なら「中心語と直接つながる語数」の平均。
f(c) と N は全トークン（機能語を含む）で数え、機能語の除外は表示時の行の絞り込みで行う。
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import chi2

from stats.kwic import _doc_bounds, find_hits

METHODS = {
    "sentence": "同一文内",
    "fixed": "前後 n 語（固定ウィンドウ）",
    "dependency": "係り受けで直接つながる語",
}

# 言語ごとの既定方式と、その理由（選択欄の直下に常時表示する）
DEFAULT_METHOD = {"ja": "sentence", "de": "sentence", "en": "fixed"}
METHOD_REASON = {
    "sentence": "この言語は語順が動くため、前後 n 語の固定ウィンドウでは取りこぼしが生じます。そのため同一文内を既定にしています。",
    "fixed": "この言語は語順が比較的固定されているため、前後 n 語の固定ウィンドウが標準的です。そのため固定ウィンドウを既定にしています。",
}


def association_measures(o: float, fn: float, fc: float, n: float, w: float) -> dict[str, float]:
    """1組の (中心語, 共起語) の指標。"""
    e = fn * fc * w / n if n > 0 else float("nan")
    mi = math.log2(o / e) if o > 0 and e > 0 else float("nan")
    t = (o - e) / math.sqrt(o) if o > 0 else float("nan")
    log_dice = 14 + math.log2(2 * o / (fn + fc)) if o > 0 and (fn + fc) > 0 else float("nan")
    a = o
    b = max(fc - o, 0.0)
    c = max(fn * w - o, 0.0)
    d = max(n - a - b - c, 0.0)
    g2 = log_likelihood_2x2(a, b, c, d)
    p = float(chi2.sf(g2, 1)) if not math.isnan(g2) else float("nan")
    return {"expected": e, "mi": mi, "t": t, "log_dice": log_dice, "g2": g2, "p": p}


def log_likelihood_2x2(a: float, b: float, c: float, d: float) -> float:
    total = a + b + c + d
    if total <= 0:
        return float("nan")
    r1, r2 = a + b, c + d
    c1, c2 = a + c, b + d
    g2 = 0.0
    for o, e in ((a, r1 * c1 / total), (b, r1 * c2 / total), (c, r2 * c1 / total), (d, r2 * c2 / total)):
        if o > 0 and e > 0:
            g2 += o * math.log(o / e)
    return 2 * g2


# ---------------------------------------------------------------------------
def _sentence_keys(tokens: pd.DataFrame) -> np.ndarray:
    return (tokens["doc_id"].to_numpy(dtype=np.int64) << 32) + tokens["sentence_id"].to_numpy(dtype=np.int64)


def collocate_occurrences(tokens: pd.DataFrame, hits: np.ndarray, method: str, window: int = 5) -> tuple[pd.DataFrame, float]:
    """中心語の各出現（hits）に対する共起語トークンの行番号を列挙する。

    返り値: (DataFrame[idx, hit, relation], W)
    """
    n = len(tokens)
    if len(hits) == 0 or n == 0:
        return pd.DataFrame(columns=["idx", "hit", "relation"]), 0.0

    if method == "fixed":
        doc_ids = tokens["doc_id"].to_numpy()
        starts, ends = _doc_bounds(doc_ids)
        idx_list, hit_list = [], []
        for k in range(-window, window + 1):
            if k == 0:
                continue
            idx = hits + k
            ok = (idx >= starts[hits]) & (idx < ends[hits])
            idx_list.append(idx[ok])
            hit_list.append(hits[ok])
        df = pd.DataFrame({"idx": np.concatenate(idx_list), "hit": np.concatenate(hit_list)})
        df["relation"] = ""
        return df, float(2 * window)

    if method == "sentence":
        keys = _sentence_keys(tokens)
        members: dict[int, np.ndarray] = {}
        order = np.argsort(keys, kind="stable")
        sorted_keys = keys[order]
        uniq, starts_u = np.unique(sorted_keys, return_index=True)
        ends_u = np.append(starts_u[1:], len(sorted_keys))
        for k, s, e in zip(uniq, starts_u, ends_u):
            members[int(k)] = order[s:e]
        idx_list, hit_list, sizes = [], [], []
        for h in hits:
            m = members[int(keys[h])]
            m = m[m != h]
            idx_list.append(m)
            hit_list.append(np.full(len(m), h))
            sizes.append(len(m))
        df = pd.DataFrame({"idx": np.concatenate(idx_list) if idx_list else [], "hit": np.concatenate(hit_list) if hit_list else []})
        df["relation"] = ""
        return df, float(np.mean(sizes)) if sizes else 0.0

    if method == "dependency":
        if "head" not in tokens.columns:
            return pd.DataFrame(columns=["idx", "hit", "relation"]), 0.0
        doc_ids = tokens["doc_id"].to_numpy()
        pos = tokens["position"].to_numpy()
        head = tokens["head"].to_numpy()
        dep = tokens["dep"].to_numpy(dtype=object)
        key = (doc_ids.astype(np.int64) << 32) + pos.astype(np.int64)
        row_of = pd.Series(np.arange(n), index=key)
        head_key = np.where(head >= 0, (doc_ids.astype(np.int64) << 32) + head.astype(np.int64), -1)
        # 係り元（この語に係る語）
        by_head: dict[int, list[int]] = {}
        for i, hk in enumerate(head_key):
            if hk >= 0:
                by_head.setdefault(int(hk), []).append(i)
        idx_list, hit_list, rel_list, sizes = [], [], [], []
        for h in hits:
            cnt = 0
            for child in by_head.get(int(key[h]), []):
                idx_list.append(child)
                hit_list.append(h)
                rel_list.append(str(dep[child]))
                cnt += 1
            hk = head_key[h]
            if hk >= 0 and hk in row_of.index:
                parent = int(row_of[hk])
                idx_list.append(parent)
                hit_list.append(h)
                rel_list.append("→" + str(dep[h]))
                cnt += 1
            sizes.append(cnt)
        df = pd.DataFrame({"idx": idx_list, "hit": hit_list, "relation": rel_list})
        return df, float(np.mean(sizes)) if sizes else 0.0

    raise ValueError(f"未知のウィンドウ方式: {method}")


def collocation_table(tokens: pd.DataFrame, node: str, unit: str = "lemma", method: str = "sentence",
                      window: int = 5, min_cooccur: int = 1) -> pd.DataFrame:
    """中心語 node のコロケーション表。logDice 降順。

    列: collocate, label, pos, is_function, relation, cooccur, freq_node, freq_collocate,
        expected, mi, t, log_dice, g2, p
    機能語の行も含める（表示側で絞り込む）。
    """
    tokens = tokens.reset_index(drop=True)
    cols = ["collocate", "label", "pos", "is_function", "relation", "cooccur", "freq_node", "freq_collocate",
            "expected", "mi", "t", "log_dice", "g2", "p"]
    hits = find_hits(tokens, node, unit=unit)
    if len(hits) == 0:
        return pd.DataFrame(columns=cols)
    occ, w = collocate_occurrences(tokens, hits, method, window)
    if occ.empty:
        return pd.DataFrame(columns=cols)

    n = len(tokens)
    fn = len(hits)
    words = tokens[unit].to_numpy(dtype=object)
    node_keys = set(tokens.iloc[hits][unit].astype(str))  # 表示名で検索した場合の同形異義語も含める

    occ = occ.assign(word=words[occ["idx"].to_numpy()])
    occ = occ[~occ["word"].isin(node_keys)]  # 自分自身は除く
    if occ.empty:
        return pd.DataFrame(columns=cols)

    group_cols = ["word", "relation"] if method == "dependency" else ["word"]
    counts = occ.groupby(group_cols).size().rename("cooccur").reset_index()
    if method != "dependency":
        counts["relation"] = ""
    counts = counts[counts["cooccur"] >= min_cooccur]

    freq_all = tokens[unit].value_counts()
    label_col = "lemma_label" if unit == "lemma" and "lemma_label" in tokens.columns else unit
    labels = tokens.groupby(unit)[label_col].first()
    pos_mode = tokens.groupby(unit)["pos"].agg(lambda x: x.value_counts().index[0])
    is_fn = tokens.groupby(unit)["is_function"].agg("max")

    rows = []
    for r in counts.itertuples(index=False):
        fc = int(freq_all.get(r.word, 0))
        m = association_measures(float(r.cooccur), float(fn), float(fc), float(n), w)
        rows.append(
            {
                "collocate": r.word,
                "label": labels.get(r.word, r.word),
                "pos": pos_mode.get(r.word, ""),
                "is_function": bool(is_fn.get(r.word, False)),
                "relation": r.relation,
                "cooccur": int(r.cooccur),
                "freq_node": fn,
                "freq_collocate": fc,
                **m,
            }
        )
    df = pd.DataFrame(rows, columns=cols)
    return df.sort_values(["log_dice", "cooccur"], ascending=[False, False]).reset_index(drop=True)
