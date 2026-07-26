import os
import time
import threading

# 自動判斷環境：如果已安裝 eventlet 則優先採用，否則退回 threading
try:
    import eventlet
    eventlet.monkey_patch()
    ASYNC_MODE = 'eventlet'
except ImportError:
    ASYNC_MODE = 'threading'

from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit
from supabase import create_client, Client

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

# 採用動態取得的 async_mode，兼顧開發與雲端部署
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=ASYNC_MODE)

# --- Supabase 初始化 ---
SUPABASE_URL = "https://cnkxsxhgdtuxknrzufhv.supabase.co"
SUPABASE_KEY = "sb_publishable_QEoX_f9G_Gf9kaaDZpaH-g_ageY5WFK"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Supabase 初始化失敗: {e}")
    supabase = None

sys_state = {
    'line_speed': 1100,
    'cards': {},
    'active_card_id': None,
    'track_path': ''
}

active_card_lock = threading.Lock()
current_active_card_template = None
clone_counter = 0

def load_state_from_supabase():
    global sys_state
    if not supabase:
        print("Supabase 未初始化，略過載入狀態")
        return
        
    try:
        res = supabase.table('powder_cards').select('*').execute()
        cards = {}
        for row in res.data:
            cards[row['id']] = {
                'id': row['id'],
                'color': row['color'],
                'colorCode': row['color_code'],
                'part_no': row['part_no'],
                'part_name': row['part_name'],
                'model_no': row['model_no'],
                'qty': row['qty'],
                'status': row['status'],
                'hang': row['hang'],
                'empty': row['empty'],
                'interval': row['interval'],
                'hook': row['hook'],
                'line_start_time': row['line_start_time'],
                'finish_time': row['finish_time']
            }
        sys_state['cards'] = cards
        
        path_res = supabase.table('powder_settings').select('value').eq('key', 'track_path_d').execute()
        if path_res.data:
            sys_state['track_path'] = path_res.data[0]['value']
        print("✅ 成功從 Supabase 載入初始狀態")
    except Exception as e:
        print(f"⚠️ 載入 Supabase 資料失敗 (網路異常或權限問題): {e}")

# 背景加載資料，避免阻擋伺服器啟動
threading.Thread(target=load_state_from_supabase, daemon=True).start()

# --- 路由設定 ---
@app.route('/')
def index(): 
    return render_template('simulator.html')

@app.route('/wait')
def wait(): 
    return render_template('waiting.html')

@app.route('/load')
def load(): 
    return render_template('loading.html')

@app.route('/unload')
def unload(): 
    return render_template('unloading.html')

@app.route('/14436.png')
def serve_image():
    return send_from_directory('.', '14436.png')

def broadcast_state():
    socketio.emit('update_state', sys_state)

# --- SocketIO 事件處理 ---
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

@socketio.on('update_track_path')
def handle_update_track(path_d):
    sys_state['track_path'] = path_d
    try:
        if supabase: 
            supabase.table('powder_settings').upsert({'key': 'track_path_d', 'value': path_d}).execute()
    except Exception as e:
        print("同步軌道至 Supabase 失敗:", e)
    broadcast_state()

@socketio.on('add_card')
def add_card(data):
    sys_state['cards'][data['id']] = data
    try:
        if supabase:
            supabase.table('powder_cards').upsert({
                'id': data['id'],
                'color': data['color'],
                'color_code': data['colorCode'],
                'part_no': data['part_no'],
                'part_name': data['part_name'],
                'model_no': data['model_no'],
                'qty': int(data['qty'] or 0),
                'status': data['status'],
                'hang': 1, 'empty': 0, 'interval': 0, 'hook': 0
            }).execute()
    except Exception as e:
        print("新增卡片至 Supabase 失敗:", e)
    broadcast_state()

@socketio.on('delete_card')
def delete_card(card_id):
    if card_id in sys_state['cards']:
        del sys_state['cards'][card_id]
        try:
            if supabase: 
                supabase.table('powder_cards').delete().eq('id', card_id).execute()
        except Exception as e:
            print("刪除 Supabase 資料失敗:", e)
        broadcast_state()

@socketio.on('change_status')
def change_status(data):
    card_id = data['id']
    if card_id in sys_state['cards']:
        sys_state['cards'][card_id]['status'] = data['status']
        try:
            if supabase: 
                supabase.table('powder_cards').update({'status': data['status']}).eq('id', card_id).execute()
        except Exception as e:
            print("更新狀態至 Supabase 失敗:", e)
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
            
        try:
            if supabase:
                supabase.table('powder_cards').update({
                    'status': 'on_line',
                    'hang': hang, 'empty': empty, 'interval': interval, 'hook': hook,
                    'line_start_time': card['line_start_time']
                }).eq('id', card_id).execute()
        except Exception as e:
            print("上線資料同步 Supabase 失敗:", e)

        broadcast_state()

@socketio.on('auto_move_to_unload')
def auto_unload(card_id):
    if card_id in sys_state['cards'] and sys_state['cards'][card_id]['status'] == 'on_line':
        sys_state['cards'][card_id]['status'] = 'unloading'
        try:
            if supabase: 
                supabase.table('powder_cards').update({'status': 'unloading'}).eq('id', card_id).execute()
        except Exception:
            pass
        broadcast_state()

@socketio.on('finish_card')
def finish_card(card_id):
    if card_id in sys_state['cards']:
        sys_state['cards'][card_id]['status'] = 'completed'
        tw_time = time.gmtime(time.time() + 8 * 3600)
        ftime = time.strftime("%Y-%m-%d %H:%M:%S", tw_time)
        sys_state['cards'][card_id]['finish_time'] = ftime
        try:
            if supabase: 
                supabase.table('powder_cards').update({
                    'status': 'completed',
                    'finish_time': ftime
                }).eq('id', card_id).execute()
        except Exception:
            pass
        broadcast_state()

# --- 背景持續上線執行緒 ---
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
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
