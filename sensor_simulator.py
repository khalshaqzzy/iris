import requests
import time
import random
import json

SERVER_URL = "http://127.0.0.1:5000/sensordata"
ROOM_IDS = ["B001", "R101", "R103", "R202", "R207", "R301"]

SEND_INTERVAL = 2

def run_simulator():
    """
    Menjalankan simulator untuk mengirim data sensor dummy ke server.
    Data untuk semua ruangan dikirim dalam satu burst, lalu ada jeda.
    Setelah 20 detik, R202 akan secara konsisten mengirim temperatur tinggi.
    """
    print("-----------------------------------------")
    print("--- Sensor Simulator untuk IRIS (Mode Burst) ---")
    print(f"Target Server: {SERVER_URL}")
    print(f"Mengirim data untuk ruangan: {', '.join(ROOM_IDS)}")
    print(f"Interval Jeda: {SEND_INTERVAL} detik setelah semua data terkirim")
    print("R202 akan memicu alarm setelah 20 detik.")
    print("Tekan CTRL+C untuk menghentikan simulator.")
    print("-----------------------------------------")

    start_time = time.time()

    while True:
        try:
            print(f"\n[{time.strftime('%H:%M:%S')}] --- MENGIRIM BURST DATA UNTUK SEMUA RUANGAN ---")
            current_time = time.time()
            is_alarm_time = (current_time - start_time) > 20

            for room_id in ROOM_IDS:
                # Cek jika ini adalah R202 dan sudah waktunya alarm
                if room_id == "R202" and is_alarm_time:
                    dummy_temperature = round(random.uniform(36.0, 45.0), 2) # Temperatur pemicu alarm
                    dummy_smoke_value = random.randint(50, 150)
                    print(f"  -> !!! {room_id} Memicu ALARM Temperatur Tinggi !!!")
                else:
                    dummy_temperature = round(random.uniform(25.0, 30.0), 2) # Temperatur normal
                    dummy_smoke_value = random.randint(50, 150)

                # JSON payload
                payload = {
                    "roomId": room_id,
                    "temperature": dummy_temperature,
                    "smokeValue": dummy_smoke_value
                }

                # HTTP POST
                response = requests.post(SERVER_URL, json=payload, timeout=5)
                response.raise_for_status()

                print(f"  -> Ruangan: {room_id}, Data: {json.dumps(payload)}, Status: {response.status_code}")
                time.sleep(0.1)

            print(f"--- BURST SELESAI. Menunggu {SEND_INTERVAL} detik... ---")

        except requests.exceptions.ConnectionError:
            print(f"[{time.strftime('%H:%M:%S')}] GAGAL -> Koneksi ke server {SERVER_URL} ditolak. Pastikan server app.py sedang berjalan.")
        except requests.exceptions.RequestException as e:
            print(f"[{time.strftime('%H:%M:%S')}] GAGAL -> Terjadi error saat mengirim data: {e}")
        
        time.sleep(SEND_INTERVAL)

if __name__ == "__main__":
    run_simulator()
