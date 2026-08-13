require('dotenv').config();
const express = require('express');
const cors = require('cors');
const { OpenAI } = require('openai'); // 使用 OpenAI SDK 串接 NVIDIA NIM API

const app = express();

// 啟用 CORS 與大容量 JSON 解析 (支援 Base64 圖片)
app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));

// 設定 NVIDIA API 客戶端
// 請在同層目錄的 .env 檔案中設定 NVIDIA_API_KEY=您的金鑰
const client = new OpenAI({
    apiKey: process.env.NVIDIA_API_KEY,
    baseURL: 'https://integrate.api.nvidia.com/v1',
});

/**
 * ========================================================
 * API 1: 標籤/料號 OCR 辨識 (建檔模式使用)
 * 模型: Llama-3.2-90B-Vision-Instruct
 * ========================================================
 */
app.post('/api/analyze-ocr', async (req, res) => {
    try {
        const { imageBase64 } = req.body;
        
        if (!imageBase64) {
            return res.status(400).json({ success: false, error: "未接收到圖片檔案。" });
        }

        // 使用強大的視覺模型進行 OCR
        const ocrModel = "meta/llama-3.2-90b-vision-instruct";

        const completion = await client.chat.completions.create({
            model: ocrModel,
            messages: [
                {
                    role: "user",
                    content: [
                        { 
                            type: "text", 
                            text: "你是一個專業的工業零件標籤辨識助理。請辨識圖片中的文字，找出對應的「料號(Part Number)」與「品名(Item Name)」。\n\n嚴格規定：\n1. 直接將料號與品名並列，中間以斜線「/」作為分隔線。\n2. 絕對不要加上任何其他的說明、前綴、標點符號或換行符號。\n3. 輸出範例：AB123456/高壓避震彈簧\n4. 如果只辨識到其中一項，就單獨輸出該項目即可。" 
                        },
                        { 
                            type: "image_url", 
                            image_url: { url: imageBase64 } 
                        }
                    ]
                }
            ],
            temperature: 0.1, // 極低溫度，確保輸出格式穩定
            max_tokens: 100
        });

        const recognizedText = completion.choices[0].message.content.trim();
        console.log(`[OCR 辨識成功] 解析結果: ${recognizedText}`);
        
        res.json({ success: true, text: recognizedText });
        
    } catch (error) {
        console.error("❌ AI 標籤 OCR 分析失敗:", error);
        res.status(500).json({ success: false, error: error.message });
    }
});

/**
 * ========================================================
 * API 2: 工件影像相似度分析 (查詢模式使用 - 擴充佔位符)
 * 用於在資料庫中找尋外觀最接近的工件
 * ========================================================
 */
app.post('/api/analyze-image', async (req, res) => {
    try {
        const { imageBase64 } = req.body;
        
        if (!imageBase64) {
            return res.status(400).json({ success: false, error: "未接收到圖片檔案。" });
        }

        // 這裡可串接您的工件特徵擷取或分類模型
        // 範例中直接返回成功狀態，供前端作後續資料庫比對或提示
        console.log(`[影像查詢] 收到前端查詢請求`);
        
        res.json({ 
            success: true, 
            message: "影像已接收，待與資料庫特徵進行匹配。"
        });
        
    } catch (error) {
        console.error("❌ 影像查詢分析失敗:", error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// 啟動伺服器
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`🚀 伺服器已啟動運行於 http://localhost:${PORT}`);
    console.log(`📡 NVIDIA API 整合已準備就緒`);
});
