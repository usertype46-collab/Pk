import threading
import os

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
    'track_path': '',
    'track_start': 0.0,       # 設置起點 (百分比或長度比例 0.0 ~ 1.0)
    'track_end': 1.0,         # 設置終點 (百分比或長度比例 0.0 ~ 1.0)
    'track_direction': '1'    # 輸送方向: '1' 為順向, '-1' 為逆向
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
                'finish_time': row['finish_time'],
                'inserted_qty': 0, # 初始化上線數量
                'unloaded_qty': 0  # 初始化下料數量
            }
        sys_state['cards'] = cards
        
        path_res = supabase.table('powder_settings').select('key, value').execute()
        for row in path_res.data:
            if row['key'] == 'track_path_d':
                sys_state['track_path'] = row['value']
            elif row['key'] == 'track_start':
                sys_state['track_start'] = float(row['value'])
            elif row['key'] == 'track_end':
                sys_state['track_end'] = float(row['value'])
            elif row['key'] == 'track_direction':
                sys_state['track_direction'] = row['value']
                
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
def handle_update_track(data):
    if isinstance(data, dict):
        if 'path_d' in data:
            sys_state['track_path'] = data['path_d']
        if 'track_start' in data:
            sys_state['track_start'] = float(data['track_start'])
        if 'track_end' in data:
            sys_state['track_end'] = float(data['track_end'])
        if 'track_direction' in data:
            sys_state['track_direction'] = str(data['track_direction'])
    else:
        sys_state['track_path'] = str(data)

    try:
        if supabase: 
            supabase.table('powder_settings').upsert({'key': 'track_path_d', 'value': sys_state['track_path']}).execute()
            supabase.table('powder_settings').upsert({'key': 'track_start', 'value': str(sys_state['track_start'])}).execute()
            supabase.table('powder_settings').upsert({'key': 'track_end', 'value': str(sys_state['track_end'])}).execute()
            supabase.table('powder_settings').upsert({'key': 'track_direction', 'value': str(sys_state['track_direction'])}).execute()
    except Exception as e:
        print("同步軌道設定至 Supabase 失敗:", e)
    broadcast_state()

@socketio.on('add_card')
def add_card(data):
    sys_state['cards'][data['id']] = data
    sys_state['cards'][data['id']]['inserted_qty'] = 0
    sys_state['cards'][data['id']]['unloaded_qty'] = 0
    try:
        if supabase:
            supabase.table('powder_cards').upsert({
                'id': data['id'],
                'color': data['color'],
                'color_code': data['colorCode'],
                'part_no': data['part_no'],
                'part_name': data['part_name'],
                'model_no': data['model_no'],
                'qty': int(data['qty'] or 1), # 確保防呆至少為 1
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
        card['inserted_qty'] = 0 # 重置
        card['unloaded_qty'] = 0 # 重置

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

# --- 背景持續上線執行緒 (加入數量滿載自動停止判斷) ---
def continuous_line_inserter():
    global clone_counter, current_active_card_template
    while True:
        time.sleep(1)
        if current_active_card_template:
            with active_card_lock:
                card_template = current_active_card_template.copy()
            
            target_card_id = card_template.get('id')
            
            # 檢查數量是否已經滿載，排滿自動停止插入
            parent_card = sys_state['cards'].get(target_card_id)
            if not parent_card or parent_card.get('inserted_qty', 0) >= int(parent_card.get('qty', 1)):
                with active_card_lock:
                    current_active_card_template = None
                continue

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
            while slept < delay_sec:
                time.sleep(0.5)
                slept += 0.5
                if not current_active_card_template or current_active_card_template.get('id') != target_card_id:
                    break
                    
            if current_active_card_template and current_active_card_template.get('id') == target_card_id:
                # 再次確認數量防呆
                parent_card = sys_state['cards'].get(target_card_id)
                if not parent_card or parent_card.get('inserted_qty', 0) >= int(parent_card.get('qty', 1)):
                    with active_card_lock:
                        current_active_card_template = None
                    continue

                clone_counter += 1
                now_ms = int(time.time() * 1000)
                clone_id = f"{target_card_id}_clone_{clone_counter}_{now_ms}"
                
                clone_card = card_template.copy()
                clone_card['id'] = clone_id
                clone_card['status'] = 'on_line'
                clone_card['line_start_time'] = now_ms
                clone_card['is_clone'] = True
                clone_card['parent_id'] = target_card_id
                
                # 增加上線進度計數
                sys_state['cards'][target_card_id]['inserted_qty'] = sys_state['cards'][target_card_id].get('inserted_qty', 0) + 1
                
                sys_state['cards'][clone_id] = clone_card
                broadcast_state()

inserter_thread = threading.Thread(target=continuous_line_inserter, daemon=True)
inserter_thread.start()

# --- 背景持續檢查抵達終點並推進下料區的執行緒 ---
def continuous_line_checker():
    while True:
        time.sleep(1)
        now_ms = int(time.time() * 1000)
        
        speed = sys_state.get('line_speed', 1100)
        speed_index = max(1.0, speed / 100.0)
        
        t_start = sys_state.get('track_start', 0.0)
        t_end = sys_state.get('track_end', 1.0)
        t_dir = str(sys_state.get('track_direction', '1'))
        
        if t_dir == '1':
            span = (t_end - t_start) if t_end >= t_start else (1.0 - t_start + t_end)
        else:
            span = (t_start - t_end) if t_start >= t_end else (t_start + 1.0 - t_end)
        if span == 0: span = 1.0
        
        total_time_ms = round(1320.0 / speed_index) * 60 * 1000 * span
        
        clones_to_remove = []
        with active_card_lock:
            for cid, card in list(sys_state['cards'].items()):
                if card.get('is_clone') and card.get('status') == 'on_line':
                    elapsed = now_ms - card.get('line_start_time', now_ms)
                    if elapsed >= total_time_ms:
                        clones_to_remove.append(cid)
        
        if clones_to_remove:
            state_changed = False
            for cid in clones_to_remove:
                clone = sys_state['cards'].pop(cid, None)
                if clone:
                    state_changed = True
                    parent_id = clone.get('parent_id')
                    if parent_id and parent_id in sys_state['cards']:
                        parent = sys_state['cards'][parent_id]
                        parent['unloaded_qty'] = parent.get('unloaded_qty', 0) + 1
                        
                        # 第一片到達時，將母卡推入下料區顯示
                        if parent['status'] == 'on_line':
                            parent['status'] = 'unloading'
                            try:
                                if supabase: supabase.table('powder_cards').update({'status': 'unloading'}).eq('id', parent_id).execute()
                            except Exception: pass
                        
                        # 當下料數量達到應有數量時，自動完成歸檔
                        if parent['unloaded_qty'] >= int(parent.get('qty', 1)):
                            parent['status'] = 'completed'
                            tw_time = time.gmtime(time.time() + 8 * 3600)
                            ftime = time.strftime("%Y-%m-%d %H:%M:%S", tw_time)
                            parent['finish_time'] = ftime
                            try:
                                if supabase: 
                                    supabase.table('powder_cards').update({'status': 'completed', 'finish_time': ftime}).eq('id', parent_id).execute()
                            except Exception: pass
            
            if state_changed:
                broadcast_state()

checker_thread = threading.Thread(target=continuous_line_checker, daemon=True)
checker_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
