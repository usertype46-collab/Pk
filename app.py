import os
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# 系統全局變數
sys_state = {
    'line_speed': 1100,
    'cards': {} # 存放所有工單卡片狀態
}

# ==========================================
# 自動建立 templates 資料夾與 HTML 檔案
# ==========================================
def create_templates():
    if not os.path.exists('templates'):
        os.makedirs('templates')

    html_files = {
        # 1. 模擬器主控台
        'simulator.html': """
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>粉體塗裝流水線模擬器</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
            <style>
                body { font-family: '微軟正黑體', sans-serif; background: #f0f2f5; margin: 0; padding: 20px; }
                .dashboard { background: white; padding: 15px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
                .speed-ctrl button { font-size: 18px; padding: 5px 15px; margin: 0 10px; cursor: pointer; }
                .factory-map { position: relative; width: 100%; max-width: 1000px; height: 600px; background: white; border-radius: 10px; border: 2px solid #ccc; overflow: hidden; margin: 0 auto; }
                .mini-card { position: absolute; width: 30px; height: 30px; border-radius: 50%; border: 2px solid #333; transform: translate(-50%, -50%); cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 10px; color: white; text-shadow: 1px 1px 2px black; font-weight: bold; transition: width 0.3s, height 0.3s; z-index: 10;}
                .mini-card:hover { width: 150px; height: auto; border-radius: 10px; padding: 10px; z-index: 20; display: block; }
                .mini-card .details { display: none; }
                .mini-card:hover .details { display: block; font-size: 12px; margin-top: 5px; }
                .mini-card:hover .short-id { display: none; }
            </style>
        </head>
        <body>
            <div class="dashboard">
                <h2>🏭 粉體塗裝流水線模擬器</h2>
                <div class="speed-ctrl">
                    流水線轉速: <span id="current-speed">1100</span>
                    <button onclick="changeSpeed(-100)">-100</button>
                    <button onclick="changeSpeed(100)">+100</button>
                    <br><small>跑完全程所需時間: <span id="total-time"></span> 分鐘</small>
                </div>
            </div>
            
            <div class="factory-map" id="map">
                <!-- SVG 路線圖 (依據 14389.jpg 繪製) -->
                <svg viewBox="0 0 1000 800" width="100%" height="100%">
                    <path id="track" d="M 200 150 L 100 150 L 100 50 L 900 50 L 900 150 L 600 150 L 600 220 L 900 220 L 900 290 L 600 290 L 600 360 L 900 360 L 900 750 L 100 750" fill="none" stroke="#ff4d4d" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>
                    <rect x="150" y="125" width="80" height="50" fill="#4d94ff" rx="5"/>
                    <text x="190" y="155" fill="white" font-size="20" text-anchor="middle">上料</text>
                    
                    <rect x="450" y="25" width="100" height="50" fill="#4d94ff" rx="5"/>
                    <text x="500" y="55" fill="white" font-size="20" text-anchor="middle">前處理</text>
                    
                    <rect x="750" y="195" width="100" height="50" fill="#4d94ff" rx="5"/>
                    <text x="800" y="225" fill="white" font-size="20" text-anchor="middle">水切爐</text>
                    
                    <rect x="700" y="450" width="120" height="60" fill="#4d94ff" rx="5"/>
                    <text x="760" y="485" fill="white" font-size="24" text-anchor="middle">噴房</text>
                    
                    <rect x="700" y="650" width="120" height="60" fill="#4d94ff" rx="5"/>
                    <text x="760" y="685" fill="white" font-size="24" text-anchor="middle">烘烤爐</text>
                    
                    <rect x="50" y="725" width="80" height="50" fill="#4d94ff" rx="5"/>
                    <text x="90" y="755" fill="white" font-size="20" text-anchor="middle">下料</text>
                </svg>
            </div>

            <script>
                const socket = io();
                const track = document.getElementById('track');
                const trackLength = track.getTotalLength();
                let speedIndex = 11;
                
                socket.on('update_state', (state) => {
                    document.getElementById('current-speed').innerText = state.line_speed;
                    speedIndex = state.line_speed / 100;
                    document.getElementById('total-time').innerText = Math.round(1320 / speedIndex);
                    renderLineCards(state.cards);
                });

                function changeSpeed(val) { socket.emit('change_speed', val); }

                function renderLineCards(cards) {
                    const map = document.getElementById('map');
                    // 清除舊卡片
                    document.querySelectorAll('.mini-card').forEach(e => e.remove());
                    
                    const now = Date.now();
                    const fullTimeMs = (1320 / speedIndex) * 60000;

                    Object.values(cards).forEach(card => {
                        if(card.status === 'on_line') {
                            const elapsed = now - card.line_start_time;
                            let progress = elapsed / fullTimeMs;
                            
                            if (progress >= 1) {
                                progress = 1;
                                socket.emit('auto_move_to_unload', card.id); // 跑完自動進下料
                            }

                            const point = track.getPointAtLength(progress * trackLength);
                            
                            const div = document.createElement('div');
                            div.className = 'mini-card';
                            div.style.left = point.x + 'px';
                            div.style.top = point.y + 'px';
                            div.style.backgroundColor = card.colorCode || '#333';
                            
                            div.innerHTML = `
                                <span class="short-id">${card.id.substring(0,3)}</span>
                                <div class="details">
                                    <b>料號:</b> ${card.part_no}<br>
                                    <b>數量:</b> ${card.qty}<br>
                                    <b>顏色:</b> ${card.color}
                                </div>
                            `;
                            map.appendChild(div);
                        }
                    });
                }
                // 每秒更新畫面
                setInterval(() => { socket.emit('request_sync'); }, 1000);
            </script>
        </body>
        </html>
        """,

        # 2. 現場待料區
        'waiting.html': """
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>現場待料區</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
            <style>
                body { font-family: '微軟正黑體', sans-serif; background: #e9ecef; padding: 20px; margin: 0; padding-bottom: 150px;}
                .form-card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }
                .data-card { background: white; padding: 10px; border-radius: 8px; margin-bottom: 10px; border-left: 10px solid #ccc; display: flex; justify-content: space-between; align-items: center;}
                select, input, button { padding: 8px; margin: 5px 0; width: 100%; box-sizing: border-box; border-radius: 4px; border: 1px solid #ccc; font-size: 16px; }
                .btn-add { background: #28a745; color: white; border: none; cursor: pointer; font-weight: bold; }
                .btn-send { background: #007bff; color: white; width: auto; }
                .btn-del { background: #dc3545; color: white; width: auto; }
                .fixed-bottom { position: fixed; bottom: 0; left: 0; right: 0; height: 120px; background: #343a40; color: white; padding: 10px; overflow-y: auto; box-shadow: 0 -2px 10px rgba(0,0,0,0.5);}
                img.preview { max-width: 50px; cursor: pointer; vertical-align: middle; margin-left: 10px; }
            </style>
        </head>
        <body>
            <h2>📦 現場待料區</h2>
            <!-- 新增表單區：與列表分離，解決下拉選單閃退問題 -->
            <div class="form-card" id="inputForm">
                <select id="colorSelect" onchange="previewColor()">
                    <option value="WE白色,#FFFFFF">WE白色</option>
                    <option value="BK黑平光,#333333">BK黑平光</option>
                    <option value="RD紅色,#FF0000">RD紅色</option>
                    <option value="YWH黃錘紋,#FFD700">YWH黃錘紋</option>
                    <option value="BE藍色,#0000FF">BE藍色</option>
                    <option value="GN綠色,#008000">GN綠色</option>
                    <!-- 依需求可在此增補所有顏色 -->
                </select>
                <input type="text" id="partNo" placeholder="料號 (點擊右側相機拍照) ➔"> 
                <input type="file" accept="image/*" capture="environment">
                <input type="text" id="partName" placeholder="品名">
                <input type="number" id="qty" placeholder="數量">
                <button class="btn-add" onclick="createCard()">➕ 新增待上線構件</button>
            </div>

            <hr>
            <h3>待處理清單 (順序排列)</h3>
            <div id="waiting-list"></div>

            <!-- 同步傳送區 -->
            <div class="fixed-bottom">
                <h4>[待上料_阿利] 同步接收區</h4>
                <div id="ali-list"></div>
            </div>

            <script>
                const socket = io();
                
                function previewColor() {
                    const val = document.getElementById('colorSelect').value.split(',');
                    document.getElementById('inputForm').style.backgroundColor = val[1];
                }

                function createCard() {
                    const colorData = document.getElementById('colorSelect').value.split(',');
                    const data = {
                        id: Date.now().toString(),
                        color: colorData[0],
                        colorCode: colorData[1],
                        part_no: document.getElementById('partNo').value || '未填寫',
                        part_name: document.getElementById('partName').value || '未填寫',
                        qty: document.getElementById('qty').value || 0,
                        status: 'waiting'
                    };
                    socket.emit('add_card', data);
                    // 清空欄位
                    document.getElementById('partNo').value = '';
                    document.getElementById('partName').value = '';
                    document.getElementById('qty').value = '';
                }

                socket.on('update_state', (state) => {
                    const waitList = document.getElementById('waiting-list');
                    const aliList = document.getElementById('ali-list');
                    waitList.innerHTML = ''; aliList.innerHTML = '';

                    Object.values(state.cards).forEach(card => {
                        const div = document.createElement('div');
                        div.className = 'data-card';
                        div.style.borderColor = card.colorCode;
                        div.innerHTML = `
                            <div><b>${card.part_no}</b> (${card.part_name}) - ${card.color} x ${card.qty}</div>
                            <div>
                                ${card.status === 'waiting' ? 
                                    `<button class="btn-send" onclick="sendToAli('${card.id}')">➕ 傳送阿利</button>
                                     <button class="btn-del" onclick="delCard('${card.id}')">刪除</button>` 
                                    : ''}
                            </div>
                        `;
                        if(card.status === 'waiting') { waitList.appendChild(div); }
                        if(card.status === 'loading') { aliList.appendChild(div.cloneNode(true)); }
                    });
                });

                function sendToAli(id) { socket.emit('change_status', {id: id, status: 'loading'}); }
                function delCard(id) { 
                    if(confirm('⚠️ 確定要刪除這筆資料嗎？')) { socket.emit('delete_card', id); }
                }
            </script>
        </body>
        </html>
        """,

        # 3. 待上料_阿利
        'loading.html': """
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>待上料_阿利</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
            <style>
                body { font-family: '微軟正黑體', sans-serif; background: #e2e8f0; padding: 20px; padding-bottom: 150px;}
                .card { background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 10px solid #ccc;}
                .grid-form { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; margin-top: 10px; }
                select, button { padding: 8px; width: 100%; box-sizing: border-box; }
                .btn-line { background: #ff9800; color: white; border: none; padding: 10px; border-radius: 4px; cursor: pointer; margin-top: 10px;}
                .fixed-bottom { position: fixed; bottom: 0; left: 0; right: 0; height: 100px; background: #2c3e50; color: white; padding: 15px; text-align: center; font-size: 20px; font-weight: bold;}
                .time-calc { font-size: 14px; color: #d35400; font-weight: bold; margin-top: 10px; }
            </style>
        </head>
        <body>
            <h2>🏗️ 待上料_阿利</h2>
            <div id="loading-list"></div>
            
            <div class="fixed-bottom">
                ⬇️ [流水線_上線] 同步傳送區 ⬇️
            </div>

            <script>
                const socket = io();
                let currentSpeed = 1100;

                socket.on('update_state', (state) => {
                    currentSpeed = state.line_speed;
                    const list = document.getElementById('loading-list');
                    list.innerHTML = '';
                    
                    Object.values(state.cards).forEach(card => {
                        if(card.status === 'loading') {
                            const div = document.createElement('div');
                            div.className = 'card';
                            div.style.borderColor = card.colorCode;
                            div.innerHTML = `
                                <strong>料號: ${card.part_no} | 品名: ${card.part_name} | 數量: ${card.qty} | 顏色: ${card.color}</strong>
                                <div class="grid-form">
                                    <label>掛: <select id="hang_${card.id}" onchange="calcTime('${card.id}', ${card.qty})"><option value="1">1</option><option value="2">2</option></select></label>
                                    <label>空: <select id="empty_${card.id}" onchange="calcTime('${card.id}', ${card.qty})">${genOptions(10)}</select></label>
                                    <label>間隔: <select id="interval_${card.id}" onchange="calcTime('${card.id}', ${card.qty})">${genOptions(10)}</select></label>
                                    <label>接勾: <select id="hook_${card.id}">${genOptions(10)}</select></label>
                                </div>
                                <div class="time-calc" id="time_${card.id}">計算上線時間...</div>
                                <button class="btn-line" onclick="sendToLine('${card.id}')">➕ 同步傳送至流水線並計時</button>
                            `;
                            list.appendChild(div);
                            setTimeout(() => calcTime(card.id, card.qty), 100);
                        }
                    });
                });

                function genOptions(max) {
                    let html = '';
                    for(let i=0; i<=max; i++) html += `<option value="${i}">${i}</option>`;
                    return html;
                }

                function calcTime(id, qty) {
                    const hang = parseFloat(document.getElementById('hang_' + id).value) || 0;
                    const empty = parseFloat(document.getElementById('empty_' + id).value) || 0;
                    const interval = parseFloat(document.getElementById('interval_' + id).value) || 0;
                    const speedIndex = currentSpeed / 100;
                    
                    const totalMins = Math.round(((hang + empty + interval) * qty) / speedIndex);
                    const h = Math.floor(totalMins / 60);
                    const m = totalMins % 60;
                    document.getElementById('time_' + id).innerText = `預估佔線時間: ${h} 小時 ${m} 分鐘`;
                }

                function sendToLine(id) { socket.emit('send_to_line', id); }
            </script>
        </body>
        </html>
        """,

        # 4. 下料_完成
        'unloading.html': """
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>下料_完成</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
            <style>
                body { font-family: '微軟正黑體', sans-serif; background: #fdf2e9; padding: 20px;}
                .card { background: white; padding: 15px; border-radius: 8px; margin-bottom: 10px; border-left: 10px solid #ccc; display: flex; justify-content: space-between; align-items: center;}
                .btn-done { background: #27ae60; color: white; border: none; padding: 10px; border-radius: 4px; cursor: pointer;}
                .record { font-size: 12px; color: #7f8c8d; }
            </style>
        </head>
        <body>
            <h2>✅ 下料與完成紀錄區</h2>
            <h3>待下料區 (模擬器跑完自動傳送至此)</h3>
            <div id="unload-list"></div>
            
            <hr>
            <h3>歷史完成紀錄</h3>
            <div id="done-list"></div>

            <script>
                const socket = io();
                
                socket.on('update_state', (state) => {
                    const unloadList = document.getElementById('unload-list');
                    const doneList = document.getElementById('done-list');
                    unloadList.innerHTML = ''; doneList.innerHTML = '';

                    Object.values(state.cards).forEach(card => {
                        const div = document.createElement('div');
                        div.className = 'card';
                        div.style.borderColor = card.colorCode;
                        
                        if(card.status === 'unloading') {
                            div.innerHTML = `
                                <div><b>${card.part_no}</b> - ${card.color} x ${card.qty}</div>
                                <button class="btn-done" onclick="finishCard('${card.id}')">✅ 點擊完成</button>
                            `;
                            unloadList.appendChild(div);
                        } else if(card.status === 'completed') {
                            div.innerHTML = `
                                <div><b>${card.part_no}</b> - ${card.color} x ${card.qty}</div>
                                <div class="record">完成時間: ${card.finish_time}</div>
                            `;
                            doneList.appendChild(div);
                        }
                    });
                });

                function finishCard(id) { socket.emit('finish_card', id); }
            </script>
        </body>
        </html>
        """
    }

    for filename, content in html_files.items():
        filepath = os.path.join('templates', filename)
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"已自動生成: {filepath}")

