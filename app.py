import os
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

sys_state = {
    'line_speed': 1100,
    'cards': {} 
}

# 共用的 i18n 語言包與切換腳本 (注入到每一個 HTML 中)
I18N_SCRIPT = """
<style>
    .lang-btn { position: fixed; top: 15px; right: 15px; z-index: 1000; background: #34495e; color: white; border: none; padding: 10px 20px; border-radius: 20px; cursor: pointer; font-weight: bold; box-shadow: 0 4px 6px rgba(0,0,0,0.3); transition: 0.3s; }
    .lang-btn:hover { background: #2c3e50; }
</style>
<button class="lang-btn" id="langBtn" onclick="toggleLang()">🌐 切換語言 / Ngôn ngữ</button>
<script>
    const i18n = {
        'zh': {
            'sim_title': '🏭 粉體塗裝流水線模擬器', 'speed': '流水線轉速: ', 'time_lbl': '跑完全程所需時間: ', 'mins': ' 分鐘',
            'map1': '上料', 'map2': '前處理', 'map3': '水切爐', 'map4': '噴房', 'map5': '烘烤爐', 'map6': '下料',
            'wait_title': '📦 現場待料區', 'part_ph': '手動輸入或掃描料號', 'name_ph': '手動輸入或掃描品名',
            'scan_btn': '📷 掃描', 'add_btn': '➕ 新增待上線構件', 'list_wait': '待處理清單 (順序排列)',
            'ali_sync': '[待上料_阿利] 同步接收區', 'btn_send_ali': '➕ 傳送阿利', 'btn_del': '刪除',
            'ocr_title': '辨識系統', 'ocr_tip': '請將文字對準綠色框框內', 'btn_pic': '📸 拍照辨識', 'btn_close': '關閉',
            'ali_title': '🏗️ 待上料_阿利', 'line_sync': '⬇️ [流水線_上線] 同步傳送區 ⬇️',
            'lbl_hang': '掛:', 'lbl_empty': '空:', 'lbl_space': '間隔:', 'lbl_hook': '接勾:',
            'btn_to_line': '➕ 同步傳送至流水線並計時', 'calcing': '計算上線時間...',
            'unload_title': '✅ 下料與完成紀錄區', 'unload_wait': '待下料區 (模擬器跑完自動傳送至此)',
            'done_list': '歷史完成紀錄', 'btn_done': '✅ 點擊完成',
            'lang_btn': '🇻🇳 切換為越文 (Việt)', 'part_no': '料號:', 'part_name': '品名:', 'qty': '數量:', 'color': '顏色:',
            'ocr_proc': '🖼️ 影像處理中，請保持網路暢通...', 'ocr_err': '⚠️ 找不到清晰文字，請重新對焦後再試', 
            'est_time': '預估佔線時間: ', 'hrs': ' 小時 ', 'done_time': '完成時間: ', 'alert_del': '⚠️ 確定要刪除這筆資料嗎？'
        },
        'vi': {
            'sim_title': '🏭 Trình mô phỏng chuyền sơn', 'speed': 'Tốc độ chuyền: ', 'time_lbl': 'Thời gian 1 vòng: ', 'mins': ' Phút',
            'map1': 'Lên hàng', 'map2': 'Tiền X.Lý', 'map3': 'Lò sấy', 'map4': 'Phòng phun', 'map5': 'Lò nướng', 'map6': 'Xuống hàng',
            'wait_title': '📦 Khu vực chờ vật liệu', 'part_ph': 'Nhập / Quét mã LK', 'name_ph': 'Nhập / Quét tên LK',
            'scan_btn': '📷 Quét', 'add_btn': '➕ Thêm vào hàng chờ', 'list_wait': 'Danh sách chờ (Theo thứ tự)',
            'ali_sync': 'Khu vực đồng bộ [Chờ lên hàng_Ali]', 'btn_send_ali': '➕ Chuyển cho Ali', 'btn_del': 'Xóa',
            'ocr_title': 'Hệ thống nhận diện', 'ocr_tip': 'Căn chỉnh văn bản vào khung xanh', 'btn_pic': '📸 Chụp nhận diện', 'btn_close': 'Đóng',
            'ali_title': '🏗️ Chờ lên hàng_Ali', 'line_sync': '⬇️ [Dây chuyền] Truyền đồng bộ ⬇️',
            'lbl_hang': 'Treo:', 'lbl_empty': 'Trống:', 'lbl_space': 'Cách:', 'lbl_hook': 'Móc:',
            'btn_to_line': '➕ Chuyển lên chuyền & Bắt đầu tính giờ', 'calcing': 'Đang tính...',
            'unload_title': '✅ Khu vực xuống hàng & Lịch sử', 'unload_wait': 'Khu vực chờ xuống hàng',
            'done_list': 'Lịch sử hoàn thành', 'btn_done': '✅ Hoàn thành',
            'lang_btn': '🇹🇼 Đổi ngôn ngữ (中文)', 'part_no': 'Mã LK:', 'part_name': 'Tên LK:', 'qty': 'SL:', 'color': 'Màu:',
            'ocr_proc': '🖼️ Đang xử lý ảnh...', 'ocr_err': '⚠️ Không tìm thấy chữ rõ ràng', 
            'est_time': 'TG dự kiến: ', 'hrs': ' Giờ ', 'done_time': 'Thời gian HT: ', 'alert_del': '⚠️ Xác nhận xóa dữ liệu này?'
        }
    };
    let currentLang = localStorage.getItem('appLang') || 'zh';
    function t(key) { return i18n[currentLang][key] || key; }
    function toggleLang() {
        currentLang = currentLang === 'zh' ? 'vi' : 'zh';
        localStorage.setItem('appLang', currentLang);
        applyLang();
        if(typeof renderDynamic === 'function') renderDynamic(); 
    }
    function applyLang() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if(el.tagName === 'INPUT') el.placeholder = t(key);
            else el.innerHTML = t(key);
        });
        document.getElementById('langBtn').innerHTML = t('lang_btn');
    }
    window.addEventListener('DOMContentLoaded', applyLang);
</script>
"""

