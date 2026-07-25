// worker.js
let isRunning = false;
let progress = 0;
let speed = 0.005; // 模擬移動速度

self.onmessage = (e) => {
    if (e.data.command === 'start') {
        isRunning = true;
        simulate();
    } else if (e.data.command === 'stop') {
        isRunning = false;
    } else if (e.data.command === 'setSpeed') {
        speed = e.data.speed;
    }
};

function simulate() {
    if (!isRunning) return;
    
    progress += speed;
    if (progress > 1) {
        progress = 0; // 循環回到起點
    }
    
    // 將計算好的進度回傳給主執行緒
    self.postMessage({ type: 'TICK', progress: progress });
    
    // 使用 setTimeout 模擬 RequestAnimationFrame 在背景的運作
    setTimeout(simulate, 16); 
}
