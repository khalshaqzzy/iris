import sqlite3
import cv2
from ultralytics import YOLO
import datetime
import os
import random
import sys

# --- CONFIGURATION ---
DATABASE_NAME = 'fire_incident.db'
YOLO_MODEL_PATH = 'best.pt'
HUMAN_CLASS_ID = 0
SIMULATION_IMAGE_DIR = 'simulation/images'
OUTPUT_IMAGE_DIR = os.path.join('static', 'detected_images')

def run_detection_process():
    """
    Skrip ini berjalan satu kali saat dipicu.
    1. Membersihkan gambar deteksi lama.
    2. Mengambil semua ID ruangan dari database.
    3. Memilih gambar acak unik untuk setiap ruangan.
    4. Melakukan deteksi pada setiap gambar.
    5. Memperbarui database dengan jumlah orang yang terdeteksi.
    6. Menyimpan gambar hasil anotasi ke direktori statis.
    """
    print(f"DETECTOR: Proses deteksi simulasi dimulai.")

    # 1. Buat dan bersihkan direktori output
    if not os.path.exists(OUTPUT_IMAGE_DIR):
        os.makedirs(OUTPUT_IMAGE_DIR)
        print(f"DETECTOR: Membuat direktori output: {OUTPUT_IMAGE_DIR}")
    else:
        print(f"DETECTOR: Membersihkan direktori output lama...")
        for f in os.listdir(OUTPUT_IMAGE_DIR):
            os.remove(os.path.join(OUTPUT_IMAGE_DIR, f))

    conn = None
    try:
        # 2. Hubungkan ke DB dan ambil semua ruangan
        conn = sqlite3.connect(DATABASE_NAME, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT ruangan FROM people_detection")
        room_ids = [row[0] for row in cursor.fetchall()]
        print(f"DETECTOR: Menjalankan deteksi untuk ruangan: {room_ids}")

        # 3. Dapatkan daftar gambar simulasi
        available_images = [img for img in os.listdir(SIMULATION_IMAGE_DIR) if img.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if len(available_images) < len(room_ids):
            print(f"DETECTOR ERROR: Tidak cukup gambar ({len(available_images)}) di '{SIMULATION_IMAGE_DIR}' untuk semua ruangan ({len(room_ids)}).", file=sys.stderr)
            return

        random.shuffle(available_images)
        image_mapping = {room_id: available_images[i] for i, room_id in enumerate(room_ids)}

        # 4. Muat model YOLO
        model = YOLO(YOLO_MODEL_PATH)

        # 5. Proses setiap ruangan
        for room_id, image_name in image_mapping.items():
            image_path = os.path.join(SIMULATION_IMAGE_DIR, image_name)
            print(f"DETECTOR: Memproses {room_id} -> {image_path}")

            if not os.path.exists(image_path):
                print(f"DETECTOR WARNING: Gambar tidak ditemukan: {image_path}", file=sys.stderr)
                continue

            # Lakukan deteksi
            results = model(image_path, verbose=False)
            frame = cv2.imread(image_path)

            # Hitung jumlah manusia
            detected_classes = results[0].boxes.cls.cpu().numpy()
            human_count = int((detected_classes == HUMAN_CLASS_ID).sum())
            current_time_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

            print(f"DETECTOR: {human_count} manusia terdeteksi di {room_id}.")

            # 6. Simpan gambar hasil anotasi
            annotated_frame = results[0].plot()
            output_filename = f"{room_id}.jpg"
            output_path = os.path.join(OUTPUT_IMAGE_DIR, output_filename)
            cv2.imwrite(output_path, annotated_frame)
            print(f"DETECTOR: Gambar hasil deteksi disimpan ke {output_path}")

            # 7. Perbarui database
            cursor.execute("""
                UPDATE people_detection 
                SET peopleCount = ?, lastUpdateTimeStamp = ?, lastDetectedTimeStamp = ?
                WHERE ruangan = ?
            """, (human_count, current_time_iso, current_time_iso, room_id))

        conn.commit()
        print("DETECTOR: Database berhasil diperbarui untuk semua ruangan.")

    except sqlite3.Error as db_err:
        print(f"DETECTOR DB ERROR: Gagal memperbarui database: {db_err}", file=sys.stderr)
    except Exception as e:
        print(f"DETECTOR CRITICAL ERROR: Terjadi pengecualian: {e}", file=sys.stderr)
    finally:
        if conn:
            conn.close()
        print("DETECTOR: Proses deteksi simulasi selesai.")

if __name__ == '__main__':
    run_detection_process()
