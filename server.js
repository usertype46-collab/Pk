import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import OpenAI from 'openai';
import path from 'path';
import { fileURLToPath } from 'url';
import { Storage, File } from 'megajs';
import sharp from 'sharp';
import crypto from 'crypto';

// 修正：補上 Node.js 環境中 MegaJS 所需的 Web Crypto API 支援
if (typeof globalThis.crypto === 'undefined') {
  globalThis.crypto = crypto.webcrypto;
}

// 載入 .env 環境變數
dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = process.env.PORT || 3000;

app.use(cors());
// 加大請求容量限制，確保高解析度相片傳送不卡死
app.use(express.json({ limit: '50mb' })); 
app.use(express.urlencoded({ limit: '50mb', extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

// --- NVIDIA API 初始化 ---
let currentApiKey = process.env.NVIDIA_API_KEY || "nvapi-請填入預設金鑰";
let currentModel = "nvidia/nemotron-3-ultra-550b-a55b";

let client = new OpenAI({
  baseURL: "https://integrate.api.nvidia.com/v1",
  apiKey: currentApiKey
});

// --- Mega 雲端硬碟初始化 ---
let megaStorage = null;

async function initMega() {
  try {
    if (!process.env.MEGA_EMAIL || !process.env.MEGA_PASSWORD) {
      console.warn("⚠️ [警告] 尚未設定 MEGA_EMAIL 或 MEGA_PASSWORD。圖片將無法上傳。");
      return;
    }
    console.log("⏳ 正在登入 Mega 雲端硬碟...");
    megaStorage = new Storage({
      email: process.env.MEGA_EMAIL,
      password: process.env.MEGA_PASSWORD
    });
    
    // 必須等待 .ready，否則後續上傳會全部失敗
    await megaStorage.ready;
    console.log("✅ Mega 雲端硬碟登入成功！空間已準備就緒。");
  } catch (err) {
    console.error("❌ Mega 登入失敗，請確認 .env 帳號密碼是否正確:", err.message);
    megaStorage = null;
  }
}
initMega();

// --- API 路由區塊 ---

// 1. 系統狀態檢查
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    model: currentModel,
    hasKey: !!currentApiKey,
    megaReady: !!megaStorage
  });
});

// 2. 更新模型與金鑰設定
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

// 3. 上傳圖片至 Mega
app.post('/api/upload-image', async (req, res) => {
  try {
    const { imageBase64 } = req.body;
    
    if (!megaStorage) {
      return res.status(500).json({ success: false, error: "後端尚未成功連線至 Mega，請通知管理員檢查伺服器。" });
    }
    if (!imageBase64) {
      return res.status(400).json({ success: false, error: "未接收到圖片檔案。" });
    }

    // 將 Base64 轉換為 Buffer
    const base64Data = imageBase64.replace(/^data:image\/\w+;base64,/, "");
    let buffer = Buffer.from(base64Data, 'base64');

    // 使用 sharp 進行圖片壓縮 (轉為 JPEG，品質 80%)，加速上傳並節省 Mega 空間
    buffer = await sharp(buffer)
      .jpeg({ quality: 80 })
      .toBuffer();

    const filename = `baifu_${Date.now()}.jpg`;
    console.log(`[Mega 上傳] 準備儲存檔案: ${filename} (大小: ${(buffer.length / 1024).toFixed(2)} KB)`);
    
    // 上傳檔案並等待完成
    const file = await megaStorage.upload(filename, buffer).complete;
    
    // 獲取公開分享連結
    const link = await file.link();
    
    // 回傳透過本機代理的網址，以解決前端 Canvas 跨域 (CORS) 污染問題
    const proxyUrl = `/image-proxy?url=${encodeURIComponent(link)}`;

    console.log(`[Mega 上傳] 成功！連結已生成。`);
    res.json({ success: true, url: proxyUrl, originalLink: link });

  } catch (error) {
    console.error("❌ 上傳至 Mega 失敗:", error);
    res.status(500).json({ success: false, error: "雲端上傳失敗：" + error.message });
  }
});

// 4. Mega 圖片代理伺服器 (避免前端跨域問題)
app.get('/image-proxy', async (req, res) => {
  try {
    const encodedUrl = req.query.url;
    if (!encodedUrl) return res.status(400).send("No URL provided");
    
    const decodedUrl = decodeURIComponent(encodedUrl);
    const file = File.fromURL(decodedUrl);
    
    await file.loadAttributes();

    res.setHeader('Content-Type', 'image/jpeg');
    // 設定快取，避免重複載入相同圖片造成 Mega 流量限制 (快取 1 年)
    res.setHeader('Cache-Control', 'public, max-age=31536000');
    
    const stream = file.download();
    stream.pipe(res);

  } catch (error) {
    console.error("❌ 代理讀取圖片失敗:", error);
    res.status(500).send("圖片載入失敗");
  }
});

// 5. NVIDIA AI 影像分析
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
      temperature: 0.1, // 降低隨機性
      max_tokens: 50    // 限制回應長度
    });

    const resultText = completion.choices[0].message.content.trim();
    res.json({ success: true, result: resultText });
    
  } catch (error) {
    console.error("❌ AI 影像分析失敗:", error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// --- 啟動伺服器 ---
app.listen(port, '0.0.0.0', () => {
  console.log(`🚀 百富系統伺服器已啟動於 http://localhost:${port}`);
});
