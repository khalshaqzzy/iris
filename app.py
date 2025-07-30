from flask import Flask, request, jsonify, render_template
import datetime
import threading
import time
import requests 
import json
import sqlite3
import subprocess 
import sys 
import shutil 
import os     

app = Flask(__name__)

# --- CONFIGURATION ---
N8N_WEBHOOK_URL = "http://localhost:5678/webhook-test/974fe0a4-e3e4-408b-99a5-5e19f5893a09"
SMOKE_THRESHOLD = 400
TEMPERATURE_THRESHOLD = 35.0
MISSING_DATA_TIMEOUT_SECONDS = 15
STALE_DATA_TIMEOUT_SECONDS = 8
DATABASE_NAME = 'fire_incident.db'
DETECTOR_SCRIPT_PATH = 'detector.py' 

INCIDENT_DB_NAME = 'incident_details.db'
INCIDENT_DB_COPY_NAME = 'incident_details_llm_copy.db'

SOURCE_DB_PATH = DATABASE_NAME
DEST_DB_FOLDER = 'retell-custom-llm-python-demo'
DEST_DB_NAME = 'fire_incident_llm_copy.db'
DEST_DB_PATH = os.path.join(DEST_DB_FOLDER, DEST_DB_NAME)
COPY_INTERVAL_SECONDS = 3

SOURCE_INCIDENT_DB_PATH = INCIDENT_DB_NAME
DEST_INCIDENT_DB_PATH = os.path.join(DEST_DB_FOLDER, INCIDENT_DB_COPY_NAME)

MANUAL_ROOM_LIST = ["B001", "R101", "R103", "R202", "R203", "R207", "R301"]

# --- In-Memory Data & State Storage ---
sensor_data_storage = {}
room_statuses = {}
fire_alert_has_occurred = False
MAX_DATA_POINTS_PER_ROOM = 50
detection_process_started = False 
incident_data_logged = False
process_lock = threading.Lock()
incident_lock = threading.Lock()

# --- DATABASE & INITIALIZATION FUNCTIONS ---

def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS people_detection')
    cursor.execute('''
        CREATE TABLE people_detection (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ruangan TEXT NOT NULL UNIQUE,
            peopleCount INTEGER DEFAULT -1,
            lastDetectedTimeStamp TEXT,
            lastUpdateTimeStamp TEXT
        )
    ''')
    for room in MANUAL_ROOM_LIST:
        cursor.execute("INSERT OR IGNORE INTO people_detection (ruangan) VALUES (?)", (room,))
    conn.commit()
    conn.close()
    print(f"SERVER: Database '{DATABASE_NAME}' initialized.")

