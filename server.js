import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import OpenAI from 'openai';
import path from 'path';
import { fileURLToPath } from 'url';
import sharp from 'sharp';
import crypto from 'crypto';

if (typeof globalThis.crypto === 'undefined') {
  globalThis.crypto = crypto.webcrypto;
}

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = process.env.PORT || 3000;

app.use(cors());
app.use(express.json({ limit: '50mb' })); 
app.use(express.urlencoded({ limit: '50mb', extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

let currentApiKey = process.env.NVIDIA_API_KEY || "nvapi-請填入預設金鑰";
let currentModel = "nvidia/nemotron-3-ultra-550b-a55b";

let client = new OpenAI({
  baseURL: "https://integrate.api.nvidia.com/v1",
  apiKey: currentApiKey
});

app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    model: currentModel,
    hasKey: !!currentApiKey,
    driveReady: !!process.env.GOOGLE_SCRIPT_URL
  });
});

app.post('/api/settings', (req, res) => {
  const { model, apiKey } = req.body;
  if (model) currentModel = model;
  if (apiKey) {
    currentApiKey = apiKey;
    client = new OpenAI({
      baseURL: "https://integrate.api.nvidia.com/v1",
      apiKey: currentApiKey
    });
  }
  res.json({ success: true });
});

// 圖片上傳至 Google Drive (透過 Google Apps Script 中繼)
app.post('/api/upload-image', async (req, res) => {
  try {
    const { imageBase64 } = req.body;
    
    if (!process.env.GOOGLE_SCRIPT_URL) {
      return res.status(500).json({ success: false, error: "後端尚未設定 GOOGLE_SCRIPT_URL 環境變數。" });
    }
    if (!imageBase64) {
      return res.status(400).json({ success: false, error: "未接收到圖片檔案。" });
    }

    const base64Data = imageBase64.replace(/^data:image\/\w+;base64,/, "");
    let buffer = Buffer.from(base64Data, 'base64');

    // 壓縮圖片
    buffer = await sharp(buffer)
      .jpeg({ quality: 80 })
      .toBuffer();

    const compressedBase64 = buffer.toString('base64');
    const filename = `baifu_${Date.now()}.jpg`;
    console.log(`[Google Drive 上傳] 準備傳送檔案: ${filename} (大小: ${(buffer.length / 1024).toFixed(2)} KB)`);
    
    // 關鍵修復：加入 redirect: 'follow' 確保正確跟隨 GAS 的 302 重新導向
    const response = await fetch(process.env.GOOGLE_SCRIPT_URL, {
      method: 'POST',
      redirect: 'follow',
      headers: {
        'Content-Type': 'text/plain;charset=utf-8'
      },
      body: JSON.stringify({
        fileName: filename,
        mimeType: 'image/jpeg',
        base64: compressedBase64
      })
    });

    const responseText = await response.text();
    let result;
    try {
      result = JSON.parse(responseText);
    } catch (parseErr) {
      console.error("❌ Google Apps Script 回傳非 JSON 格式:", responseText);
      throw new Error("Google Apps Script 回傳格式錯誤，請檢查網址或權限設定是否為「任何人」。");
    }

    if (result.success) {
      const proxyUrl = `/image-proxy?url=${encodeURIComponent(result.url)}`;
      console.log(`[Google Drive 上傳] 成功！連結: ${result.url}`);
      res.json({ success: true, url: proxyUrl, originalLink: result.url });
    } else {
      throw new Error(result.error || "Google Apps Script 發生未知錯誤");
    }

  } catch (error) {
    console.error("❌ 上傳至 Google Drive 失敗:", error);
    res.status(500).json({ success: false, error: "雲端上傳失敗：" + error.message });
  }
});

app.get('/image-proxy', async (req, res) => {
  try {
    const encodedUrl = req.query.url;
    if (!encodedUrl) return res.status(400).send("No URL provided");
    
    const decodedUrl = decodeURIComponent(encodedUrl);
    const response = await fetch(decodedUrl);
    if (!response.ok) {
        throw new Error(`無法獲取圖片，狀態碼: ${response.status}`);
    }

    res.setHeader('Content-Type', response.headers.get('content-type') || 'image/jpeg');
    res.setHeader('Cache-Control', 'public, max-age=31536000');
    
    const buffer = await response.arrayBuffer();
    res.send(Buffer.from(buffer));

  } catch (error) {
    console.error("❌ 代理讀取圖片失敗:", error);
    res.status(500).send("圖片載入失敗");
  }
});

app.post('/api/analyze-image', async (req, res) => {
  try {
    const { imageBase64, items } = req.body;

    const completion = await client.chat.completions.create({
      model: currentModel,
      messages: [
        {
          role: "user",
          content: [
            { 
              type: "text", 
              text: `你是一個專業的粉體塗裝自動槍參數辨識與分析助手。現有資料庫構件清單如下：${JSON.stringify(items)}。請辨識圖片中最符合哪一個構件，並【僅回傳該構件的 id字串】，不要包含任何其他文字或說明。` 
            },
            { type: "image_url", image_url: { url: imageBase64 } }
          ]
        }
      ],
      temperature: 0.1,
      max_tokens: 50
    });

    const resultText = completion.choices[0].message.content.trim();
    res.json({ success: true, result: resultText });
    
  } catch (error) {
    console.error("❌ AI 影像分析失敗:", error);
    res.status(500).json({ success: false, error: error.message });
  }
});

app.listen(port, '0.0.0.0', () => {
  console.log(`🚀 百富系統伺服器已啟動於 http://localhost:${port}`);
});
