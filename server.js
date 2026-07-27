import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import OpenAI from 'openai';
import path from 'path';
import { fileURLToPath } from 'url';

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

const nvidiaApiKey = process.env.NVIDIA_API_KEY || "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";

const client = new OpenAI({
  baseURL: "https://integrate.api.nvidia.com/v1",
  apiKey: nvidiaApiKey
});

app.get('/api/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    hasKey: !!nvidiaApiKey,
    apiKey: nvidiaApiKey, // 供前端自動抓取 API Key
    model: "nvidia/nemotron-3-ultra-550b-a55b"
  });
});

app.post('/api/analyze-image', async (req, res) => {
  try {
    const { imageBase64, items } = req.body;

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
      extra_body: {
        "chat_template_kwargs": { "enable_thinking": true },
        "reasoning_budget": 16384
      },
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
