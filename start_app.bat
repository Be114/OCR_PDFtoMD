@echo off
echo ===================================
echo Kindle PDF処理Webアプリケーション
echo ===================================
echo.

REM 必要なライブラリをインストール
echo 必要なライブラリをインストール中...
pip install -r requirements.txt

echo.
echo アプリケーションを起動中...
echo ブラウザで http://localhost:5000 にアクセスしてください
echo.
echo 終了するには Ctrl+C を押してください
echo.

REM Flaskアプリケーションを起動
python app.py

pause