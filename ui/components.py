"""共通 UI 部品: ?アイコン付き数値、用語解説の展開、警告バナー、書き出しボタン。"""
from __future__ import annotations

from typing import Iterable

import pandas as pd
import streamlit as st

from interpretations import glossary
from interpretations.flags import Flag


def metric_help(container, label: str, value, key: str | None = None, fmt: str | None = None) -> None:
    """数値の横に「?」アイコン（help）を付けて表示する。key は用語辞書のキー。"""
    if value is None:
        shown = "—"
    elif fmt:
        shown = format(value, fmt)
    else:
        shown = f"{value:,}" if isinstance(value, int) else str(value)
    help_text = glossary.tooltip(key) if key else None
    container.metric(label, shown, help=help_text)


def glossary_expander(keys: Iterable[str], title: str = "❓ この画面の数字の読み方（必ず一度は読んでください）") -> None:
    keys = list(keys)
    with st.expander(title, expanded=False):
        tabs = st.tabs([glossary.label(k) for k in keys])
        for tab, k in zip(tabs, keys):
            with tab:
                st.markdown(glossary.full_text(k))


def caution_box(key: str) -> None:
    """用語辞書の caution を常時表示する（TTR など、必ず併記すべきもの）。"""
    e = glossary.entry(key)
    st.warning(f"**{e.get('label', key)} について**\n\n" + str(e.get("caution", "")).strip())


def show_flags(flags: Iterable[Flag], empty_message: str | None = None) -> None:
    flags = list(flags)
    if not flags:
        if empty_message:
            st.success(empty_message)
        return
    for f in flags:
        if f.level == "warning":
            st.warning(f.message)
        else:
            st.info(f.message)


def explanation_panel(inp, thresholds: dict, title: str | None = None) -> None:
    """explainer の出力を画面に描く。
    【この数字が言っていること】は本文、【論文に書くなら】はコピーできる枠、
    【言ってはいけないこと】は警告色、【次に確認すべきこと】は情報色で出す。
    フラグが無ければ後ろ2つの見出しは出ない（explainer 側の仕様）。"""
    from interpretations.explainer import H_DONT, H_FACT, H_NEXT, H_PAPER, explain_sections

    with st.container(border=True):
        if title:
            st.markdown(f"**{title}**")
        for heading, lines in explain_sections(inp, thresholds):
            st.markdown(f"**{heading}**")
            if heading == H_PAPER:
                st.code("\n".join(lines), language=None, wrap_lines=True)
            elif heading == H_DONT:
                st.warning("\n\n".join(f"- {ln}" for ln in lines) if len(lines) > 1 else lines[0])
            elif heading == H_NEXT:
                st.info("\n\n".join(f"- {ln}" for ln in lines) if len(lines) > 1 else lines[0])
            else:
                st.markdown("\n\n".join(lines) if len(lines) == 1 else "\n".join(f"- {ln}" for ln in lines))


def csv_bytes(df: pd.DataFrame) -> bytes:
    """Excel で開いても文字化けしない UTF-8 (BOM 付き)。"""
    return df.to_csv(index=False).encode("utf-8-sig")


def download_csv(df: pd.DataFrame, filename: str, label: str = "CSV で保存", key: str | None = None) -> None:
    st.download_button(label, data=csv_bytes(df), file_name=filename, mime="text/csv", key=key)


def plotly_config(filename: str) -> dict:
    """st.plotly_chart の config。図の右上のカメラアイコンで PNG 保存できるようにする。
    サーバー側での画像生成はしない（表示と書き出しの二重実装を避けるため）。"""
    return {
        "displaylogo": False,
        "toImageButtonOptions": {"format": "png", "filename": filename, "scale": 2},
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    }


def png_hint() -> None:
    st.caption("図を PNG で保存するには、図の右上に出るカメラのアイコンを押してください。")


def column_config_with_help(mapping: dict[str, tuple[str, str]]) -> dict:
    """列名 → (表示ラベル, 用語辞書キー) から st.dataframe の column_config を作る。
    列見出しに「?」アイコンが付き、hover で解説が出る。"""
    cfg = {}
    for col, (label, key) in mapping.items():
        help_text = glossary.tooltip(key) if key else None
        cfg[col] = st.column_config.Column(label, help=help_text)
    return cfg
