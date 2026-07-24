// worker.js
let speed = 1100;
let isRunning = true;
let cards = {};

// 接收主執行緒的參數更新
self.onmessage = function(e) {
    const data = e.data;
    if (data.type === 'UPDATE_SPEED') {
        speed = data.speed;
    } else if (data.type === 'UPDATE_CARDS') {
        cards = data.cards;
    }
};

// 模擬引擎 Ticker (每 50ms 更新一次進度)
setInterval(() => {
    if (!isRunning) return;
    
    // 計算每張卡片的進度
    for (let id in cards) {
        // 假設總路徑長度為 100%，依據速度計算當前進度
        cards[id].progress += (speed / 100000); 
        if (cards[id].progress > 1) {
            cards[id].progress = 1; // 跑完路線
        }
    }
    
    // 將計算結果回傳給主執行緒進行渲染
    self.postMessage({
        type: 'TICK',
        cards: cards
    });
}, 50);
