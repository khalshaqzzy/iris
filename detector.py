# C:/Users/Khalfani Shaquille/Documents/GitHub/iris/detector.py

import sqlite3
import cv2
from ultralytics import YOLO
import datetime
import time
import sys

# --- CONFIGURATION ---
DATABASE_NAME = 'fire_incident.db'
YOLO_MODEL_PATH = 'best.pt'
HUMAN_CLASS_ID = 0 
DB_UPDATE_INTERVAL_SECONDS = 5 # Interval for database updates

def run_detection_process():
    print(f"DETECTOR: Process started. Using database '{DATABASE_NAME}' and model '{YOLO_MODEL_PATH}'.")
    
    last_db_update_time = 0 # Initialize the last database update time

    try:
        model = YOLO(YOLO_MODEL_PATH)
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            print("DETECTOR ERROR: Cannot open camera.", file=sys.stderr)
            return

        while True: 
            # 1. Capture and process frames as quickly as possible
            success, frame = cap.read()
            if not success:
                print("DETECTOR: Failed to read frame from camera. Breaking loop...", file=sys.stderr)
                break

            results = model(frame, verbose=False)
            
            # 2. Display detection results live without delay
            annotated_frame = results[0].plot()
            cv2.imshow("Human Detection (Press 'q' to exit)", annotated_frame)

            # Check for 'q' key to exit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            # 3. Update the database at the specified interval
            current_time = time.time()
            if current_time - last_db_update_time > DB_UPDATE_INTERVAL_SECONDS:
                print(f"DETECTOR: {DB_UPDATE_INTERVAL_SECONDS}s have passed. Updating database...")
                last_db_update_time = current_time # Reset the update time

                detected_classes = results[0].boxes.cls.cpu().numpy()
                human_count = int((detected_classes == HUMAN_CLASS_ID).sum())
                current_time_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
                print(f"DETECTOR: {human_count} humans detected at {current_time_iso}")

                # --- DATABASE UPDATE ---
                conn = None
                try:
                    conn = sqlite3.connect(DATABASE_NAME, timeout=10)
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE people_detection SET peopleCount = ?, lastUpdateTimeStamp = ?
                    """, (human_count, current_time_iso))
                    
                    if human_count > 0:
                        cursor.execute("""
                            UPDATE people_detection SET lastDetectedTimeStamp = ? WHERE peopleCount > 0
                        """, (current_time_iso,))
                    
                    conn.commit()
                    print("DETECTOR: Database updated successfully.")
                except sqlite3.Error as db_err:
                    print(f"DETECTOR DB ERROR: Failed to update database: {db_err}", file=sys.stderr)
                finally:
                    if conn:
                        conn.close()

    except Exception as e:
        print(f"DETECTOR CRITICAL ERROR: An exception occurred: {e}", file=sys.stderr)
    finally:
        if 'cap' in locals() and cap.isOpened():
            cap.release()
        cv2.destroyAllWindows()
        print("DETECTOR: Detection process terminated.")

if __name__ == '__main__':
    run_detection_process()