def init_incident_db():
    conn = sqlite3.connect(INCIDENT_DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS initial_incident')
    cursor.execute('''
        CREATE TABLE initial_incident (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roomId TEXT NOT NULL,
            temperature REAL,
            smokeValue INTEGER,
            alertTime TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    print(f"SERVER: Incident database '{INCIDENT_DB_NAME}' created.")

# --- BACKGROUND PROCESSES (THREADS) ---

def copy_database_periodically():
    while True:
        try:
            if not os.path.exists(DEST_DB_FOLDER): os.makedirs(DEST_DB_FOLDER)
            shutil.copy2(SOURCE_DB_PATH, DEST_DB_PATH)
        except Exception as e:
            print(f"DB COPIER ERROR: {e}", file=sys.stderr)
        time.sleep(COPY_INTERVAL_SECONDS)

def copy_incident_db_periodically():
    while True:
        time.sleep(COPY_INTERVAL_SECONDS)
        try:
            if not os.path.exists(SOURCE_INCIDENT_DB_PATH): continue
            if not os.path.exists(DEST_DB_FOLDER): os.makedirs(DEST_DB_FOLDER)
            shutil.copy2(SOURCE_INCIDENT_DB_PATH, DEST_INCIDENT_DB_PATH)
        except Exception as e:
            print(f"INCIDENT DB COPIER ERROR: {e}", file=sys.stderr)
        
def check_status_periodically():
    while True:
        time.sleep(STALE_DATA_TIMEOUT_SECONDS / 2)
        current_time = time.time()
        for room_id in list(room_statuses.keys()):
            if room_id not in room_statuses: continue
            room_info = room_statuses[room_id]
            # --- MODIFICATION: Don't check status for rooms already in fire alert ---
            if room_info.get("status") == "ALERT_FIRE":
                continue
            
            time_since_last_seen = current_time - room_info.get("last_seen_epoch", 0)
            new_status, new_details = room_info.get("status"), room_info.get("details", "")
            
            if time_since_last_seen > MISSING_DATA_TIMEOUT_SECONDS:
                if new_status != "ALERT_MISSING":
                    new_status, new_details = "ALERT_MISSING", f"Data not received for > {MISSING_DATA_TIMEOUT_SECONDS} seconds."
                    send_alert_to_n8n(room_id=room_id, alert_type="MISSING")
            elif time_since_last_seen > STALE_DATA_TIMEOUT_SECONDS:
                if new_status not in ["ALERT_MISSING", "STALE"]:
                    new_status, new_details = "STALE", f"Data not updated for > {STALE_DATA_TIMEOUT_SECONDS} sec"
            elif new_status in ["ALERT_MISSING", "STALE", "UNKNOWN"]:
                new_status, new_details = "NORMAL", f"Temperature: {room_info.get('temp_current')}°C, Smoke: {room_info.get('smoke_current')}"

            if room_statuses[room_id].get("status") != new_status:
                print(f"SERVER: Status {room_id} -> {new_status}")
                room_statuses[room_id]["status"] = new_status
                room_statuses[room_id]["details"] = new_details

# --- HELPER FUNCTIONS ---

def send_alert_to_n8n(room_id, alert_type, temperature=None, smoke_value=None, reasons=None, message_override=None):
    if not N8N_WEBHOOK_URL or "URL_WEBHOOK" in N8N_WEBHOOK_URL: return
    current_alert_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
    payload = {"roomId": room_id, "alertType": alert_type, "temperature": temperature, "smokeValue": smoke_value, "reasons": reasons if reasons is not None else [], "alertTime": current_alert_time}
    if alert_type == "FIRE": payload["message"] = message_override or f"POTENTIAL FIRE in {room_id}!"
    elif alert_type == "MISSING": payload["message"] = f"WARNING! Sensor data from {room_id} not received for > {MISSING_DATA_TIMEOUT_SECONDS} sec."
    else: return
    try: requests.post(N8N_WEBHOOK_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'}, timeout=10).raise_for_status()
    except requests.exceptions.RequestException as e: print(f"SERVER ERROR: Failed to send '{alert_type}' alert to n8n for {room_id}: {e}", file=sys.stderr)


# --- FLASK ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/sensordata', methods=['POST'])
def receive_sensor_data():
    global detection_process_started, incident_data_logged, fire_alert_has_occurred
    try:
        data = request.get_json()
        if not data or "roomId" not in data:
            return jsonify({"status": "error", "message": "Invalid data: roomId missing"}), 400
            
        room_id = data.get("roomId")
        
        current_time_epoch = time.time()
        current_time_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        temp = float(data.get("temperature")) if data.get("temperature") is not None else None
        smoke_value = int(data.get("smokeValue")) if data.get("smokeValue") is not None else None
        
        if room_id not in room_statuses:
            room_statuses[room_id] = {"status": "NORMAL", "details": "Receiving data..."}
            sensor_data_storage[room_id] = []
        
        room_statuses[room_id].update({
            "last_seen_epoch": current_time_epoch, "last_update_iso": current_time_iso,
            "temp_current": temp, "smoke_current": smoke_value
        })
        
        sensor_point = {"timestamp": current_time_iso, "temperature": temp, "smokeValue": smoke_value}
        sensor_data_storage[room_id].append(sensor_point)
        if len(sensor_data_storage[room_id]) > MAX_DATA_POINTS_PER_ROOM:
            sensor_data_storage[room_id].pop(0)

        alert_reasons_list = []
        if temp is not None and temp > TEMPERATURE_THRESHOLD: alert_reasons_list.append(f"High Temperature ({temp}°C)")
        if smoke_value is not None and smoke_value > SMOKE_THRESHOLD: alert_reasons_list.append(f"Smoke Detected")

        if alert_reasons_list:
            if not fire_alert_has_occurred:
                print("SERVER: !!! FIRST FIRE DETECTED !!! Emergency mode activated.")
                fire_alert_has_occurred = True

            current_status = "ALERT_FIRE"
            details_message = f"FIRE! {', '.join(alert_reasons_list)}"
            print(f"SERVER: ALERT! Fire detected in {room_id}. Reason: {details_message}")
            send_alert_to_n8n(room_id=room_id, alert_type="FIRE", temperature=temp, smoke_value=smoke_value, reasons=alert_reasons_list, message_override=details_message)
            
            with incident_lock:
                if not incident_data_logged:
                    try:
                        conn = sqlite3.connect(INCIDENT_DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO initial_incident (roomId, temperature, smokeValue, alertTime) VALUES (?, ?, ?, ?)", (room_id, temp, smoke_value, current_time_iso))
                        conn.commit()
                        conn.close()
                        incident_data_logged = True
                        print(f"SERVER: First incident detail for {room_id} has been logged in '{INCIDENT_DB_NAME}'.")
                    except Exception as e:
                        print(f"SERVER ERROR: Failed to log first incident data: {e}", file=sys.stderr)

            with process_lock:
                if not detection_process_started:
                    print("SERVER: Fire condition detected. Attempting to run detection script...")
                    try:
                        subprocess.Popen([sys.executable, DETECTOR_SCRIPT_PATH])
                        detection_process_started = True 
                        print(f"SERVER: Script '{DETECTOR_SCRIPT_PATH}' executed successfully.")
                    except Exception as e:
                        print(f"SERVER ERROR: Failed to execute detector.py script: {e}", file=sys.stderr)
        else:
            # If the status of this room is ALREADY fire detected, DO NOT change it back to NORMAL.
            # Let the status be locked as ALERT_FIRE.
            if room_statuses[room_id].get("status") == "ALERT_FIRE":
                current_status = "ALERT_FIRE"
                details_message = room_statuses[room_id].get("details") # Use the existing fire message detail
            else:
                # If there has never been a fire, then the status is NORMAL.
                current_status = "NORMAL"
                details_message = f"Temperature: {temp}°C, Smoke: {smoke_value}" if temp is not None and smoke_value is not None else "Incomplete sensor data"
        
        room_statuses[room_id]["status"] = current_status
        room_statuses[room_id]["details"] = details_message
        return jsonify({"status": "success", "message": "Data received"}), 200
    except Exception as e:
        print(f"SERVER ERROR: Error processing sensor data: {e}", file=sys.stderr)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/get_live_data')
def get_live_data():
    global fire_alert_has_occurred
    response_data = {}
    
    people_counts = {}
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT ruangan, peopleCount FROM people_detection")
        rows = cursor.fetchall()
        for row in rows:
            people_counts[row[0]] = row[1]
        conn.close()
    except sqlite3.Error as e:
        print(f"SERVER ERROR: Failed to read people_detection from DB: {e}", file=sys.stderr)

    for room_id, status_info in room_statuses.items():
        data_list = sensor_data_storage.get(room_id, [])
        response_data[room_id] = {
            "status": status_info.get("status", "UNKNOWN"),
            "details": status_info.get("details", ""),
            "last_update_iso": status_info.get("last_update_iso"),
            "temperature_current": status_info.get("temp_current"),
            "smoke_current": status_info.get("smoke_current"),
            "people_count": people_counts.get(room_id, -1),
            "labels": [datetime.datetime.fromisoformat(d['timestamp']).strftime('%H:%M:%S') for d in data_list],
            "temperatures": [d['temperature'] for d in data_list],
            "smokeValues": [d['smokeValue'] for d in data_list]
        }
    
    return jsonify({
        "rooms": response_data,
        "fire_alert_triggered": fire_alert_has_occurred
    })


# --- RETELL AI TOOL ENDPOINT ---
@app.route('/get_people_count', methods=['GET'])
def get_people_count():
    print("\n--- RETELL AI TOOL INVOCATION ---")
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Endpoint /get_people_count accessed.")
    room_to_query = request.args.get('ruangan')
    if room_to_query == '{{arguments.room_id}}':
        print("LOG: Placeholder '{{arguments.room_id}}' detected. Redirecting to total building request.")
        room_to_query = None
    if room_to_query:
        print(f"LOG: Received request for specific room: '{room_to_query}'")
    else:
        print("LOG: Received request for total people in the entire building.")
    try:
        conn = sqlite3.connect(DATABASE_NAME) 
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if room_to_query:
            cursor.execute("SELECT ruangan, peopleCount FROM people_detection WHERE ruangan = ?", (room_to_query,))
            data = cursor.fetchone()
            conn.close()
            if data:
                return jsonify({"status": "success", "ruangan": data["ruangan"], "jumlah_orang": data["peopleCount"] if data["peopleCount"] is not None and data["peopleCount"] >= 0 else 0}), 200
            else:
                return jsonify({"status": "error", "message": f"Room '{room_to_query}' not found."}), 404
        else:
            cursor.execute("SELECT SUM(peopleCount) as total FROM people_detection WHERE peopleCount > 0")
            total_people_data = cursor.fetchone()
            total_people = total_people_data['total'] if total_people_data and total_people_data['total'] is not None else 0
            cursor.execute("SELECT ruangan, peopleCount FROM people_detection WHERE peopleCount > 0 ORDER BY ruangan")
            details = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return jsonify({"status": "success", "total_people": total_people, "details": details}), 200
    except Exception as e:
        print(f"API TOOL ERROR: Failed to retrieve people count data: {e}", file=sys.stderr)
        return jsonify({"status": "error", "message": "An internal error occurred while accessing data."}), 500

# --- MAIN EXECUTION BLOCK ---
if __name__ == '__main__':
    init_db() 
    init_incident_db()
    
    threading.Thread(target=copy_database_periodically, daemon=True).start()
    threading.Thread(target=copy_incident_db_periodically, daemon=True).start()
    threading.Thread(target=check_status_periodically, daemon=True).start()
    print("SERVER: All background processes have been started.")
    
    print("\nSERVER: Flask application is ready to accept requests at http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False), 500

