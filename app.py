import os
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

# 1. 自動建立 templates 資料夾 (若不存在)
if not os.path.exists('templates'):
    os.makedirs('templates')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
# 啟用 CORS 允許跨網域即時連線
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# 系統全域狀態暫存 (Railway 重啟會清空，但作為即時看板足夠使用)
system_state = {
    'line_speed': 1100,
    'staging_cards': [],   # 現場待料區
    'loading_cards': [],   # 待上料_阿利
    'simulator_cards': [], # 流水線
    'completed_cards': []  # 下料_完成
}

# --- 路由設定 (提供網頁) ---
@app.route('/')
@app.route('/simulator')
def simulator():
    return render_template('simulator.html')

@app.route('/staging')
def staging():
    return render_template('staging.html')

@app.route('/loading')
def loading():
    return render_template('loading.html')

@app.route('/unloading')
def unloading():
    return render_template('unloading.html')

# --- Socket.IO 即時通訊邏輯 ---
@socketio.on('connect')
def handle_connect():
    # 當有新網頁開啟，立刻同步當前系統狀態給它
    emit('sync_state', system_state)

@socketio.on('update_speed')
def handle_speed(data):
    system_state['line_speed'] = data['speed']
    socketio.emit('sync_state', system_state) # 廣播給所有人

@socketio.on('move_card')
def handle_move_card(data):
    card = data['card']
    source = data['source']
    target = data['target']
    
    # 從來源區移除
    if source in system_state:
        system_state[source] = [c for c in system_state[source] if c['id'] != card['id']]
    
    # 加入目標區
    if target in system_state:
        system_state[target].append(card)
        
    socketio.emit('sync_state', system_state)

@socketio.on('delete_card')
def handle_delete(data):
    card_id = data['id']
    for key in system_state:
        if isinstance(system_state[key], list):
            system_state[key] = [c for c in system_state[key] if c['id'] != card_id]
    socketio.emit('sync_state', system_state)

if __name__ == '__main__':
    # 注意：在 Railway 上需綁定 0.0.0.0
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
