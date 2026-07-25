// public/simulationWorker.js
let cards = {};
let lineSpeed = 1100;
let isRunning = false;
let animationInterval;

self.onmessage = function(e) {
    const { type, payload } = e.data;
    if (type === 'SYNC_STATE') {
        cards = payload.cards;
        lineSpeed = payload.line_speed || 1100;
        if (!isRunning) {
            isRunning = true;
            startSimulation();
        }
    } else if (type === 'STOP') {
        isRunning = false;
        clearInterval(animationInterval);
    }
};

function startSimulation() {
    animationInterval = setInterval(() => {
        const now = Date.now();
        const speedIndex = Math.max(1.0, lineSpeed / 100.0);
        const fullTimeMs = (1320.0 / speedIndex) * 60000;
        
        const progressUpdates = {};
        
        Object.values(cards).forEach(card => {
            if (card.status === 'on_line') {
                const elapsed = now - (card.line_start_time || now);
                let progress = elapsed / fullTimeMs;
                
                if (progress >= 1) {
                    progress = 1;
                    // 標記需要自動進入下料區的卡片
                    self.postMessage({ type: 'AUTO_UNLOAD', cardId: card.id });
                }
                progressUpdates[card.id] = progress;
            }
        });
        
        self.postMessage({ type: 'PROGRESS_UPDATE', payload: progressUpdates });
    }, 16); // 約 60FPS 的更新頻率
}
