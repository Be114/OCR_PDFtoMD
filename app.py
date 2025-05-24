import os
import uuid
import shutil
import time
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, send_from_directory
from werkzeug.utils import secure_filename
import tempfile
import fitz  # PyMuPDF
from PIL import Image
import requests
import json
import base64
import io
from dotenv import load_dotenv
import concurrent.futures

# .envファイルから環境変数を読み込む
load_dotenv()

# KindleOCRクラスの統合
class KindleOCR:
    def __init__(self, api_key):
        """OpenRouter APIの初期化"""
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/",
            "X-Title": "Kindle OCR",
        }

    def image_to_base64(self, image_path):
        """画像をbase64エンコードする"""
        with Image.open(image_path) as img:
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def extract_text(self, image_path):
        """画像からテキストを抽出する"""
        try:
            # 画像をbase64エンコード
            base64_image = self.image_to_base64(image_path)
            
            # APIリクエストを作成
            data = {
                "model": "google/gemini-2.0-flash-001",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "この画像から日本語テキストを抽出してください。装飾や構造は無視して、純粋なテキストのみを抽出してください。"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ]
            }
            
            # APIリクエスト送信
            response = requests.post(
                url=self.api_url,
                headers=self.headers,
                data=json.dumps(data)
            )
            
            if response.status_code == 200:
                response_data = response.json()
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    extracted_text = response_data['choices'][0]['message']['content']
                    if extracted_text:
                        return extracted_text.strip()
            
            print(f"APIレスポンスエラー: {response.text}")
            return None

        except Exception as e:
            print(f"テキスト抽出エラー ({os.path.basename(image_path)}): {str(e)}")
            return None

    def process_images_to_markdown(self, image_files, output_path):
        """画像ファイルのリストを処理してMarkdownファイルを生成（並列処理対応）"""
        try:
            max_workers = 5  # 並列処理数を5に固定
            all_text_results = [None] * len(image_files)  # 結果をページ順に格納するリスト
            success_count = 0
            
            print(f"OCR処理開始（並列数: {max_workers}）: {len(image_files)}個の画像を処理します")
            
            # ThreadPoolExecutorを使用して並列処理
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # {future: page_index}の辞書を作成し、完了時に元のページインデックスを取得できるようにする
                future_to_page_index = {
                    executor.submit(self.extract_text, image_path): i
                    for i, image_path in enumerate(image_files)
                }
                
                # as_completedで完了した順に処理
                for i, future in enumerate(concurrent.futures.as_completed(future_to_page_index)):
                    page_idx = future_to_page_index[future]
                    try:
                        text = future.result()  # この呼び出しで例外が発生する可能性もある
                        if text:
                            all_text_results[page_idx] = f"## ページ {page_idx + 1}\n\n{text}"
                            success_count += 1
                            print(f"ページ {page_idx + 1}/{len(image_files)} のテキスト抽出成功 ({i+1}タスク完了)")
                        else:
                            all_text_results[page_idx] = f"## ページ {page_idx + 1}\n\n[テキスト抽出に失敗しました]"
                            print(f"ページ {page_idx + 1}/{len(image_files)} のテキスト抽出失敗 ({i+1}タスク完了)")
                    except Exception as exc:
                        all_text_results[page_idx] = f"## ページ {page_idx + 1}\n\n[テキスト抽出エラー: APIリクエスト失敗]"
                        print(f'ページ {page_idx + 1}/{len(image_files)} の処理で例外発生: {exc} ({i+1}タスク完了)')
            
            # Markdownファイルに保存
            if all_text_results:
                # all_text_resultsにはNoneが含まれる可能性があるのでフィルタリング
                markdown_content = '\n\n'.join(filter(None, all_text_results))
                
                # 出力ディレクトリを確保
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                
                print(f"Markdownファイルを保存しました: {output_path}")
                print(f"OCR処理完了 - 成功: {success_count}/{len(image_files)}ページ, 並列数: {max_workers}")
                return success_count, len(image_files)
            
            return 0, len(image_files)
            
        except Exception as e:
            print(f"OCR処理エラー: {str(e)}")
            return 0, len(image_files)

# Flask アプリケーションの初期化
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # セッション管理用の秘密鍵

# 設定
UPLOAD_FOLDER = 'uploads'
IMAGES_FOLDER = 'temp_images'  # 変換された画像の一時保存先
MARKDOWN_FOLDER = 'markdown_output'  # Markdownファイルの保存先
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB制限

# OpenRouter APIキー（環境変数から読み込み）
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

