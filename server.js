import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import OpenAI from 'openai';
import path from 'path';
import { fileURLToPath } from 'url';

dotenv.config();

// 取得當前目錄路徑 (ES Module 寫法)
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
// Railway 會自動提供 PORT 環境變數
const port = process.env.PORT || 3000;

app.use(cors());
// 提升上傳容量限制，避免高解析度相機照片轉 Base64 後過大
app.use(express.json({ limit: '50mb' })); 
app.use(express.urlencoded({ limit: '50mb', extended: true }));

// 讓 Express 提供 public 資料夾內的靜態網頁 (包含 index.html)
app.use(express.static(path.join(__dirname, 'public')));

// 初始 NVIDIA API，優先讀取環境變數，若無則使用預設金鑰
const nvidiaApiKey = process.env.NVIDIA_API_KEY || "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";

const client = new OpenAI({
  baseURL: "https://integrate.api.nvidia.com/v1",
  apiKey: nvidiaApiKey
});

// 健康檢查與模型代碼偵測替換按鈕使用的 API
app.get('/api/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    hasKey: !!nvidiaApiKey,
    model: "nvidia/nemotron-3-ultra-550b-a55b"
  });
});

// 後端代理呼叫 NVIDIA AI 辨識拍照構件
app.post('/api/analyze-image', async (req, res) => {
  try {
    const { imageBase64, items } = req.body;

    // 呼叫 NVIDIA API (已整合您提供的 Reasoning 與 Token 參數)
    const completion = await client.chat.completions.create({
      model: "nvidia/nemotron-3-ultra-550b-a55b",
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
      temperature: 1,
      top_p: 0.95,
      max_tokens: 16384,
      // 支援 NVIDIA NIM 的 thinking 與預算參數
      extra_body: {
        "chat_template_kwargs": { "enable_thinking": true },
        "reasoning_budget": 16384
      },
      // 為了方便前端直接取得最終 JSON 分析結果，這裡關閉 stream
      stream: false 
    });

    const aiResponse = completion.choices[0]?.message?.content || "";
    // 若 AI 回傳包含推理過程，嘗試過濾出 ID (依據實際模型輸出特性調整)
    res.json({ success: true, result: aiResponse.trim() });
  } catch (error) {
    console.error("NVIDIA API 呼叫錯誤:", error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// 監聽 0.0.0.0 以確保在 Railway 容器內正確對外開放
app.listen(port, "0.0.0.0", () => {
  console.log(`伺服器已在 http://localhost:${port} 運行`);
});
