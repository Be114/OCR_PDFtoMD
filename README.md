# PDF処理Webアプリケーション

## 概要
このアプリケーションは、PDFファイルをアップロードしてOCR処理を行い、Markdownファイルとして出力するWebベースのシステムです。
OpenRouter APIとGoogle Gemini Flashを活用した高精度なOCR機能により、PDFから正確なテキストを抽出し、読みやすいMarkdown形式で提供します。

## 機能
- 📄 PDFファイルのWebアップロード
- 🔒 セキュアなファイル処理
- 📱 基本的なWebインターフェース
- 🎯 ドラッグ&ドロップ対応
- ⚡ リアルタイムファイル検証
- 🤖 OpenRouter API (Gemini Flash) を利用した高精度OCR
- 📝 処理結果のMarkdownファイルダウンロード機能
- ⚡ 並列処理によるOCR速度向上

## ファイル構成
```
├── app.py                      # メインのFlaskアプリケーション
├── requirements.txt            # 必要なPythonライブラリ
├── start_app.bat              # Windows用アプリケーション起動スクリプト
├── .env.example               # APIキー設定用テンプレートファイル
├── README.md                  # このファイル
├── templates/                 # HTMLテンプレート
│   ├── index.html            # メインページ（アップロードフォーム）
│   └── upload_success.html   # アップロード成功ページ
├── uploads/                   # アップロードされたファイルの保存先（自動作成）
├── markdown_output/           # Markdown出力先ディレクトリ（自動作成）
└── temp_images/               # 一時画像保存先ディレクトリ（自動作成）
```

## セットアップと起動方法

**重要**: OCR機能を使用するには、事前にOpenRouter APIキーの設定が必須です。[設定セクション](#設定)を参照してください。

### 方法1: バッチファイルを使用（推奨・Windows）
1. OpenRouter APIキーを設定（下記の設定セクション参照）
2. `start_app.bat` をダブルクリック
3. 必要なライブラリが自動でインストールされます
4. ブラウザで `http://localhost:5000` にアクセス

### 方法2: 手動セットアップ
1. **Python 3.7以上**がインストールされていることを確認
2. OpenRouter APIキーを設定（下記の設定セクション参照）
3. 必要なライブラリをインストール:
   ```bash
   pip install -r requirements.txt
   ```

4. アプリケーションを起動:
   ```bash
   python app.py
   ```

5. ブラウザで `http://localhost:5000` にアクセス

## 使用方法
1. Webブラウザでアプリケーション（`http://localhost:5000`）にアクセス
2. 「ファイルを選択」ボタンをクリックするか、PDFファイルをドラッグ&ドロップ
3. 「アップロード開始」ボタンをクリック
4. OCR処理が自動的に開始されます（処理時間はファイルサイズにより数分程度）
5. 処理完了後、アップロード成功ページで処理結果のMarkdownファイルをダウンロード

## 設定
### APIキーの設定
OCR機能を使用するために**OpenRouter APIキーの設定が必須**です。以下の手順に従って設定してください：

#### ステップ1: APIキーの取得
[OpenRouter](https://openrouter.ai/)でアカウントを作成し、APIキーを取得してください。

#### ステップ2: 環境変数ファイルの作成
プロジェクトのルートディレクトリで以下のコマンドを実行：
```bash
cp .env.example .env
```

#### ステップ3: APIキーの設定
テキストエディタで `.env` ファイルを開き、取得したAPIキーを設定：
```
OPENROUTER_API_KEY=sk-your-actual-api-key-here
```

#### ステップ4: アプリケーションの再起動
APIキーを設定した後、アプリケーションを再起動してください。

**重要**: `.env` ファイルはGitの管理対象外のため、APIキーが誤ってコミットされる心配はありません。

### アップロード制限
- 対応ファイル形式: PDF
- 最大ファイルサイズ: 16MB
- アップロード先: `uploads/` ディレクトリ

## セキュリティ機能
- ファイル拡張子の検証
- セキュアなファイル名生成
- ファイルサイズ制限
- UUIDによる重複ファイル名回避

## 開発情報
- **フレームワーク**: Flask 2.3.3
- **Python**: 3.7以上推奨
- **フロントエンド**: HTML5, CSS3, JavaScript（バニラ）
- **OCRエンジン**: OpenRouter API + Google Gemini Flash
- **PDF処理**: PyMuPDF (fitz)
- **画像処理**: PIL (Pillow)

## トラブルシューティング
### よくある問題
1. **ポート5000が使用中**
   - `app.py`の最後の行で別のポートを指定: `app.run(port=5001)`

2. **ライブラリインストールエラー**
   - Python環境を確認: `python --version`
   - pipを更新: `python -m pip install --upgrade pip`

3. **ファイルアップロードエラー**
   - ファイルサイズが16MB以下か確認
   - PDFファイル形式か確認

4. **APIキー未設定エラー**
   - `.env`ファイルが作成されているか確認
   - `OPENROUTER_API_KEY`が正しく設定されているか確認
   - アプリケーションを再起動

## ヘルスチェック
アプリケーションの状態確認: `http://localhost:5000/health`


## ライセンス
このプロジェクトは開発中のため、ライセンスは後日決定予定です。
