"""
🏭 粉體塗裝流水線模擬器 - 核心伺服器
包含 SocketIO 即時通訊與靜態檔案路由
"""

import os
import time
import threading
from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit

app = Flask(__name__, static_folder='.', template_folder='.')
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

sys_state = {
    'line_speed': 1100,
    'cards': {},
}

# 提供 HTML 頁面路由
@app.route('/')
def index():
    return send_from_directory('.', 'simulator.html')

@app.route('/<filename>.html')
def serve_html(filename):
    return send_from_directory('.', f'{filename}.html')

@app.route('/worker.js')
def serve_worker():
    return send_from_directory('.', 'worker.js')

# SocketIO 事件處理
@socketio.on('connect')
def handle_connect():
    emit('state_update', sys_state)

@socketio.on('update_settings')
def handle_settings(data):
    sys_state['line_speed'] = data.get('speed', sys_state['line_speed'])
    emit('state_update', sys_state, broadcast=True)

@socketio.on('add_material')
def handle_add_material(data):
    now_ms = int(time.time() * 1000)
    card_id = f"card_{now_ms}"
    sys_state['cards'][card_id] = {
        'id': card_id,
        'station': data.get('station'),
        'start_time': now_ms,
        'progress': 0
    }
    emit('state_update', sys_state, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
