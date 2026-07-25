let isRunning = false;
let currentSpeed = 1100; // 預設轉速[span_6](start_span)[span_6](end_span)
let activeCards = [];

self.onmessage = function(e) {
    const { command, speed, cards } = e.data;
    
    if (command === 'init') {
        isRunning = true;
        simulateLoop();
    } else if (command === 'update') {
        if (speed) currentSpeed = speed;
        if (cards) activeCards = cards;
    } else if (command === 'stop') {
        isRunning = false;
    }
};

function simulateLoop() {
    if (!isRunning) return;
    
    const now = Date.now();
    // 轉速指數計算 (speed / 100)，跑完全程基準為 1320 分鐘[span_7](start_span)[span_7](end_span)
    const speedIndex = Math.max(1.0, currentSpeed / 100.0);
    const fullTimeMs = (1320 / speedIndex) * 60000; 

    const updates = activeCards.map(card => {
        const elapsed = now - card.line_start_time;
        let progress = elapsed / fullTimeMs;
        let shouldUnload = false;

        if (progress >= 1) {
            progress = 1;
            shouldUnload = true;
        }

        return { id: card.id, progress, shouldUnload };
    });

    self.postMessage({ type: 'tick', updates });
    setTimeout(simulateLoop, 16); // ~60 FPS
}