def allowed_file(filename):
    """アップロードされたファイルが許可された拡張子かチェック"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_upload_directory():
    """アップロードディレクトリが存在することを確認"""
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

def ensure_images_directory():
    """画像保存ディレクトリが存在することを確認"""
    if not os.path.exists(IMAGES_FOLDER):
        os.makedirs(IMAGES_FOLDER)

def ensure_markdown_directory():
    """Markdown保存ディレクトリが存在することを確認"""
    if not os.path.exists(MARKDOWN_FOLDER):
        os.makedirs(MARKDOWN_FOLDER)

def pdf_to_images(pdf_path, output_dir=None, dpi=300):
    """
    PDFファイルを高解像度のPNG画像に変換する
    
    Args:
        pdf_path (str): PDFファイルのパス
        output_dir (str): 出力ディレクトリ（Noneの場合は一意のディレクトリを作成）
        dpi (int): 解像度（デフォルト300dpi）
    
    Returns:
        tuple: (出力ディレクトリパス, 変換された画像ファイルのリスト, 総ページ数)
    """
    try:
        # 出力ディレクトリの設定
        if output_dir is None:
            # PDFファイル名からユニークなディレクトリ名を生成
            pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
            output_dir = os.path.join(IMAGES_FOLDER, f"{pdf_basename}_{uuid.uuid4().hex[:8]}")
        
        # 出力ディレクトリを作成
        os.makedirs(output_dir, exist_ok=True)
        
        # PDFを開く
        pdf_document = fitz.open(pdf_path)
        total_pages = len(pdf_document)
        image_files = []
        
        print(f"PDF変換開始: {os.path.basename(pdf_path)} ({total_pages}ページ)")
        
        # 各ページを画像に変換
        for page_num in range(total_pages):
            page = pdf_document[page_num]
            
            # 高解像度でレンダリング（dpi/72でスケール計算）
            mat = fitz.Matrix(dpi/72, dpi/72)
            pix = page.get_pixmap(matrix=mat)
            
            # 画像ファイル名を生成
            image_filename = f"page_{page_num + 1:03d}.png"
            image_path = os.path.join(output_dir, image_filename)
            
            # PNG形式で保存
            pix.save(image_path)
            image_files.append(image_path)
            
            print(f"ページ {page_num + 1}/{total_pages} 変換完了: {image_filename}")
        
        # PDFを閉じる
        pdf_document.close()
        
        print(f"PDF変換完了: {len(image_files)}個の画像ファイルを生成")
        return output_dir, image_files, total_pages
        
    except Exception as e:
        print(f"PDF変換エラー: {str(e)}")
        return None, [], 0

def cleanup_temp_images(image_dir):
    """一時的な画像ディレクトリを削除する"""
    try:
        if os.path.exists(image_dir):
            shutil.rmtree(image_dir)
            print(f"一時ディレクトリを削除しました: {image_dir}")
    except Exception as e:
        print(f"一時ディレクトリ削除エラー: {str(e)}")

def cleanup_uploaded_pdf(pdf_path):
    """アップロードされたPDFファイルを削除する"""
    try:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
            print(f"アップロードファイルを削除しました: {pdf_path}")
    except Exception as e:
        print(f"アップロードファイル削除エラー: {str(e)}")

def generate_download_filename(original_filename):
    """ダウンロード用のファイル名を生成する"""
    base_name = os.path.splitext(original_filename)[0]
    timestamp = int(time.time())
    return f"{base_name}_extracted_{timestamp}.md"

@app.route('/')
def index():
    """メインページ - PDFアップロードフォームを表示"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """PDFファイルのアップロード処理"""
    filepath = None
    image_dir = None
    
    try:
        # ファイルがリクエストに含まれているかチェック
        if 'file' not in request.files:
            flash('ファイルが選択されていません', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        
        # ファイルが選択されているかチェック
        if file.filename == '':
            flash('ファイルが選択されていません', 'error')
            return redirect(request.url)
        
        # ファイルサイズチェック
        if file.content_length and file.content_length > MAX_CONTENT_LENGTH:
            flash(f'ファイルサイズが制限を超えています（最大{MAX_CONTENT_LENGTH // (1024*1024)}MB）', 'error')
            return redirect(request.url)
        
        # ファイルが有効でPDF形式かチェック
        if not file or not allowed_file(file.filename):
            flash('PDFファイルのみアップロード可能です', 'error')
            return redirect(request.url)
        
        # 必要なディレクトリを確保
        ensure_upload_directory()
        ensure_images_directory()
        ensure_markdown_directory()
        
        # 安全なファイル名を生成
        filename = secure_filename(file.filename)
        if not filename:
            flash('無効なファイル名です', 'error')
            return redirect(request.url)
        
        # 重複を避けるためにUUIDを追加
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        # ファイルを保存
        file.save(filepath)
        print(f"ファイル保存完了: {filepath}")
        
        # PDF→画像変換を実行
        print(f"PDF→画像変換を開始: {filepath}")
        try:
            image_dir, image_files, total_pages = pdf_to_images(filepath)
        except Exception as pdf_error:
            print(f"PDF変換エラー: {str(pdf_error)}")
            flash(f'PDFファイルの処理中にエラーが発生しました: {str(pdf_error)}', 'error')
            # クリーンアップ
            cleanup_uploaded_pdf(filepath)
            return redirect(url_for('index'))
        
        # 変数の初期化
        markdown_path = None
        markdown_filename = None
        ocr_success_count = 0
        ocr_total_count = 0
        
        if image_dir and image_files:
            # 画像変換成功 - OCR処理を実行
            print(f"OCR処理を開始: {len(image_files)}個の画像")
            
            if OPENROUTER_API_KEY:
                try:
                    # KindleOCRインスタンスを作成
                    ocr = KindleOCR(OPENROUTER_API_KEY)
                    
                    # Markdownファイルのパスを生成
                    base_filename = os.path.splitext(filename)[0]
                    markdown_filename = generate_download_filename(filename)
                    markdown_path = os.path.join(MARKDOWN_FOLDER, markdown_filename)
                    
                    # OCR処理を実行
                    ocr_success_count, ocr_total_count = ocr.process_images_to_markdown(image_files, markdown_path)
                    
                    if ocr_success_count > 0:
                        flash(f'ファイル "{filename}" が正常に処理されました。{total_pages}ページの画像に変換し、{ocr_success_count}ページのテキストを抽出しました', 'success')
                        
                        # 処理完了後のクリーンアップ
                        cleanup_uploaded_pdf(filepath)
                        cleanup_temp_images(image_dir)
                    else:
                        flash(f'ファイル "{filename}" の画像変換は成功しましたが、OCR処理でテキストを抽出できませんでした', 'warning')
                
                except Exception as ocr_error:
                    print(f"OCR処理エラー: {str(ocr_error)}")
                    flash(f'OCR処理中にエラーが発生しました: {str(ocr_error)}', 'warning')
                    # エラー時のクリーンアップ
                    cleanup_uploaded_pdf(filepath)
                    cleanup_temp_images(image_dir)
            else:
                flash(f'ファイル "{filename}" が正常にアップロードされ、{total_pages}ページの画像に変換されました（OCR処理はAPIキーが設定されていないためスキップされました）', 'warning')
            
            return render_template('upload_success.html',
                                 filename=filename,
                                 filepath=filepath,
                                 image_dir=image_dir,
                                 image_count=len(image_files),
                                 total_pages=total_pages,
                                 markdown_path=markdown_path,
                                 markdown_filename=markdown_filename,
                                 ocr_success_count=ocr_success_count,
                                 ocr_total_count=ocr_total_count)
        else:
            # 変換失敗
            flash(f'ファイル "{filename}" の画像変換に失敗しました。PDFファイルが破損している可能性があります', 'error')
            # クリーンアップ
            cleanup_uploaded_pdf(filepath)
            
            return render_template('upload_success.html',
                                 filename=filename,
                                 filepath=None,
                                 image_dir=None,
                                 image_count=0,
                                 total_pages=0,
                                 markdown_path=None,
                                 markdown_filename=None,
                                 ocr_success_count=0,
                                 ocr_total_count=0)
            
    except Exception as e:
        print(f"アップロード処理エラー: {str(e)}")
        flash(f'アップロード中に予期しないエラーが発生しました: {str(e)}', 'error')
        
        # エラー時のクリーンアップ
        if filepath:
            cleanup_uploaded_pdf(filepath)
        if image_dir:
            cleanup_temp_images(image_dir)
        
        return redirect(url_for('index'))

@app.route('/download/<filename>')
def download_file(filename):
    """Markdownファイルのダウンロード"""
    try:
        # セキュリティチェック: ファイル名にパス区切り文字が含まれていないか確認
        if '/' in filename or '\\' in filename or '..' in filename:
            flash('無効なファイル名です', 'error')
            return redirect(url_for('index'))
        
        # ファイルパスを構築
        file_path = os.path.join(MARKDOWN_FOLDER, filename)
        
        # ファイルが存在するかチェック
        if not os.path.exists(file_path):
            flash('ファイルが見つかりません', 'error')
            return redirect(url_for('index'))
        
        # ファイルをダウンロード用に送信
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='text/markdown'
        )
        
    except Exception as e:
        flash(f'ダウンロード中にエラーが発生しました: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/health')
def health_check():
    """ヘルスチェック用エンドポイント"""
    return jsonify({
        'status': 'healthy',
        'upload_folder': UPLOAD_FOLDER,
        'markdown_folder': MARKDOWN_FOLDER,
        'api_key_configured': bool(OPENROUTER_API_KEY)
    })

if __name__ == '__main__':
    # 必要なディレクトリを作成
    ensure_upload_directory()
    ensure_images_directory()
    ensure_markdown_directory()
    
    print("=== Kindle PDF処理Webアプリケーション ===")
    print(f"アップロードフォルダ: {os.path.abspath(UPLOAD_FOLDER)}")
    print(f"画像保存フォルダ: {os.path.abspath(IMAGES_FOLDER)}")
    print(f"Markdown保存フォルダ: {os.path.abspath(MARKDOWN_FOLDER)}")
    print(f"APIキー設定済み: {'はい' if OPENROUTER_API_KEY else 'いいえ'}")
    print("サーバーを起動中...")
    
    # 開発サーバーを起動
    app.run(debug=True, host='0.0.0.0', port=5000)