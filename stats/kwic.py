"""KWIC コンコーダンス。

tokens DataFrame を numpy 配列として扱い、文書境界をまたがないように
前後 n 語を取り出す。数百万トークンでも一瞬で返る構造にする。
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd


def _doc_bounds(doc_ids: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """各トークン位置に対して、その文書の [start, end) を返す。tokens は doc_id, position 順を前提。"""
    n = len(doc_ids)
    if n == 0:
        return np.array([], dtype=int), np.array([], dtype=int)
    change = np.flatnonzero(doc_ids[1:] != doc_ids[:-1]) + 1
    starts = np.concatenate([[0], change])
    ends = np.concatenate([change, [n]])
    # 各トークンの属する文書の start/end
    seg = np.repeat(np.arange(len(starts)), ends - starts)
    return starts[seg], ends[seg]


def _match(col: np.ndarray, query: str, regex: bool, case_sensitive: bool) -> np.ndarray:
    if regex:
        flags = 0 if case_sensitive else re.IGNORECASE
        pat = re.compile(query, flags)
        return np.fromiter((bool(pat.fullmatch(str(x))) for x in col), dtype=bool, count=len(col))
    if case_sensitive:
        return col == query
    q = query.lower()
    return np.fromiter((str(x).lower() == q for x in col), dtype=bool, count=len(col))


def find_hits(tokens: pd.DataFrame, query: str, unit: str = "lemma", regex: bool = False,
              case_sensitive: bool = True) -> np.ndarray:
    """検索語に一致するトークンの行番号（0始まり）を返す。

    unit が lemma のときは、集計キー（「ライト-light（光）」）と表示名（「ライト」）の
    どちらに一致しても拾う。表示名で検索すると同形異義語がまとめて出るので、
    絞り込みたい場合は集計キーで検索する。
    """
    mask = _match(tokens[unit].to_numpy(dtype=object), query, regex, case_sensitive)
    if unit == "lemma" and "lemma_label" in tokens.columns:
        mask = mask | _match(tokens["lemma_label"].to_numpy(dtype=object), query, regex, case_sensitive)
    return np.flatnonzero(mask)


def matched_keys(tokens: pd.DataFrame, hits: np.ndarray, unit: str = "lemma") -> pd.Series:
    """ヒットしたトークンが、どの集計キーに何件属するか（同形異義語の内訳）。"""
    if len(hits) == 0:
        return pd.Series(dtype=int)
    return tokens.iloc[hits][unit].value_counts()


def kwic(tokens: pd.DataFrame, query: str, unit: str = "lemma", window: int = 5,
         regex: bool = False, case_sensitive: bool = True, display: str = "surface") -> pd.DataFrame:
    """KWIC 表を返す。

    列: doc_id, position, sentence_id, key, L{window}..L1, KWIC, R1..R{window}, left, right
    key はヒットした語の集計キー（unit 列の値）。left/right は前後文脈を空白で連結した文字列。
    """
    tokens = tokens.reset_index(drop=True)
    hits = find_hits(tokens, query, unit=unit, regex=regex, case_sensitive=case_sensitive)
    cols_l = [f"L{i}" for i in range(window, 0, -1)]
    cols_r = [f"R{i}" for i in range(1, window + 1)]
    base_cols = ["doc_id", "position", "sentence_id", "key"] + cols_l + ["KWIC"] + cols_r + ["left", "right"]
    if len(hits) == 0:
        return pd.DataFrame(columns=base_cols)

    disp = tokens[display].to_numpy(dtype=object)
    doc_ids = tokens["doc_id"].to_numpy()
    starts, ends = _doc_bounds(doc_ids)

    out: dict[str, list] = {}
    out["doc_id"] = tokens["doc_id"].to_numpy()[hits].tolist()
    out["position"] = tokens["position"].to_numpy()[hits].tolist()
    out["sentence_id"] = tokens["sentence_id"].to_numpy()[hits].tolist()
    out["key"] = tokens[unit].to_numpy(dtype=object)[hits].tolist()
    out["KWIC"] = disp[hits].tolist()

    for k in range(1, window + 1):
        idx = hits - k
        ok = idx >= starts[hits]
        vals = np.where(ok, disp[np.clip(idx, 0, len(disp) - 1)], "")
        out[f"L{k}"] = vals.tolist()
        idx = hits + k
        ok = idx < ends[hits]
        vals = np.where(ok, disp[np.clip(idx, 0, len(disp) - 1)], "")
        out[f"R{k}"] = vals.tolist()

    df = pd.DataFrame(out)
    df["left"] = df[cols_l].apply(lambda r: " ".join(x for x in r if x), axis=1)
    df["right"] = df[cols_r].apply(lambda r: " ".join(x for x in r if x), axis=1)
    return df[base_cols]


def sort_kwic(df: pd.DataFrame, by: str = "R1", ascending: bool = True) -> pd.DataFrame:
    if by not in df.columns or len(df) == 0:
        return df
    return df.sort_values(by, ascending=ascending, kind="stable").reset_index(drop=True)
