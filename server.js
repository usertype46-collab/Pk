import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import OpenAI from 'openai';
import path from 'path';
import { fileURLToPath } from 'url';
import { Storage, File } from 'megajs';
import sharp from 'sharp';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = process.env.PORT || 3000;

app.use(cors());
// 加大請求容量限制，確保高解析度裁切圖片傳送不卡死
app.use(express.json({ limit: '50mb' })); 
app.use(express.urlencoded({ limit: '50mb', extended: true }));

app.use(express.static(path.join(__dirname, 'public')));

// 將變數設為 let 以支援前端動態修改設定
let currentApiKey = process.env.NVIDIA_API_KEY || "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";
let currentModel = "nvidia/nemotron-3-ultra-550b-a55b";

let client = new OpenAI({
  baseURL: "https://integrate.api.nvidia.com/v1",
  apiKey: currentApiKey
});

// Mega 雲端硬碟授權設定
let megaStorage = null;
async function initMega() {
  try {
    if (process.env.MEGA_EMAIL && process.env.MEGA_PASSWORD) {
      megaStorage = await new Storage({
        email: process.env.MEGA_EMAIL,
        password: process.env.MEGA_PASSWORD
      }).ready;
      console.log("Mega 雲端硬碟授權登入成功");
    } else {
      console.warn("未設定 MEGA_EMAIL 或 MEGA_PASSWORD 環境變數，圖片上傳功能將無法使用。");
    }
  } catch (error) {
    console.error("Mega 授權登入失敗:", error.message);
  }
}
initMega();

// 健康狀態檢查與獲取當前模型資訊
app.get('/api/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    hasKey: !!currentApiKey,
    model: currentModel
  });
});

// 提供前端修改 模型 與 API Key 的路由
app.post('/api/settings', (req, res) => {
  try {
    const { apiKey, model } = req.body;
    
    if (model) {
      currentModel = model;
    }
    
    // 如果有傳入 apiKey 且不是遮罩字串，則更新後端 OpenAI 客戶端設定
    if (apiKey && apiKey !== '********') {
      currentApiKey = apiKey;
      client = new OpenAI({
        baseURL: "https://integrate.api.nvidia.com/v1",
        apiKey: currentApiKey
      });
    }
    
    res.json({ success: true, model: currentModel, hasKey: !!currentApiKey });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// 處理圖片壓縮與上傳至 Mega 雲端的路由
app.post('/api/upload-image', async (req, res) => {
  try {
    const { imageBase64 } = req.body;
    
    if (!imageBase64 || !megaStorage) {
      return res.status(400).json({ success: false, error: "缺少圖片資料或 Mega 雲端未設定" });
    }

    // 移除 base64 標頭
    const base64Data = imageBase64.replace(/^data:image\/\w+;base64,/, "");
    const imageBuffer = Buffer.from(base64Data, 'base64');

    // 使用 sharp 進行圖片壓縮 (調整品質為 60%，最大寬度 800px)
    const compressedBuffer = await sharp(imageBuffer)
      .resize({ width: 800, withoutEnlargement: true })
      .jpeg({ quality: 60 })
      .toBuffer();

    const fileName = `coating_item_${Date.now()}.jpg`;

    // 取得根資料夾或指定資料夾，這裡預設上傳到 Mega 根目錄
    // 寫入緩衝區到 Mega
    const file = await megaStorage.upload({
      name: fileName,
      size: compressedBuffer.length
    }, compressedBuffer).complete;

    // 取得 Mega 檔案分享連結
    const link = await file.link();

    // 回傳透過伺服器代理的圖片網址，讓前端的 <img> 可以直接讀取
    const proxyUrl = `/api/image-proxy?url=${encodeURIComponent(link)}`;

    res.json({ 
      success: true, 
      url: proxyUrl, 
      downloadUrl: proxyUrl 
    });

  } catch (error) {
    console.error("圖片壓縮或上傳錯誤:", error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// 新增：Mega 圖片代理伺服器 (將加密的 Mega 連結解密為一般圖片串流)
app.get('/api/image-proxy', async (req, res) => {
  try {
    const { url } = req.query;
    if (!url) {
      return res.status(400).send("缺少 URL 參數");
    }

    const decodedUrl = decodeURIComponent(url);
    const file = File.fromURL(decodedUrl);
    await file.loadAttributes();

    res.setHeader('Content-Type', 'image/jpeg');
    // 設定快取，避免重複載入相同圖片造成 Mega 流量浪費
    res.setHeader('Cache-Control', 'public, max-age=31536000');
    
    // 下載並導流至 Response
    const stream = file.download();
    stream.pipe(res);

  } catch (error) {
    console.error("代理讀取圖片失敗:", error);
    res.status(500).send("圖片載入失敗");
  }
});

// NVIDIA AI 影像分析路由
app.post('/api/analyze-image', async (req, res) => {
  try {
    const { imageBase64, items } = req.body;

    const completion = await client.chat.completions.create({
      model: currentModel, // 動態套用當前所選的模型
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
      temperature: 0.1, // 降低隨機性，讓匹配更精準
      top_p: 0.95,
      max_tokens: 1024, // 配合 Llama Vision 模型調整合理的 token 數量
      stream: false 
    });

    const aiResponse = completion.choices[0]?.message?.content || "";
    res.json({ success: true, result: aiResponse.trim() });
  } catch (error) {
    console.error("NVIDIA API 呼叫錯誤:", error);
    res.status(500).json({ success: false, error: error.message });
  }
});

app.listen(port, "0.0.0.0", () => {
  console.log(`伺服器已在 http://localhost:${port} 運行`);
});
