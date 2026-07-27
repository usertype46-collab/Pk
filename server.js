import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import OpenAI from 'openai';

dotenv.config();

const app = express();
const port = process.env.PORT || 3000;

app.use(cors());
app.use(express.json({ limit: '10mb' }));

// 初始化 NVIDIA API Client (金鑰安全存放在後端環境變數)
const nvidiaApiKey = process.env.NVIDIA_API_KEY || "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";

const client = new OpenAI({
  baseURL: "https://integrate.api.nvidia.com/v1",
  apiKey: nvidiaApiKey
});

// 健康檢查與自動偵測金鑰狀態 API
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

    // 呼叫 NVIDIA API 進行影像或參數推理
    const completion = await client.chat.completions.create({
      model: "nvidia/nemotron-3-ultra-550b-a55b",
      messages: [
        {
          role: "system",
          content: "你是一個專業的粉體塗裝自動槍參數辨識與分析助手。請根據使用者上傳的圖片以及資料庫清單，判斷最匹配的構件項目並以 JSON 格式回傳。"
        },
        {
          role: "user",
          content: [
            { type: "text", text: `現有資料庫構件清單如下：${JSON.stringify(items)}。請辨識圖片中最符合哪一個構件，並僅回傳該構件的 id。` },
            { type: "image_url", image_url: { url: imageBase64 } }
          ]
        }
      ],
      temperature: 0.2,
      max_tokens: 1024,
    });

    const aiResponse = completion.choices[0]?.message?.content || "";
    res.json({ success: true, result: aiResponse });
  } catch (error) {
    console.error("NVIDIA API 呼叫錯誤:", error);
    res.status(500).json({ success: false, error: error.message });
  }
});

app.listen(port, () => {
  console.log(`伺服器已在 http://localhost:${port} 運行`);
});
