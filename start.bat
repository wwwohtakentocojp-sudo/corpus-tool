@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================================
echo  コーパス分析ツール を起動します
echo  （初回は必要な部品のダウンロードに数分かかります）
echo ============================================================
echo.

rem --- uv（Python と依存関係を管理するツール）の確認 -----------------
where uv >nul 2>nul
if %errorlevel%==0 goto :have_uv

if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    goto :have_uv
)

echo uv が見つからないため、インストールします...
powershell -ExecutionPolicy ByPass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex"
if errorlevel 1 (
    echo.
    echo [失敗] uv のインストールに失敗しました。
    echo        インターネット接続を確認して、もう一度このファイルを実行してください。
    pause
    exit /b 1
)
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

:have_uv
rem --- Python と依存関係の準備（uv が Python 本体も自動で用意します） -----
echo 必要な部品を準備しています...
uv sync
if errorlevel 1 (
    echo.
    echo [失敗] 必要な部品の準備に失敗しました。
    echo        インターネット接続を確認して、もう一度このファイルを実行してください。
    pause
    exit /b 1
)

rem --- 起動 -------------------------------------------------------------
echo.
echo ブラウザが自動で開きます。開かない場合は http://localhost:8501 を開いてください。
echo 終了するにはこのウィンドウを閉じてください。
echo.
uv run streamlit run app.py --server.address localhost --server.headless false
pause
