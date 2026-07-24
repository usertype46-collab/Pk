import os
import time
import threading
from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

sys_state = {
    'line_speed': 1100,
    'cards': {},
    'active_card_id': None
}

active_card_lock = threading.Lock()
current_active_card_template = None
clone_counter = 0

I18N_SCRIPT = """
<style>
    body { padding-top: 60px !important; }
    .lang-btn { position: fixed; top: 10px; right: 10px; z-index: 1000; background: #34495e; color: white; border: none; padding: 10px 15px; border-radius: 20px; cursor: pointer; font-weight: bold; font-size: 13px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); transition: 0.3s; }
    .lang-btn:hover { background: #2c3e50; }
</style>
<button class="lang-btn" id="langBtn" onclick="toggleLang()">🌐 切換語言 / Ngôn ngữ</button>
<script>
    const i18n = {
        'zh': {
            'sim_title': '🏭 粉體塗裝流水線模擬器', 'speed': '流水線轉速: ', 'time_lbl': '跑完全程所需時間: ', 'mins': ' 分鐘',
            'wait_title': '📦 現場待料區', 'part_ph': '手動輸入或掃描料號', 'name_ph': '手動輸入或掃描品名',
            'scan_btn': '📷 掃描', 'add_btn': '➕ 新增待上線構件', 'list_wait': '待處理清單 (順序排列)',
            'ali_sync': '[待上料_阿利] 同步接收區', 'btn_send_ali': '➕ 傳送阿利', 'btn_del': '刪除',
            'ocr_title': '📸 拍照系統', 'ocr_tip': '請將目標對準綠色框框內', 'btn_pic': '📸 拍照儲存', 'btn_close': '關閉',
            'ali_title': '🏗️ 待上料_阿利', 'line_sync': '⬇️ [流水線_上線] 同步傳送區 ⬇️',
            'lbl_hang': '掛:', 'lbl_empty': '空:', 'lbl_space': '間隔:', 'lbl_hook': '接勾:',
            'btn_to_line': '🚀 上線並開始持續滿線插入', 'calcing': '計算上線時間...',
            'unload_title': '✅ 下料與完成紀錄區', 'unload_wait': '待下料區 (模擬器跑完自動傳送至此)',
            'done_list': '歷史完成紀錄', 'btn_done': '✅ 點擊完成',
            'lang_btn': '🇻🇳 切換為越文 (Việt)', 'part_no': '料號:', 'part_name': '品名:', 'qty': '數量:', 'color': '顏色:',
            'est_time': '預估佔線時間: ', 'hrs': ' 小時 ', 'done_time': '完成時間: ', 'alert_del': '⚠️ 確定要刪除這筆資料嗎？',
            'comp_lbl': '構件', 'full_line_status': '⚡ 滿線模式持續上料中: ', 'none_loading': '暫無 (等待上料)'
        },
        'vi': {
            'sim_title': '🏭 Trình mô phỏng chuyền sơn', 'speed': 'Tốc độ chuyền: ', 'time_lbl': 'Thời gian 1 vòng: ', 'mins': ' Phút',
            'wait_title': '📦 Khu vực chờ vật liệu', 'part_ph': 'Nhập / Quét mã LK', 'name_ph': 'Nhập / Quét tên LK',
            'scan_btn': '📷 Quét', 'add_btn': '➕ Thêm vào hàng chờ', 'list_wait': 'Danh sách chờ (Theo thứ tự)',
            'ali_sync': 'Khu vực đồng bộ [Chờ lên hàng_Ali]', 'btn_send_ali': '➕ Chuyển cho Ali', 'btn_del': 'Xóa',
            'ocr_title': '📸 Hệ thống chụp', 'ocr_tip': 'Căn chỉnh văn bản vào khung xanh', 'btn_pic': '📸 Chụp & Lưu', 'btn_close': 'Đóng',
            'ali_title': '🏗️ Chờ lên hàng_Ali', 'line_sync': '⬇️ [Dây chuyền] Truyền đồng bộ ⬇️',
            'lbl_hang': 'Treo:', 'lbl_empty': 'Trống:', 'lbl_space': 'Cách:', 'lbl_hook': 'Móc:',
            'btn_to_line': '🚀 Lên chuyền & Nạp liên tục', 'calcing': 'Đang tính...',
            'unload_title': '✅ Khu vực xuống hàng & Lịch sử', 'unload_wait': 'Khu vực chờ xuống hàng',
            'done_list': 'Lịch sử hoàn thành', 'btn_done': '✅ Hoàn thành',
            'lang_btn': '🇹🇼 Đổi ngôn ngữ (中文)', 'part_no': 'Mã LK:', 'part_name': 'Tên LK:', 'qty': 'SL:', 'color': 'Màu:',
            'est_time': 'TG dự kiến: ', 'hrs': ' Giờ ', 'done_time': 'Thời gian HT: ', 'alert_del': 'Xác nhận xóa dữ liệu này?',
            'comp_lbl': 'Cấu kiện', 'full_line_status': '⚡ Đang nạp hàng liên tục: ', 'none_loading': 'Chưa có'
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
        const langBtn = document.getElementById('langBtn');
        if(langBtn) langBtn.innerHTML = t('lang_btn');
    }
    function renderField(val) {
        if (typeof val === 'string' && val.startsWith('data:image')) {
            return `<img src="${val}" style="max-height: 40px; vertical-align: middle; border-radius: 4px; border: 1px solid #ccc; margin: 2px;">`;
        }
        return val;
    }
    window.addEventListener('DOMContentLoaded', applyLang);
</script>
"""