def create_templates():
    if not os.path.exists('templates'):
        os.makedirs('templates')

    html_files = {
        # 1. 模擬器主控台 (放大動態跑圖與中越雙語)
        'simulator.html': f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>粉體塗裝流水線模擬器</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
            <style>
                body {{ font-family: '微軟正黑體', sans-serif; background: #f0f2f5; margin: 0; padding: 20px; }}
                .dashboard {{ background: white; padding: 15px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                .speed-ctrl button {{ font-size: 18px; padding: 5px 15px; margin: 0 10px; cursor: pointer; }}
                
                .factory-map {{ 
                    position: relative; width: 100%; max-width: 1000px; 
                    aspect-ratio: 10 / 8; background: white; 
                    border-radius: 10px; border: 2px solid #ccc; margin: 0 auto;
                }}
                .factory-map svg {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; }}
                
                /* 放大卡片尺寸 30px -> 45px，增強視覺 */
                .mini-card {{ 
                    position: absolute; width: 45px; height: 45px; border-radius: 50%; 
                    border: 3px solid #333; transform: translate(-50%, -50%); cursor: pointer; 
                    display: flex; align-items: center; justify-content: center; font-size: 14px; 
                    color: white; text-shadow: 1px 1px 2px black; font-weight: bold; 
                    transition: all 0.3s; z-index: 10;
                }}
                .mini-card .details {{ display: none; }}
                
                .mini-card.expanded {{
                    width: 220px; height: auto; border-radius: 10px; padding: 15px;
                    z-index: 50; text-align: left; box-shadow: 0 5px 15px rgba(0,0,0,0.5);
                    cursor: default; align-items: flex-start;
                }}
                .mini-card.expanded .short-id {{ display: none; }}
                .mini-card.expanded .details {{ display: block; font-size: 14px; line-height: 1.6; width: 100%; position: relative; }}
                .close-btn {{ 
                    position: absolute; top: -5px; right: 0; font-size: 20px; 
                    cursor: pointer; font-weight: bold; background: rgba(0,0,0,0.4);
                    border-radius: 50%; width: 24px; height: 24px; text-align: center; line-height: 22px;
                }}
            </style>
            {I18N_SCRIPT}
        </head>
        <body onclick="closeAllCards()">
            <div class="dashboard">
                <h2 data-i18n="sim_title">🏭 粉體塗裝流水線模擬器</h2>
                <div class="speed-ctrl">
                    <span data-i18n="speed">流水線轉速: </span><span id="current-speed" style="font-weight:bold; color:red; font-size:20px;">1100</span>
                    <button onclick="changeSpeed(-100); event.stopPropagation();">-100</button>
                    <button onclick="changeSpeed(100); event.stopPropagation();">+100</button>
                    <br><small><span data-i18n="time_lbl">跑完全程所需時間: </span><span id="total-time" style="font-weight:bold;"></span><span data-i18n="mins"> 分鐘</span></small>
                </div>
            </div>
            
            <div class="factory-map" id="map">
                <svg viewBox="0 0 1000 800">
                    <path id="track" d="M 200 150 L 100 150 L 100 50 L 900 50 L 900 150 L 600 150 L 600 220 L 900 220 L 900 290 L 600 290 L 600 360 L 900 360 L 900 750 L 100 750" fill="none" stroke="#ff4d4d" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>
                    <rect x="150" y="125" width="80" height="50" fill="#4d94ff" rx="5"/>
                    <text x="190" y="155" fill="white" font-size="20" text-anchor="middle" data-i18n="map1">上料</text>
                    <rect x="450" y="25" width="100" height="50" fill="#4d94ff" rx="5"/>
                    <text x="500" y="55" fill="white" font-size="20" text-anchor="middle" data-i18n="map2">前處理</text>
                    <rect x="750" y="195" width="100" height="50" fill="#4d94ff" rx="5"/>
                    <text x="800" y="225" fill="white" font-size="20" text-anchor="middle" data-i18n="map3">水切爐</text>
                    <rect x="700" y="450" width="120" height="60" fill="#4d94ff" rx="5"/>
                    <text x="760" y="485" fill="white" font-size="24" text-anchor="middle" data-i18n="map4">噴房</text>
                    <rect x="700" y="650" width="120" height="60" fill="#4d94ff" rx="5"/>
                    <text x="760" y="685" fill="white" font-size="24" text-anchor="middle" data-i18n="map5">烘烤爐</text>
                    <rect x="50" y="725" width="80" height="50" fill="#4d94ff" rx="5"/>
                    <text x="90" y="755" fill="white" font-size="20" text-anchor="middle" data-i18n="map6">下料</text>
                </svg>
            </div>

            <script>
                const socket = io();
                const track = document.getElementById('track');
                const trackLength = track.getTotalLength();
                let speedIndex = 11;
                let activeCardId = null; 
                
                socket.on('update_state', (state) => {{
                    document.getElementById('current-speed').innerText = state.line_speed;
                    speedIndex = state.line_speed / 100;
                    document.getElementById('total-time').innerText = Math.round(1320 / speedIndex);
                    renderLineCards(state.cards);
                }});

                function changeSpeed(val) {{ socket.emit('change_speed', val); }}
                function toggleCard(id, event) {{ event.stopPropagation(); activeCardId = activeCardId === id ? null : id; renderLineCards(sys_state_cache); }}
                function closeAllCards() {{ activeCardId = null; renderLineCards(sys_state_cache); }}
                
                let sys_state_cache = {{}};

                function renderDynamic() {{ renderLineCards(sys_state_cache); }}

                function renderLineCards(cards) {{
                    sys_state_cache = cards;
                    const map = document.getElementById('map');
                    document.querySelectorAll('.mini-card').forEach(e => e.remove());
                    
                    const now = Date.now();
                    const fullTimeMs = (1320 / speedIndex) * 60000;

                    Object.values(cards).forEach(card => {{
                        if(card.status === 'on_line') {{
                            const elapsed = now - card.line_start_time;
                            let progress = elapsed / fullTimeMs;
                            
                            if (progress >= 1) {{
                                progress = 1;
                                socket.emit('auto_move_to_unload', card.id); 
                            }}

                            const point = track.getPointAtLength(progress * trackLength);
                            const div = document.createElement('div');
                            div.className = 'mini-card';
                            if (activeCardId === card.id) div.classList.add('expanded');
                            
                            const xPercent = (point.x / 1000) * 100;
                            const yPercent = (point.y / 800) * 100;
                            div.style.left = xPercent + '%';
                            div.style.top = yPercent + '%';
                            div.style.backgroundColor = card.colorCode || '#333';
                            div.onclick = (e) => toggleCard(card.id, e);
                            
                            // 根據當前語言載入面板標題
                            div.innerHTML = `
                                <span class="short-id">${{card.id.substring(0,3)}}</span>
                                <div class="details">
                                    <div class="close-btn" onclick="toggleCard('${{card.id}}', event)">×</div>
                                    <b>${{t('part_no')}}</b> ${{card.part_no}}<br>
                                    <b>${{t('part_name')}}</b> ${{card.part_name}}<br>
                                    <b>${{t('qty')}}</b> ${{card.qty}}<br>
                                    <b>${{t('color')}}</b> ${{card.color}}
                                </div>
                            `;
                            map.appendChild(div);
                        }}
                    }});
                }}
                setInterval(() => {{ socket.emit('request_sync'); }}, 1000);
            </script>
        </body>
        </html>
        """,

        # 2. 現場待料區 (加入完整色系與精準 OCR Canvas濾鏡)
        'waiting.html': f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>現場待料區</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js"></script>
            <style>
                body {{ font-family: '微軟正黑體', sans-serif; background: #e9ecef; padding: 20px; margin: 0; padding-bottom: 150px;}}
                .form-card {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }}
                .input-group {{ display: flex; gap: 5px; margin: 5px 0; }}
                select, input, button {{ padding: 10px; width: 100%; box-sizing: border-box; border-radius: 4px; border: 1px solid #ccc; font-size: 16px; }}
                .btn-scan {{ background: #6c757d; color: white; width: 80px; flex-shrink: 0; font-weight: bold; cursor: pointer; padding: 5px;}}
                .btn-add {{ background: #28a745; color: white; border: none; cursor: pointer; font-weight: bold; margin-top:10px; }}
                .data-card {{ background: white; padding: 10px; border-radius: 8px; margin-bottom: 10px; border-left: 10px solid #ccc; display: flex; justify-content: space-between; align-items: center;}}
                .btn-send {{ background: #007bff; color: white; width: auto; padding: 8px; font-weight:bold;}}
                .btn-del {{ background: #dc3545; color: white; width: auto; padding: 8px; font-weight:bold;}}
                .fixed-bottom {{ position: fixed; bottom: 0; left: 0; right: 0; height: 120px; background: #343a40; color: white; padding: 10px; overflow-y: auto;}}
                
                #scannerModal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 999; flex-direction: column; align-items: center; justify-content: center; }}
                .video-container {{ position: relative; width: 90%; max-width: 500px; aspect-ratio: 4/3; overflow: hidden; border: 2px solid #fff; border-radius: 10px;}}
                video {{ width: 100%; height: 100%; object-fit: cover; }}
                .scan-box {{ position: absolute; top: 35%; left: 10%; width: 80%; height: 30%; border: 2px solid #00ff00; box-shadow: 0 0 0 9999px rgba(0,0,0,0.6); }}
                .scan-controls {{ margin-top: 20px; display: flex; gap: 15px; }}
                .scan-controls button {{ width: auto; padding: 12px 25px; font-weight: bold; font-size: 16px; border: none;}}
            </style>
            {I18N_SCRIPT}
        </head>
        <body>
            <h2 data-i18n="wait_title">📦 現場待料區</h2>
            <div class="form-card" id="inputForm">
                <select id="colorSelect" onchange="previewColor()">
                    <option value="WE白色,#FFFFFF">WE白色</option>
                    <option value="WES白砂,#F5F5F5">WES白砂</option>
                    <option value="BK黑平光,#333333">BK黑平光</option>
                    <option value="EBK消光黑,#1A1A1A">EBK消光黑</option>
                    <option value="BKH黑錘紋,#2C2C2C">BKH黑錘紋</option>
                    <option value="BKS1黑砂,#111111">BKS1黑砂</option>
                    <option value="BKS5黑砂,#222222">BKS5黑砂</option>
                    <option value="BKSA黑砂閃銀,#3A3A3A">BKSA黑砂閃銀</option>
                    <option value="BKSA1黑閃銀,#444444">BKSA1黑閃銀</option>
                    <option value="PK粉紅色,#FFC0CB">PK粉紅色</option>
                    <option value="RD紅色,#FF0000">RD紅色</option>
                    <option value="OE橘色,#FFA500">OE橘色</option>
                    <option value="OE1橘色,#FF8C00">OE1橘色</option>
                    <option value="OE2橘色,#FF7F50">OE2橘色</option>
                    <option value="YWH黃錘紋,#DAA520">YWH黃錘紋</option>
                    <option value="YW1黃亮光,#FFFF00">YW1黃亮光</option>
                    <option value="GYW鵝黃色,#FFDF00">GYW鵝黃色</option>
                    <option value="GN綠色,#008000">GN綠色</option>
                    <option value="FGN青綠色,#00FF7F">FGN青綠色</option>
                    <option value="BE藍色,#0000FF">BE藍色</option>
                    <option value="BEG艷藍色,#1E90FF">BEG艷藍色</option>
                    <option value="DBE深藍色,#00008B">DBE深藍色</option>
                    <option value="PEL紫色,#800080">PEL紫色</option>
                    <option value="IG灰色,#808080">IG灰色</option>
                    <option value="IGS灰砂紋,#A9A9A9">IGS灰砂紋</option>
                    <option value="DGS藍砂紋,#536878">DGS藍砂紋</option>
                    <option value="ATG深灰,#696969">ATG深灰</option>
                    <option value="SAT2閃銀,#C0C0C0">SAT2閃銀</option>
                    <option value="GSAT黃金色,#FFD700">GSAT黃金色</option>
                </select>
                <div class="input-group">
                    <input type="text" id="partNo" data-i18n="part_ph" placeholder="手動輸入或掃描料號"> 
                    <button type="button" class="btn-scan" data-i18n="scan_btn" onclick="openScanner('partNo')">📷 掃描</button>
                </div>
                <div class="input-group">
                    <input type="text" id="partName" data-i18n="name_ph" placeholder="手動輸入或掃描品名">
                    <button type="button" class="btn-scan" data-i18n="scan_btn" onclick="openScanner('partName')">📷 掃描</button>
                </div>
                <input type="number" id="qty" placeholder="數量 / Số lượng">
                <button class="btn-add" data-i18n="add_btn" onclick="createCard()">➕ 新增待上線構件</button>
            </div>

            <hr>
            <h3 data-i18n="list_wait">待處理清單 (順序排列)</h3>
            <div id="waiting-list"></div>
            <div class="fixed-bottom">
                <h4 data-i18n="ali_sync" style="margin-top:5px;">[待上料_阿利] 同步接收區</h4>
                <div id="ali-list"></div>
            </div>

            <div id="scannerModal">
                <h3 id="scanTitle" data-i18n="ocr_title" style="color: white; margin-bottom:10px;">辨識系統</h3>
                <div class="video-container">
                    <video id="videoElement" autoplay playsinline></video>
                    <div class="scan-box"></div>
                </div>
                <p id="scanStatus" data-i18n="ocr_tip" style="color:#00ff00; margin-top:15px; font-weight:bold;">請將文字對準綠色框框內</p>
                <div class="scan-controls">
                    <button onclick="captureAndRecognize()" data-i18n="btn_pic" style="background:#28a745; color:white;">📸 拍照辨識</button>
                    <button onclick="closeScanner()" data-i18n="btn_close" style="background:#dc3545; color:white;">關閉</button>
                </div>
                <canvas id="canvasElement" style="display:none;"></canvas>
            </div>

            <script>
                const socket = io();
                let sys_state_cache = {{cards:{{}}}};
                
                function previewColor() {{
                    const val = document.getElementById('colorSelect').value.split(',');
                    document.getElementById('inputForm').style.backgroundColor = val[1];
                }}

                function createCard() {{
                    const colorData = document.getElementById('colorSelect').value.split(',');
                    const data = {{
                        id: Date.now().toString(),
                        color: colorData[0],
                        colorCode: colorData[1],
                        part_no: document.getElementById('partNo').value || '未填寫',
                        part_name: document.getElementById('partName').value || '未填寫',
                        qty: document.getElementById('qty').value || 0,
                        status: 'waiting'
                    }};
                    socket.emit('add_card', data);
                    document.getElementById('partNo').value = '';
                    document.getElementById('partName').value = '';
                    document.getElementById('qty').value = '';
                }}

                function renderDynamic() {{
                    const waitList = document.getElementById('waiting-list');
                    const aliList = document.getElementById('ali-list');
                    waitList.innerHTML = ''; aliList.innerHTML = '';

                    Object.values(sys_state_cache.cards).forEach(card => {{
                        const div = document.createElement('div');
                        div.className = 'data-card';
                        div.style.borderColor = card.colorCode;
                        div.innerHTML = `
                            <div><b>${{card.part_no}}</b> (${{card.part_name}}) - ${{card.color}} x ${{card.qty}}</div>
                            <div style="display:flex; gap:5px;">
                                ${{card.status === 'waiting' ? 
                                    `<button class="btn-send" onclick="sendToAli('${{card.id}}')">${{t('btn_send_ali')}}</button>
                                     <button class="btn-del" onclick="delCard('${{card.id}}')">${{t('btn_del')}}</button>` 
                                    : ''}}
                            </div>
                        `;
                        if(card.status === 'waiting') {{ waitList.appendChild(div); }}
                        if(card.status === 'loading') {{ aliList.appendChild(div.cloneNode(true)); }}
                    }});
                }}

                socket.on('update_state', (state) => {{
                    sys_state_cache = state;
                    renderDynamic();
                }});

                function sendToAli(id) {{ socket.emit('change_status', {{id: id, status: 'loading'}}); }}
                function delCard(id) {{ if(confirm(t('alert_del'))) {{ socket.emit('delete_card', id); }} }}

                let currentScanTarget = '';
                let stream = null;
                const video = document.getElementById('videoElement');
                const canvas = document.getElementById('canvasElement');
                const ctx = canvas.getContext('2d');

                async function openScanner(target) {{
                    currentScanTarget = target;
                    document.getElementById('scannerModal').style.display = 'flex';
                    document.getElementById('scanStatus').innerText = t('ocr_tip');
                    
                    try {{
                        stream = await navigator.mediaDevices.getUserMedia({{
                            video: {{ facingMode: 'environment', advanced: [{{ focusMode: "continuous" }}] }}
                        }});
                        video.srcObject = stream;
                    }} catch (err) {{
                        document.getElementById('scanStatus').innerText = '無法存取相機 / Lỗi Camera';
                    }}
                }}

                function closeScanner() {{
                    document.getElementById('scannerModal').style.display = 'none';
                    if(stream) {{ stream.getTracks().forEach(track => track.stop()); }}
                }}

                async function captureAndRecognize() {{
                    document.getElementById('scanStatus').innerText = t('ocr_proc');
                    video.pause();
                    
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

                    const cropX = canvas.width * 0.10;
                    const cropY = canvas.height * 0.35;
                    const cropW = canvas.width * 0.80;
                    const cropH = canvas.height * 0.30;
                    
                    const cropCanvas = document.createElement('canvas');
                    cropCanvas.width = cropW;
                    cropCanvas.height = cropH;
                    const cropCtx = cropCanvas.getContext('2d');
                    
                    // 【精準優化】增加對比、去色，使 Tesseract 在工業低光源環境辨識大幅提升
                    cropCtx.filter = 'contrast(200%) brightness(120%) grayscale(100%)';
                    cropCtx.drawImage(canvas, cropX, cropY, cropW, cropH, 0, 0, cropW, cropH);

                    const langType = currentScanTarget === 'partNo' ? 'eng' : 'chi_tra+eng';
                    
                    try {{
                        const {{ data: {{ text }} }} = await Tesseract.recognize(
                            cropCanvas,
                            langType,
                            {{ logger: m => {{ if (m.status === 'recognizing text') {{
                                document.getElementById('scanStatus').innerText = `${{Math.round(m.progress * 100)}}%`;
                            }}}}}}
                        );
                        
                        const cleanText = text.replace(/\\n/g, ' ').trim();
                        if (cleanText) {{
                            document.getElementById(currentScanTarget).value = cleanText;
                            closeScanner();
                            video.play();
                        }} else {{
                            document.getElementById('scanStatus').innerText = t('ocr_err');
                            video.play();
                        }}
                    }} catch(e) {{
                        document.getElementById('scanStatus').innerText = 'Error';
                        video.play();
                    }}
                }}
            </script>
        </body>
        </html>
        """,

        # 3. 待上料_阿利 (雙語切換支援)
        'loading.html': f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>待上料_阿利</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
            <style>
                body {{ font-family: '微軟正黑體', sans-serif; background: #e2e8f0; padding: 20px; padding-bottom: 150px;}}
                .card {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 10px solid #ccc;}}
                .grid-form {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; margin-top: 10px; }}
                select, button {{ padding: 8px; width: 100%; box-sizing: border-box; }}
                .btn-line {{ background: #ff9800; color: white; border: none; padding: 10px; border-radius: 4px; cursor: pointer; margin-top: 10px; font-weight:bold;}}
                .fixed-bottom {{ position: fixed; bottom: 0; left: 0; right: 0; height: 80px; background: #2c3e50; color: white; padding: 15px; text-align: center; font-size: 18px; font-weight: bold;}}
                .time-calc {{ font-size: 14px; color: #d35400; font-weight: bold; margin-top: 10px; }}
            </style>
            {I18N_SCRIPT}
        </head>
        <body>
            <h2 data-i18n="ali_title">🏗️ 待上料_阿利</h2>
            <div id="loading-list"></div>
            
            <div class="fixed-bottom" data-i18n="line_sync">
                ⬇️ [流水線_上線] 同步傳送區 ⬇️
            </div>

            <script>
                const socket = io();
                let currentSpeed = 1100;
                let sys_state_cache = {{cards:{{}}}};

                function renderDynamic() {{
                    const list = document.getElementById('loading-list');
                    list.innerHTML = '';
                    
                    Object.values(sys_state_cache.cards).forEach(card => {{
                        if(card.status === 'loading') {{
                            const div = document.createElement('div');
                            div.className = 'card';
                            div.style.borderColor = card.colorCode;
                            div.innerHTML = `
                                <strong>${{t('part_no')}} ${{card.part_no}} | ${{t('part_name')}} ${{card.part_name}} | ${{t('qty')}} ${{card.qty}} | ${{t('color')}} ${{card.color}}</strong>
                                <div class="grid-form">
                                    <label>${{t('lbl_hang')}} <select id="hang_${{card.id}}" onchange="calcTime('${{card.id}}', ${{card.qty}})"><option value="1">1</option><option value="2">2</option></select></label>
                                    <label>${{t('lbl_empty')}} <select id="empty_${{card.id}}" onchange="calcTime('${{card.id}}', ${{card.qty}})">${{genOptions(10)}}</select></label>
                                    <label>${{t('lbl_space')}} <select id="interval_${{card.id}}" onchange="calcTime('${{card.id}}', ${{card.qty}})">${{genOptions(10)}}</select></label>
                                    <label>${{t('lbl_hook')}} <select id="hook_${{card.id}}">${{genOptions(10)}}</select></label>
                                </div>
                                <div class="time-calc" id="time_${{card.id}}">${{t('calcing')}}</div>
                                <button class="btn-line" onclick="sendToLine('${{card.id}}')">${{t('btn_to_line')}}</button>
                            `;
                            list.appendChild(div);
                            setTimeout(() => calcTime(card.id, card.qty), 100);
                        }}
                    }});
                }}

                socket.on('update_state', (state) => {{
                    currentSpeed = state.line_speed;
                    sys_state_cache = state;
                    renderDynamic();
                }});

                function genOptions(max) {{
                    let html = '';
                    for(let i=0; i<=max; i++) html += `<option value="${{i}}">${{i}}</option>`;
                    return html;
                }}

                function calcTime(id, qty) {{
                    const hang = parseFloat(document.getElementById('hang_' + id).value) || 0;
                    const empty = parseFloat(document.getElementById('empty_' + id).value) || 0;
                    const interval = parseFloat(document.getElementById('interval_' + id).value) || 0;
                    const speedIndex = currentSpeed / 100;
                    
                    const totalMins = Math.round(((hang + empty + interval) * qty) / speedIndex);
                    const h = Math.floor(totalMins / 60);
                    const m = totalMins % 60;
                    document.getElementById('time_' + id).innerText = `${{t('est_time')}} ${{h}} ${{t('hrs')}} ${{m}} ${{t('mins')}}`;
                }}

                function sendToLine(id) {{ socket.emit('send_to_line', id); }}
            </script>
        </body>
        </html>
        """,

        # 4. 下料_完成
        'unloading.html': f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>下料_完成</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
            <style>
                body {{ font-family: '微軟正黑體', sans-serif; background: #fdf2e9; padding: 20px;}}
                .card {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 10px; border-left: 10px solid #ccc; display: flex; justify-content: space-between; align-items: center;}}
                .btn-done {{ background: #27ae60; color: white; border: none; padding: 10px; border-radius: 4px; cursor: pointer; font-weight:bold;}}
                .record {{ font-size: 12px; color: #7f8c8d; margin-top: 5px;}}
            </style>
            {I18N_SCRIPT}
        </head>
        <body>
            <h2 data-i18n="unload_title">✅ 下料與完成紀錄區</h2>
            <h3 data-i18n="unload_wait">待下料區 (模擬器跑完自動傳送至此)</h3>
            <div id="unload-list"></div>
            <hr>
            <h3 data-i18n="done_list">歷史完成紀錄</h3>
            <div id="done-list"></div>

            <script>
                const socket = io();
                let sys_state_cache = {{cards:{{}}}};

                function renderDynamic() {{
                    const unloadList = document.getElementById('unload-list');
                    const doneList = document.getElementById('done-list');
                    unloadList.innerHTML = ''; doneList.innerHTML = '';

                    Object.values(sys_state_cache.cards).forEach(card => {{
                        const div = document.createElement('div');
                        div.className = 'card';
                        div.style.borderColor = card.colorCode;
                        
                        if(card.status === 'unloading') {{
                            div.innerHTML = `
                                <div><b>${{card.part_no}}</b> - ${{card.color}} x ${{card.qty}}</div>
                                <button class="btn-done" onclick="finishCard('${{card.id}}')">${{t('btn_done')}}</button>
                            `;
                            unloadList.appendChild(div);
                        }} else if(card.status === 'completed') {{
                            div.innerHTML = `
                                <div><b>${{card.part_no}}</b> - ${{card.color}} x ${{card.qty}}<br>
                                <span class="record">${{t('done_time')}} ${{card.finish_time}}</span></div>
                            `;
                            doneList.appendChild(div);
                        }}
                    }});
                }}

                socket.on('update_state', (state) => {{
                    sys_state_cache = state;
                    renderDynamic();
                }});

                function finishCard(id) {{ socket.emit('finish_card', id); }}
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

@app.route('/')
def index(): return render_template('simulator.html')
@app.route('/wait')
def wait(): return render_template('waiting.html')
@app.route('/load')
def load(): return render_template('loading.html')
@app.route('/unload')
def unload(): return render_template('unloading.html')

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
        tw_time = time.gmtime(time.time() + 8 * 3600)
        sys_state['cards'][card_id]['finish_time'] = time.strftime("%Y-%m-%d %H:%M:%S", tw_time)
        broadcast_state()

if __name__ == '__main__':
    # 注意：重構開發時，如需重置 HTML 更新，請先砍掉舊有的 templates 資料夾讓程式重寫
    import shutil
    if os.path.exists('templates'):
        shutil.rmtree('templates')
    
    create_templates() 
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
