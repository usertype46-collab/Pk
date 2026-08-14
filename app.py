import os
import io
import re
import base64
import json
import time
import urllib.parse
import requests
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

# 載入環境變數
load_dotenv()

# 建立 Flask 應用，設定靜態資料夾為 public
app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)

current_api_key = os.getenv("NVIDIA_API_KEY", "nvapi-請填入預設金鑰")
current_model = "nvidia/nemotron-3-ultra-550b-a55b"

def get_openai_client():
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=current_api_key
    )

def convert_google_drive_url(url):
    """將 Google Drive 的 HTML 檢視連結轉換為直連圖片 CDN 網址"""
    if not url:
        return url
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url) or re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if match:
        return f"https://lh3.googleusercontent.com/d/{match.group(1)}"
    return url

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "model": current_model,
        "hasKey": bool(current_api_key),
        "driveReady": bool(os.getenv("GOOGLE_SCRIPT_URL"))
    })

@app.route('/api/settings', methods=['POST'])
def update_settings():
    global current_model, current_api_key
    data = request.json
    if data.get('model'):
        current_model = data['model']
    if data.get('apiKey'):
        current_api_key = data['apiKey']
    return jsonify({"success": True})

@app.route('/api/upload-image', methods=['POST'])
def upload_image():
    try:
        data = request.json
        image_base64 = data.get('imageBase64')
        gas_url = os.getenv("GOOGLE_SCRIPT_URL")

        if not gas_url:
            return jsonify({"success": False, "error": "後端尚未設定 GOOGLE_SCRIPT_URL 環境變數。"}), 500
        if not image_base64:
            return jsonify({"success": False, "error": "未接收到圖片檔案。"}), 400

        # 清除 base64 標頭
        base64_data = re.sub(r'^data:image/\w+;base64,', '', image_base64)
        image_bytes = base64.b64decode(base64_data)

        # 壓縮圖片
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=80)
        compressed_base64 = base64.b64encode(output.getvalue()).decode('utf-8')
        
        filename = f"baifu_{int(time.time() * 1000)}.jpg"
        
        # 發送至 Google Apps Script
        response = requests.post(
            gas_url,
            json={
                "fileName": filename,
                "mimeType": "image/jpeg",
                "base64": compressed_base64
            },
            headers={"Content-Type": "text/plain;charset=utf-8"},
            allow_redirects=True
        )
        
        result = response.json()
        if result.get('success'):
            direct_url = convert_google_drive_url(result.get('url'))
            proxy_url = f"/image-proxy?url={urllib.parse.quote(direct_url)}"
            return jsonify({"success": True, "url": proxy_url, "originalLink": direct_url})
        else:
            raise Exception(result.get('error', "Google Apps Script 發生未知錯誤"))

    except Exception as e:
        return jsonify({"success": False, "error": f"雲端上傳失敗：{str(e)}"}), 500

@app.route('/image-proxy', methods=['GET'])
def image_proxy():
    try:
        encoded_url = request.args.get('url')
        if not encoded_url:
            return "No URL provided", 400
        
        decoded_url = urllib.parse.unquote(encoded_url)
        decoded_url = convert_google_drive_url(decoded_url)

        response = requests.get(decoded_url, allow_redirects=True)
        if response.status_code != 200:
            raise Exception(f"無法獲取圖片，狀態碼: {response.status_code}")

        content_type = response.headers.get('content-type', 'image/jpeg')
        
        return send_file(
            io.BytesIO(response.content),
            mimetype=content_type,
            max_age=31536000
        )

    except Exception as e:
        return "圖片載入失敗", 500

@app.route('/api/analyze-image', methods=['POST'])
def analyze_image():
    try:
        data = request.json
        image_base64 = data.get('imageBase64')
        items = data.get('items')

        client = get_openai_client()

        completion = client.chat.completions.create(
            model=current_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"你是一個專業的粉體塗裝自動槍參數辨識與分析助手。現有資料庫構件清單如下：{json.dumps(items)}。請辨識圖片中最符合哪一個構件，並【僅回傳該構件的 id字串】，不要包含任何其他文字或說明。"
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_base64}
                        }
                    ]
                }
            ],
            temperature=0.1,
            max_tokens=50
        )

        result_text = completion.choices[0].message.content.strip()
        return jsonify({"success": True, "result": result_text})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/parse-item-name', methods=['POST'])
def parse_item_name():
    try:
        data = request.json
        image_base64 = data.get('imageBase64')
        if not image_base64:
            return jsonify({"success": False, "error": "未接收到圖片資料"}), 400

        client = get_openai_client()

        completion = client.chat.completions.create(
            model=current_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "你是一個專業的圖面與工單標籤文字辨識助手。請仔細辨識圖片中的「料號」與「品名」。\n請將辨識結果格式化為「料號/品名」（例如：UC-280B1-C003-WE/轉軸同心固定座.白）。\n【注意事項】：\n1. 料號與品名之間使用單一斜線「/」分隔，左右不要多餘空格。\n2. 請【僅回傳格式化的 料號/品名 字串】，絕對不要包含任何額外說明、Markdown引號或標點符號。"
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_base64}
                        }
                    ]
                }
            ],
            temperature=0.1,
            max_tokens=100
        )

        result_text = completion.choices[0].message.content.strip()
        result_text = re.sub(r'^[`\'"]+|[`\'"]+$', '', result_text)
        return jsonify({"success": True, "result": result_text})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/')
def index():
    return app.send_static_file('index.html')

if __name__ == '__main__':
    port = int(os.getenv("PORT", 3000))
    app.run(host='0.0.0.0', port=port)
