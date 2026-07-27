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

// 當前可動態更換的模型名稱 (預設模型)
let activeModel = process.env.NVIDIA_MODEL || "nvidia/nemotron-3-ultra-550b-a55b";

const client = new OpenAI({
  baseURL: "https://integrate.api.nvidia.com/v1",
  apiKey: nvidiaApiKey
});

// 健康檢查與當前模型狀態接口
app.get('/api/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    hasKey: !!nvidiaApiKey,
    model: activeModel
  });
});

// 取得當前使用的 AI 模型資訊
app.get('/api/model', (req, res) => {
  res.json({ 
    success: true, 
    model: activeModel, 
    hasKey: !!nvidiaApiKey 
  });
});

// 動態更新並儲存新的 AI 模型
app.post('/api/model', (req, res) => {
  const { model } = req.body;
  if (!model || typeof model !== 'string') {
    return res.status(400).json({ success: false, error: '請提供有效的模型名稱' });
  }
  activeModel = model.trim();
  console.log(`[系統訊息] NVIDIA AI 模型已更換為: ${activeModel}`);
  res.json({ success: true, model: activeModel });
});

app.post('/api/analyze-image', async (req, res) => {
  try {
    const { imageBase64, items } = req.body;

    // 判斷模型特徵，決定是否加入 nemotron / deepseek 思考鏈參數
    const lowerModel = activeModel.toLowerCase();
    const isReasoningModel = lowerModel.includes('nemotron') || lowerModel.includes('r1');
    
    const requestPayload = {
      model: activeModel,
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
      temperature: 0.2,
      top_p: 0.95,
      max_tokens: 4096,
      stream: false 
    };

    if (isReasoningModel) {
      requestPayload.extra_body = {
        "chat_template_kwargs": { "enable_thinking": true },
        "reasoning_budget": 16384
      };
      requestPayload.max_tokens = 16384;
    }

    let completion;
    try {
      completion = await client.chat.completions.create(requestPayload);
    } catch (apiErr) {
      // 若因不支援思考參數引發 400 錯誤，退回標準模式重新呼叫
      if (requestPayload.extra_body) {
        console.warn("包含 extra_body 請求失敗，嘗試改以標準請求呼叫...", apiErr.message);
        delete requestPayload.extra_body;
        requestPayload.max_tokens = 4096;
        completion = await client.chat.completions.create(requestPayload);
      } else {
        throw apiErr;
      }
    }

    const aiResponse = completion.choices[0]?.message?.content || "";
    res.json({ success: true, result: aiResponse.trim(), usedModel: activeModel });
  } catch (error) {
    console.error("NVIDIA API 呼叫錯誤:", error);
    res.status(500).json({ success: false, error: error.message });
  }
});

app.listen(port, "0.0.0.0", () => {
  console.log(`伺服器已在 http://localhost:${port} 運行`);
});
