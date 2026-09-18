#!/usr/bin/env bash
# コーパス分析ツール 起動スクリプト（macOS / Linux）
# ダブルクリックで開けない場合はターミナルで:  bash start.sh
set -e
cd "$(dirname "$0")"

echo "============================================================"
echo " コーパス分析ツール を起動します"
echo " （初回は必要な部品のダウンロードに数分かかります）"
echo "============================================================"
echo

# --- uv の確認 ------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
    if [ -x "$HOME/.local/bin/uv" ]; then
        export PATH="$HOME/.local/bin:$PATH"
    else
        echo "uv が見つからないため、インストールします..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    fi
fi

# --- Python と依存関係の準備 ---------------------------------------------
echo "必要な部品を準備しています..."
uv sync

# --- 起動 -----------------------------------------------------------------
echo
echo "ブラウザが自動で開きます。開かない場合は http://localhost:8501 を開いてください。"
echo "終了するには Ctrl+C を押してください。"
echo
uv run streamlit run app.py