def create_templates():
    if not os.path.exists('templates'):
        os.makedirs('templates')

    html_files = {
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
                .status-banner {{ background: #27ae60; color: white; padding: 10px; border-radius: 6px; font-weight: bold; margin-top: 10px; display: flex; align-items: center; justify-content: space-between; }}
                
                .factory-map {{ 
                    position: relative; width: 100%; max-width: 768px; 
                    aspect-ratio: 768 / 1024;
                    background: url('/14436.png') no-repeat center center;
                    background-size: cover;
                    border-radius: 10px; border: 2px solid #ccc; margin: 0 auto;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                    overflow: hidden;
                }}
                .factory-map svg {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; pointer-events: none; }}
                
                .chain-track {{
                    stroke-dasharray: 10, 8;
                    animation: moveChain 1.5s linear infinite;
                    opacity: 0.85;
                }}
                @keyframes moveChain {{
                    from {{ stroke-dashoffset: 18; }}
                    to {{ stroke-dashoffset: 0; }}
                }}

                .mini-card {{ 
                    position: absolute; width: auto; min-width: 50px; height: 26px; border-radius: 4px; 
                    border: 2px solid #fff; box-shadow: 0 2px 5px rgba(0,0,0,0.5); transform: translate(-50%, -50%); cursor: pointer; 
                    display: flex; align-items: center; justify-content: center; font-size: 12px; 
                    color: white; text-shadow: 1px 1px 2px black; font-weight: bold; 
                    transition: all 0.3s; z-index: 10; padding: 0 5px; white-space: nowrap;
                }}
                .mini-card .details {{ display: none; }}
                
                #overlay {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 9990; }}
                .mini-card.expanded {{
                    position: fixed !important; top: 50% !important; left: 50% !important;
                    transform: translate(-50%, -50%) !important;
                    width: 85vw; max-width: 350px; height: auto; border-radius: 12px; padding: 20px;
                    z-index: 9999; text-align: left; box-shadow: 0 10px 25px rgba(0,0,0,0.5);
                    cursor: default; display: flex; flex-direction: column; white-space: normal; background-color: #34495e !important;
                }}
                .mini-card.expanded .short-id {{ display: none; }}
                .mini-card.expanded .details {{ display: block; font-size: 16px; line-height: 1.8; width: 100%; position: relative; color: white; }}
                
                .close-btn {{ 
                    position: absolute; top: -10px; right: -10px; font-size: 24px; 
                    cursor: pointer; font-weight: bold; background: rgba(0,0,0,0.7);
                    border-radius: 50%; width: 32px; height: 32px; text-align: center; line-height: 28px; border: 2px solid white; color: white;
                }}
            </style>
            {I18N_SCRIPT}
        </head>
        <body onclick="closeAllCards()">
            <div id="overlay"></div>
            <div class="dashboard">
                <h2 data-i18n="sim_title">🏭 粉體塗裝流水線模擬器</h2>
                <div class="speed-ctrl">
                    <span data-i18n="speed">流水線轉速: </span><span id="current-speed" style="font-weight:bold; color:red; font-size:20px;">1100</span>
                    <button onclick="changeSpeed(-100); event.stopPropagation();">-100</button>
                    <button onclick="changeSpeed(100); event.stopPropagation();">+100</button>
                    <br><small><span data-i18n="time_lbl">跑完全程所需時間: </span><span id="total-time" style="font-weight:bold;"></span><span data-i18n="mins"> 分鐘</span></small>
                </div>
                <div class="status-banner" id="active-banner">
                    <span><span data-i18n="full_line_status">⚡ 滿線模式持續上料中: </span><span id="active-card-name" style="text-decoration:underline;">暫無</span></span>
                </div>
            </div>
            
            <div class="factory-map" id="map">
                <svg viewBox="0 0 1000 1333" preserveAspectRatio="none">
                    <!--
                    【調整後校正軌道】
                    上料 -> 前處理(上方) -> 水切爐 -> 烘烤爐/噴房 -> 下料(下方)
                    -->
                    <path id="track" d="
                        M 458 1180
                        L 458 280
                        L 121 280
                        L 121 98
                        L 921 98
                        L 921 205
                        L 580 205
                        L 580 280
                        L 921 280
                        L 921 370
                        L 580 370
                        L 580 310
                        L 921 310
                        L 921 530
                        L 580 530
                        L 580 590
                        L 921 590
                        L 921 1180
                        L 458 1180 Z" 
                        fill="none" stroke="#e74c3c" stroke-width="8" stroke-linecap="round" stroke-linejoin="round" class="chain-track"/>
                </svg>
            </div>

            <script>
                const socket = io();
                const track = document.getElementById('track');
                const overlay = document.getElementById('overlay');
                const trackLength = track.getTotalLength();
                let speedIndex = 11;
                let activeCardId = null; 
                let sys_state_cache = {{cards:{{}}, active_card_id: null}};
                
                socket.on('update_state', (state) => {{
                    document.getElementById('current-speed').innerText = state.line_speed;
                    speedIndex = state.line_speed / 100;
                    document.getElementById('total-time').innerText = Math.round(1320 / speedIndex);
                    
                    sys_state_cache = state;
                    updateActiveBanner();
                    renderLineCards(state.cards);
                }});

                function changeSpeed(val) {{ socket.emit('change_speed', val); }}
                
                function toggleCard(id, event) {{ 
                    event.stopPropagation(); 
                    activeCardId = activeCardId === id ? null : id;
                    overlay.style.display = activeCardId ? 'block' : 'none';
                    renderLineCards(sys_state_cache.cards); 
                }}
                
                function closeAllCards() {{ 
                    activeCardId = null; 
                    overlay.style.display = 'none';
                    renderLineCards(sys_state_cache.cards); 
                }}

                function updateActiveBanner() {{
                    const activeId = sys_state_cache.active_card_id;
                    const el = document.getElementById('active-card-name');
                    if (activeId && sys_state_cache.cards[activeId]) {{
                        const c = sys_state_cache.cards[activeId];
                        let name = c.part_name && !c.part_name.startsWith('data:image') ? c.part_name : c.part_no;
                        el.innerHTML = `${{renderField(name)}} (${{c.color}})`;
                    }} else {{
                        el.innerHTML = t('none_loading');
                    }}
                }}

                function renderDynamic() {{ 
                    updateActiveBanner();
                    renderLineCards(sys_state_cache.cards); 
                }}

                function renderLineCards(cards) {{
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
                            
                            if (activeCardId === card.id) {{
                                div.classList.add('expanded');
                                div.style.left = '50%';
                                div.style.top = '50%';
                            }} else {{
                                const xPercent = (point.x / 1000) * 100;
                                const yPercent = (point.y / 1333) * 100;
                                div.style.left = xPercent + '%';
                                div.style.top = yPercent + '%';
                            }}
                            
                            div.style.backgroundColor = card.colorCode || '#333';
                            div.onclick = (e) => toggleCard(card.id, e);
                            
                            let shortLabel = t('comp_lbl');
                            if (card.part_name && !card.part_name.startsWith('data:image') && card.part_name !== '未填寫') {{
                                shortLabel = card.part_name;
                            }} else if (card.part_no && !card.part_no.startsWith('data:image') && card.part_no !== '未填寫') {{
                                shortLabel = card.part_no;
                            }}
                            
                            div.innerHTML = `
                                <span class="short-id">${{shortLabel}}</span>
                                <div class="details">
                                    <div class="close-btn" onclick="toggleCard('${{card.id}}', event)">×</div>
                                    <b>${{t('part_no')}}</b> ${{renderField(card.part_no)}}<br>
                                    <b>${{t('part_name')}}</b> ${{renderField(card.part_name)}}<br>
                                    <b>機/櫃:</b> ${{renderField(card.model_no) || '未填寫'}}<br>
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

        'waiting.html': f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>現場待料區</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
            <style>
                body {{ font-family: '微軟正黑體', sans-serif; background: #e9ecef; padding: 20px; margin: 0; padding-bottom: 150px;}}
                .form-card {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }}
                .input-group {{ display: flex; gap: 5px; margin: 5px 0; align-items: center; }}
                select, input, button {{ padding: 10px; width: 100%; box-sizing: border-box; border-radius: 4px; border: 1px solid #ccc; font-size: 16px; }}
                .btn-scan {{ background: #6c757d; color: white; width: 80px; flex-shrink: 0; font-weight: bold; cursor: pointer; padding: 5px;}}
                .btn-add {{ background: #28a745; color: white; border: none; cursor: pointer; font-weight: bold; margin-top:10px; }}
                .data-card {{ background: white; padding: 10px; border-radius: 8px; margin-bottom: 10px; border-left: 10px solid #ccc; display: flex; justify-content: space-between; align-items: center;}}
                .btn-send {{ background: #007bff; color: white; width: auto; padding: 8px; font-weight:bold;}}
                .btn-del {{ background: #dc3545; color: white; width: auto; padding: 8px; font-weight:bold;}}
                .fixed-bottom {{ position: fixed; bottom: 0; left: 0; right: 0; height: 120px; background: #343a40; color: white; padding: 10px; overflow-y: auto; z-index: 50;}}
                
                #scannerModal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 999; flex-direction: column; align-items: center; justify-content: center; }}
                .video-container {{ position: relative; width: 90%; max-width: 500px; aspect-ratio: 4/3; overflow: hidden; border: 2px solid #fff; border-radius: 10px;}}
                video {{ width: 100%; height: 100%; object-fit: cover; }}
                .scan-box {{ position: absolute; top: 35%; left: 10%; width: 80%; height: 30%; border: 2px solid #00ff00; box-shadow: 0 0 0 9999px rgba(0,0,0,0.6); pointer-events: none; }}
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
                <div class="input-group" id="partNoGroup">
                    <input type="text" id="partNo" data-i18n="part_ph" placeholder="手動輸入或掃描料號"> 
                    <button type="button" class="btn-scan" data-i18n="scan_btn" onclick="openScanner('partNo')">📷 掃描</button>
                </div>
                <div class="input-group" id="partNameGroup">
                    <input type="text" id="partName" data-i18n="name_ph" placeholder="手動輸入或掃描品名">
                    <button type="button" class="btn-scan" data-i18n="scan_btn" onclick="openScanner('partName')">📷 掃描</button>
                </div>
                <div class="input-group" id="modelNoGroup">
                    <input type="text" id="modelNo" placeholder="機種第幾櫃 (手動輸入 / Nhập model)">
                    <button type="button" class="btn-scan" data-i18n="scan_btn" onclick="openScanner('modelNo')">📷 掃描</button>
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
                <h3 id="scanTitle" data-i18n="ocr_title" style="color: white; margin-bottom:10px;">📸 拍照系統</h3>
                <div class="video-container">
                    <video id="videoElement" autoplay playsinline></video>
                    <div class="scan-box"></div>
                </div>
                <p id="scanStatus" data-i18n="ocr_tip" style="color:#00ff00; margin-top:15px; font-weight:bold;">請將目標對準綠色框框內</p>
                <div class="scan-controls">
                    <button onclick="captureAndStore()" data-i18n="btn_pic" style="background:#28a745; color:white;">📸 拍照儲存</button>
                    <button onclick="closeScanner()" data-i18n="btn_close" style="background:#dc3545; color:white;">關閉</button>
                </div>
                <canvas id="canvasElement" style="display:none;"></canvas>
            </div>

            <script>
                const socket = io();
                let sys_state_cache = {{cards:{{}}}};
                let scanData = {{ partNo: '', partName: '', modelNo: '' }}; 
                
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
                        part_no: scanData.partNo || document.getElementById('partNo').value || '未填寫',
                        part_name: scanData.partName || document.getElementById('partName').value || '未填寫',
                        model_no: scanData.modelNo || document.getElementById('modelNo').value || '', 
                        qty: document.getElementById('qty').value || 0,
                        status: 'waiting'
                    }};
                    socket.emit('add_card', data);
                    
                    scanData = {{ partNo: '', partName: '', modelNo: '' }};
                    document.getElementById('partNo').value = '';
                    document.getElementById('partName').value = '';
                    document.getElementById('modelNo').value = '';
                    document.getElementById('qty').value = '';
                    if(document.getElementById('partNoPreview')) document.getElementById('partNoPreview').remove();
                    if(document.getElementById('partNamePreview')) document.getElementById('partNamePreview').remove();
                    if(document.getElementById('modelNoPreview')) document.getElementById('modelNoPreview').remove();
                }}

                function renderDynamic() {{
                    const waitList = document.getElementById('waiting-list');
                    const aliList = document.getElementById('ali-list');
                    waitList.innerHTML = ''; aliList.innerHTML = '';

                    Object.values(sys_state_cache.cards).forEach(card => {{
                        const div = document.createElement('div');
                        div.className = 'data-card';
                        div.style.borderColor = card.colorCode;
                        
                        let modelInfo = card.model_no ? ` [${{renderField(card.model_no)}}]` : '';
                        
                        div.innerHTML = `
                            <div><b>${{renderField(card.part_no)}}</b> (${{renderField(card.part_name)}})${{modelInfo}} - ${{card.color}} x ${{card.qty}}</div>
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
                            video: {{ 
                                facingMode: 'environment', 
                                width: {{ ideal: 1280 }}, 
                                height: {{ ideal: 720 }} 
                            }}
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

                function captureAndStore() {{
                    video.pause();
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

                    const vw = video.videoWidth;
                    const vh = video.videoHeight;
                    const cw = video.clientWidth;
                    const ch = video.clientHeight;

                    const intrinsicAspect = vw / vh;
                    const renderedAspect = cw / ch;

                    let scale, offsetX = 0, offsetY = 0;
                    if (intrinsicAspect > renderedAspect) {{
                        scale = ch / vh;
                        offsetX = (cw - (vw * scale)) / 2;
                    }} else {{
                        scale = cw / vw;
                        offsetY = (ch - (vh * scale)) / 2;
                    }}

                    const boxLeft = cw * 0.10;
                    const boxTop = ch * 0.35;
                    const boxWidth = cw * 0.80;
                    const boxHeight = ch * 0.30;

                    const cropX = (boxLeft - offsetX) / scale;
                    const cropY = (boxTop - offsetY) / scale;
                    const cropW = boxWidth / scale;
                    const cropH = boxHeight / scale;
                    
                    const cropCanvas = document.createElement('canvas');
                    const maxW = 400;
                    const scaleFactor = cropW > maxW ? maxW / cropW : 1;
                    cropCanvas.width = cropW * scaleFactor;
                    cropCanvas.height = cropH * scaleFactor;
                    const cropCtx = cropCanvas.getContext('2d');
                    cropCtx.scale(scaleFactor, scaleFactor);
                    cropCtx.drawImage(canvas, cropX, cropY, cropW, cropH, 0, 0, cropW, cropH);

                    const base64Img = cropCanvas.toDataURL('image/jpeg', 0.85);
                    scanData[currentScanTarget] = base64Img;
                    
                    const inputEl = document.getElementById(currentScanTarget);
                    inputEl.value = '[🖼️ 已儲存照片]';
                    
                    let previewEl = document.getElementById(currentScanTarget + 'Preview');
                    if(!previewEl) {{
                        previewEl = document.createElement('img');
                        previewEl.id = currentScanTarget + 'Preview';
                        previewEl.style = "max-height: 40px; margin-left: 5px; border-radius: 4px; border: 1px solid #ccc; cursor: pointer;";
                        previewEl.title = "點擊刪除照片";
                        previewEl.onclick = function() {{
                            scanData[currentScanTarget] = '';
                            this.remove();
                            inputEl.value = '';
                        }};
                        document.getElementById(currentScanTarget + 'Group').insertBefore(previewEl, inputEl.nextSibling);
                    }}
                    previewEl.src = base64Img;

                    closeScanner();
                    video.play();
                }}
            </script>
        </body>
        </html>
        """,

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
                .fixed-bottom {{ position: fixed; bottom: 0; left: 0; right: 0; height: 80px; background: #2c3e50; color: white; padding: 15px; text-align: center; font-size: 18px; font-weight: bold; z-index:50;}}
                .time-calc {{ font-size: 14px; color: #d35400; font-weight: bold; margin-top: 10px; }}
            </style>
            {I18N_SCRIPT}
        </head>
        <body>
            <h2 data-i18n="ali_title">🏗️ 待上料_阿利</h2>
            <div id="loading-list"></div>
            <div class="fixed-bottom" data-i18n="line_sync">⬇️ [流水線_上線] 同步傳送區 ⬇️</div>

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
                                <strong>${{t('part_no')}} ${{renderField(card.part_no)}} | ${{t('part_name')}} ${{renderField(card.part_name)}} | ${{card.model_no ? '機/櫃: ' + renderField(card.model_no) + ' | ' : ''}}${{t('qty')}} ${{card.qty}} | ${{t('color')}} ${{card.color}}</strong>
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

                function sendToLine(id) {{
                    const hang = parseInt(document.getElementById('hang_' + id).value) || 1;
                    const empty = parseInt(document.getElementById('empty_' + id).value) || 0;
                    const interval = parseInt(document.getElementById('interval_' + id).value) || 0;
                    const hook = parseInt(document.getElementById('hook_' + id).value) || 0;
                    socket.emit('send_to_line', {{ id: id, hang: hang, empty: empty, interval: interval, hook: hook }}); 
                }}
            </script>
        </body>
        </html>
        """,

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
                .done-table-container {{ overflow-x: auto; background: white; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .done-table {{ width: 100%; border-collapse: collapse; min-width: 600px; text-align: center; font-size: 14px;}}
                .done-table th, .done-table td {{ border: 1px solid #dee2e6; padding: 12px 8px; }}
                .done-table th {{ background: #34495e; color: white; font-weight: bold; white-space: nowrap;}}
                .done-table tr:nth-child(even) {{ background: #f8f9fa; }}
                .empty-record {{ text-align: center; color: #7f8c8d; padding: 20px; font-weight: bold; }}
            </style>
            {I18N_SCRIPT}
        </head>
        <body>
            <h2 data-i18n="unload_title">✅ 下料與完成紀錄區</h2>
            <h3 data-i18n="unload_wait">待下料區 (模擬器跑完自動傳送至此)</h3>
            <div id="unload-list"></div>
            <hr>
            <h3 data-i18n="done_list">歷史完成紀錄</h3>
            <div id="done-list" class="done-table-container"></div>

            <script>
                const socket = io();
                let sys_state_cache = {{cards:{{}}}};

                function renderDynamic() {{
                    const unloadList = document.getElementById('unload-list');
                    const doneList = document.getElementById('done-list');
                    unloadList.innerHTML = ''; 
                    
                    let tableHTML = `
                    <table class="done-table">
                        <thead>
                            <tr>
                                <th>1. 料號 (Mã LK)</th>
                                <th>2. 品名 (Tên LK)</th>
                                <th>3. 機種第幾櫃 (Model)</th>
                                <th>數量 (SL)</th>
                                <th>顏色 (Màu)</th>
                                <th>完成時間 (Thời gian)</th>
                            </tr>
                        </thead>
                        <tbody>
                    `;
                    let hasCompleted = false;

                    Object.values(sys_state_cache.cards).forEach(card => {{
                        if(card.status === 'unloading') {{
                            const div = document.createElement('div');
                            div.className = 'card';
                            div.style.borderColor = card.colorCode;
                            div.innerHTML = `
                                <div><b>${{renderField(card.part_no)}}</b> - ${{card.color}} x ${{card.qty}}</div>
                                <button class="btn-done" onclick="finishCard('${{card.id}}')">${{t('btn_done')}}</button>
                            `;
                            unloadList.appendChild(div);
                        }} else if(card.status === 'completed') {{
                            hasCompleted = true;
                            tableHTML += `
                                <tr>
                                    <td>${{renderField(card.part_no)}}</td>
                                    <td>${{renderField(card.part_name)}}</td>
                                    <td style="font-weight:bold; color:#d35400;">${{renderField(card.model_no) || '-'}}</td>
                                    <td>${{card.qty}}</td>
                                    <td>
                                        <span style="display:inline-block;width:14px;height:14px;background:${{card.colorCode}};border:1px solid #333;border-radius:3px;vertical-align:middle;margin-right:5px;"></span>
                                        ${{card.color}}
                                    </td>
                                    <td style="font-size:12px; color:#555;">${{card.finish_time}}</td>
                                </tr>
                            `;
                        }}
                    }});
                    tableHTML += `</tbody></table>`;
                    
                    if(hasCompleted) {{
                        doneList.innerHTML = tableHTML;
                    }} else {{
                        doneList.innerHTML = '<div class="empty-record">尚無完成紀錄 / Chưa có dữ liệu</div>';
                    }}
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

@app.route('/14436.png')
def serve_image():
    return send_from_directory('.', '14436.png')

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
def send_to_line(data):
    global current_active_card_template
    if isinstance(data, dict):
        card_id = data.get('id')
        hang = data.get('hang', 1)
        empty = data.get('empty', 0)
        interval = data.get('interval', 0)
        hook = data.get('hook', 0)
    else:
        card_id = str(data)
        hang, empty, interval, hook = 1, 0, 0, 0

    if card_id in sys_state['cards']:
        card = sys_state['cards'][card_id]
        card['status'] = 'on_line'
        card['line_start_time'] = int(time.time() * 1000)
        card['hang'] = hang
        card['empty'] = empty
        card['interval'] = interval
        card['hook'] = hook

        sys_state['active_card_id'] = card_id
        with active_card_lock:
            current_active_card_template = card.copy()
            
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

def continuous_line_inserter():
    global clone_counter, current_active_card_template
    while True:
        time.sleep(1)
        if current_active_card_template:
            with active_card_lock:
                card_template = current_active_card_template.copy()
            
            speed = sys_state.get('line_speed', 1100)
            speed_index = max(1.0, speed / 100.0)
            
            hang = card_template.get('hang', 1)
            empty = card_template.get('empty', 0)
            interval = card_template.get('interval', 0)
            total_hooks = max(1, hang + empty + interval)
            
            base_line_time_min = 1320.0 / speed_index
            visual_gap_sec = base_line_time_min * 60.0 * 0.012
            hook_time_sec = total_hooks * (60.0 / speed_index)
            delay_sec = max(visual_gap_sec, hook_time_sec)
            
            slept = 0.0
            target_card_id = card_template.get('id')
            while slept < delay_sec:
                time.sleep(0.5)
                slept += 0.5
                if not current_active_card_template or current_active_card_template.get('id') != target_card_id:
                    break
                    
            if current_active_card_template and current_active_card_template.get('id') == target_card_id:
                clone_counter += 1
                now_ms = int(time.time() * 1000)
                clone_id = f"{target_card_id}_clone_{clone_counter}_{now_ms}"
                
                clone_card = card_template.copy()
                clone_card['id'] = clone_id
                clone_card['status'] = 'on_line'
                clone_card['line_start_time'] = now_ms
                clone_card['is_clone'] = True
                
                sys_state['cards'][clone_id] = clone_card
                broadcast_state()

inserter_thread = threading.Thread(target=continuous_line_inserter, daemon=True)
inserter_thread.start()

if __name__ == '__main__':
    import shutil
    if os.path.exists('templates'):
        shutil.rmtree('templates')
    
    create_templates()
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
