"""公開デモ版（Streamlit Community Cloud）向けの切り替え。

環境変数 DEMO_MODE=true のときだけ有効。ローカル実行（既定）では何も変わらない。
Community Cloud では Secrets に書いた値が環境変数としても渡されるので、
Secrets に DEMO_MODE = "true" と書けばよい。
サンプルデータは samples/demo/ に同梱する（デモ版で外部からの取得は行わない）。

公開版はアップロードしたファイルがサーバーを経由するため、
「外部送信しない」というローカル版の前提が成立しない。
そのため公開版は同梱サンプルで機能を体験するためのデモと位置づけ、
自分のデータの分析はローカル版で行うよう案内する。
"""
from __future__ import annotations

import os

import streamlit as st

# 公開時に置き換える。環境変数 REPO_URL で上書きできる
DEFAULT_REPO_URL = "https://github.com/<your-account>/corpus-tool"


def _env(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    if v is None:
        try:
            v = st.secrets.get(name)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - secrets.toml が無い環境
            v = None
    return str(v) if v is not None else default


def is_demo() -> bool:
    return _env("DEMO_MODE", "false").strip().lower() in ("1", "true", "yes", "on")


def repo_url() -> str:
    return _env("REPO_URL", DEFAULT_REPO_URL)


def max_upload_mb() -> float:
    """デモ版のアップロード上限（MB）。DEMO_MAX_UPLOAD_MB で変更可。ローカル版は上限なし（0）。"""
    if not is_demo():
        return 0.0
    try:
        return float(_env("DEMO_MAX_UPLOAD_MB", "5"))
    except ValueError:
        return 5.0


def check_upload_size(name: str, size_bytes: int) -> bool:
    """上限を超えていれば画面にエラーを出して False。ローカル版は常に True。"""
    limit = max_upload_mb()
    if limit <= 0 or size_bytes <= limit * 1024 * 1024:
        return True
    st.error(
        f"{name} は {size_bytes / 1024 / 1024:.1f} MB あり、デモ版の上限（{limit:g} MB）を超えています。"
        " デモ版は同梱サンプルで機能を体験するためのものです。大きなデータやご自身の資料は、ローカル版で分析してください。"
    )
    return False


def banner() -> None:
    """画面上部に常時表示するデモ版の注意。"""
    if not is_demo():
        return
    st.warning(
        "**これは動作を体験するためのデモ版です。** アップロードしたファイルはサーバーを経由します。"
        " 未公開の資料や再配布が禁止されているコーパスは、ここにアップロードしないでください。"
        " ご自身のデータを分析する場合は、ローカル版をお使いください（左下にリンク）。"
    )


def sidebar_links() -> None:
    if not is_demo():
        return
    url = repo_url()
    with st.sidebar:
        st.markdown("---")
        st.markdown("**デモ版について**")
        st.markdown(
            f"- [ソースコード（GitHub）]({url})\n"
            f"- [ローカル版の導入手順]({url}#自分のデータで使うローカル版)\n"
            f"- ローカル版は一切の外部送信を行いません。ご自身のデータはローカル版で分析してください。"
        )
        st.caption(f"デモ版のアップロード上限: {max_upload_mb():g} MB")


def german_model_note() -> None:
    """ドイツ語選択時、デモ版では sm モデルを使っている旨を注記する。"""
    if not is_demo():
        return
    st.info(
        "デモ版のドイツ語解析は、小さい言語モデル（de_core_news_sm）を使っています。"
        " 公開環境のメモリ制約のためで、精度重視のモデル（lg）は選べません。lg を使う場合はローカル版で `uv sync --extra large-models` を実行してください。"
    )