# ==========================================
# Flask 路由設定
# ==========================================
@app.route('/')
def index(): return render_template('simulator.html')
@app.route('/wait')
def wait(): return render_template('waiting.html')
@app.route('/load')
def load(): return render_template('loading.html')
@app.route('/unload')
def unload(): return render_template('unloading.html')

# ==========================================
# Socket.IO 即時通訊與邏輯處理
# ==========================================
def broadcast_state():
    socketio.emit('update_state', sys_state)

@socketio.on('connect')
def handle_connect():
    emit('update_state', sys_state)

@socketio.on('request_sync')
def handle_sync():
    emit('update_state', sys_state)

@socketio.on('change_speed')
def handle_speed(val):
    sys_state['line_speed'] += val
    if sys_state['line_speed'] < 900: sys_state['line_speed'] = 900
    if sys_state['line_speed'] > 1400: sys_state['line_speed'] = 1400
    broadcast_state()

@socketio.on('add_card')
def add_card(data):
    sys_state['cards'][data['id']] = data
    broadcast_state()

@socketio.on('delete_card')
def delete_card(card_id):
    if card_id in sys_state['cards']:
        del sys_state['cards'][card_id]
        broadcast_state()

@socketio.on('change_status')
def change_status(data):
    card_id = data['id']
    if card_id in sys_state['cards']:
        sys_state['cards'][card_id]['status'] = data['status']
        broadcast_state()

@socketio.on('send_to_line')
def send_to_line(card_id):
    if card_id in sys_state['cards']:
        sys_state['cards'][card_id]['status'] = 'on_line'
        # 紀錄上線時間，用於模擬器計算座標
        sys_state['cards'][card_id]['line_start_time'] = int(time.time() * 1000) 
        broadcast_state()

@socketio.on('auto_move_to_unload')
def auto_unload(card_id):
    if card_id in sys_state['cards'] and sys_state['cards'][card_id]['status'] == 'on_line':
        sys_state['cards'][card_id]['status'] = 'unloading'
        broadcast_state()

@socketio.on('finish_card')
def finish_card(card_id):
    if card_id in sys_state['cards']:
        sys_state['cards'][card_id]['status'] = 'completed'
        # 紀錄完成當下的台灣時間
        tw_time = time.gmtime(time.time() + 8 * 3600)
        sys_state['cards'][card_id]['finish_time'] = time.strftime("%Y-%m-%d %H:%M:%S", tw_time)
        broadcast_state()

if __name__ == '__main__':
    create_templates() # 啟動前自動建立資料夾與檔案
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
