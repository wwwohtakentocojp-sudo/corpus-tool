"""第1層: 用語辞書の読み込みとアクセス。AI は使わない。

glossary.yaml の本文には {threshold_name} 形式のテンプレート変数を書ける。
値は config.yaml から埋める（数値を辞書と設定に二重に書かないため）。
config に無い変数を参照していれば、読み込み時に例外を出す（黙って空欄にしない）。
"""
from __future__ import annotations

import string
from pathlib import Path
from typing import Any

import yaml

GLOSSARY_PATH = Path(__file__).resolve().parent / "glossary.yaml"

# 全指標キー（一つも省略しないことを tests で検証する）
REQUIRED_KEYS = [
    "frequency", "pmw", "dispersion_dp", "ttr", "ttr_standardized",
    "mi_score", "t_score", "log_dice", "log_likelihood",
    "p_value", "log_ratio", "odds_ratio",
    "correspondence_axis", "network_centrality",
    "data_size",
]

# テンプレート本文を持つフィールド
_TEXT_FIELDS = ("what", "high", "low", "caution", "range", "example")


class GlossaryTemplateError(ValueError):
    """辞書の本文が、config に無いテンプレート変数を参照している。"""


def fmt_threshold(v: Any) -> str:
    """閾値の表示。整数は桁区切り、小数は末尾の 0 を落とす（3.0 → 3、6.63 → 6.63）。"""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        return f"{int(v):,}" if v.is_integer() else f"{v:g}"
    return str(v)


def template_variables(config: dict[str, Any]) -> dict[str, str]:
    """辞書・解説文で使えるテンプレート変数。config.yaml から作る。
    一覧は glossary.yaml の先頭コメントにも書いてある（変更時は両方を更新すること）。"""
    th = dict(config.get("thresholds", {}))
    variables: dict[str, Any] = dict(th)
    variables["high_freq_top_percent"] = float(th.get("high_freq_top_ratio", 0.0)) * 100
    variables["log_ratio_times"] = 2 ** float(th.get("log_ratio_min", 1.0))
    variables["sttr_window"] = config.get("basic_stats", {}).get("sttr_window")
    variables["default_window"] = config.get("collocation", {}).get("default_window")
    return {k: fmt_threshold(v) for k, v in variables.items() if v is not None}


def render_template(text: str, variables: dict[str, str], where: str = "") -> str:
    """{name} を埋める。未定義の変数があれば GlossaryTemplateError。"""
    try:
        return string.Formatter().vformat(text, (), variables)
    except KeyError as e:
        raise GlossaryTemplateError(
            f"用語辞書の {where} が未定義のテンプレート変数 {{{e.args[0]}}} を参照しています。"
            " config.yaml に対応する閾値を追加するか、glossary.yaml の変数名を直してください。"
        ) from e
    except (IndexError, ValueError) as e:
        raise GlossaryTemplateError(f"用語辞書の {where} のテンプレート書式が不正です: {e}") from e


def _default_config() -> dict[str, Any]:
    from app_config import load_config

    return load_config()


_CACHE: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}


def load_glossary(path: str | Path | None = None, config: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """テンプレート変数を埋めた辞書を返す。同じ path/config なら再利用する。"""
    p = Path(path) if path else GLOSSARY_PATH
    cfg = config if config is not None else _default_config()
    key = (str(p), id(cfg))
    if key in _CACHE:
        return _CACHE[key]
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    variables = template_variables(cfg)
    rendered: dict[str, dict[str, Any]] = {}
    for k, e in raw.items():
        out = dict(e)
        for field in _TEXT_FIELDS:
            if field in out and out[field] is not None:
                out[field] = render_template(str(out[field]), variables, where=f"{k}.{field}")
        rendered[k] = out
    _CACHE[key] = rendered
    return rendered


def entry(key: str) -> dict[str, Any]:
    g = load_glossary()
    if key not in g:
        raise KeyError(f"用語辞書に {key} がありません")
    return g[key]


def label(key: str) -> str:
    return str(entry(key).get("label", key))


def join_lines(text: str) -> str:
    """YAML の複数行文字列を1行にする。日本語なので改行は空白を入れずに連結する。
    段落の区切り（空行）は残す。"""
    paras = str(text).strip().split("\n\n")
    return "\n\n".join("".join(line.strip() for line in p.splitlines()) for p in paras)


def caution_head(key: str) -> str:
    """caution の最初の段落を1行で。"""
    return join_lines(entry(key).get("caution", "")).split("\n\n")[0]


def tooltip(key: str) -> str:
    """"?" アイコン（help=）用の短い説明。what と caution。"""
    e = entry(key)
    what = join_lines(e.get("what", ""))
    caution = join_lines(e.get("caution", ""))
    text = what
    if caution:
        text += "\n\n注意: " + caution
    return text


def full_text(key: str) -> str:
    """展開表示用: label / what / high / low / caution / range / example を Markdown で。"""
    e = entry(key)
    parts = [f"**{e.get('label', key)}**"]
    for field, title in (("what", "何を測っているか"), ("high", "値が高いとき"), ("low", "値が低いとき"),
                         ("caution", "注意（必ず読んでください）"), ("range", "値の範囲と目安"), ("example", "例")):
        if e.get(field):
            parts += [f"**{title}**", join_lines(e[field])]
    return "\n\n".join(parts)
