# IRIS: AI-Powered Incident Response Information System

**IRIS (Incident Response Information System)** is an intelligent, integrated security system designed to monitor, detect, and automatically respond to potential fire incidents in an office environment. It addresses the critical shortcomings of conventional, isolated alarm systems by leveraging IoT, a microservices architecture, and AI to provide real-time, holistic, and actionable intelligence during an emergency.

![Screenshot of the IRIS Dashboard in normal state](https://drive.google.com/uc?export=view&id=1JAeI-cA1uulEtHD4DKOPJRWH7EsWvBvX)
*Example of the IRIS Dashboard when all systems are operating normally.*

---
## 🎯 The Problem
Conventional fire alarm systems are reactive and lack integration. When a detector is triggered, it provides a zonal alert but fails to offer a comprehensive, real-time overview of the situation. This leaves emergency reporting and evacuation guidance dependent on slow and error-prone human intervention amidst panic. Static evacuation plans on walls become quickly outdated in a dynamic fire scenario.

## ✨ The Solution: IRIS
IRIS transforms this paradigm by turning every sensor into an intelligent data source. By centralizing data and orchestrating an automated response, the system gains a complete, live picture of the building's condition. This foundation enables dynamic notifications and intelligent, automated responses—capabilities impossible for traditional architectures.

### Key Features
- **Real-time Monitoring Dashboard:** A modern web interface that displays live data from temperature and smoke sensors, complete with historical graphs and room statuses (Normal, Stale, Missing Data, or Fire).
- **Automatic Fire & Anomaly Detection:** The system proactively monitors sensor data. If temperature or smoke levels exceed safe thresholds, the system automatically triggers a fire emergency status and initiates the response workflow.
- **Occupancy-Aware Computer Vision:** When the fire alarm is active, the system automatically runs a YOLOv8 human detection module to identify and count people in the affected area. This provides crucial, real-time occupancy data for rescue teams.
- **Intelligent Emergency Reporting & Guidance AI:** Leveraging **Retell AI**, **Google Gemini**, and **n8n.io**, the system automates emergency communications.
    - **For Emergency Services:** An AI voice agent automatically calls the fire department. Using a **Retrieval-Augmented Generation (RAG)** architecture, the AI can dynamically query a database for live incident details (location, sensor readings) and real-time occupancy counts, providing the most accurate information possible.
    - **For Occupants:** The n8n workflow is extended to generate personalized, safe evacuation routes for each employee based on their location and the fire's location, delivering instructions via channels like Telegram.
- **Centralized Database Management:** All sensor data, room statuses, and incident details are logged in a SQLite database for analysis, reporting, and as a live data source for the AI.
- **Workflow Automation & Orchestration:** Uses **n8n.io** as the central orchestrator for the emergency response. When triggered by the main server, n8n manages the entire workflow, from calling the AI services to sending notifications, making the system modular and scalable.

---

## 🏗️ System Architecture
The IRIS system is designed with a **microservices architecture**, where each core function is an independent, isolated service. This enhances modularity, simplifies development, and allows for independent scaling. The architecture is organized into logical layers, ensuring a clear separation of concerns.

### Architectural Layers & Components
1.  **Physical/Device Layer:** The "eyes and ears" of the system.
    - **IoT Sensors (`sensor_simulator.py`):** ESP32-based units sending temperature and smoke data.
    - **Cameras:** Provide the video stream for the detection module.
2.  **Application/Service Layer:** The core logic and intelligence.
    - **Web Server (`app.py`):** A Flask-based service that acts as the central API gateway, processes sensor data, serves the dashboard, and triggers the n8n emergency workflow via a webhook.
    - **Human Detection Module (`detector.py`):** An independent Python script using OpenCV and a YOLOv8 model (`best.pt`) to perform real-time human detection and update the database.
    - **Workflow Orchestrator (`n8n.io`):** A low-code platform that receives the trigger from the Web Server and manages the entire emergency response sequence, including calling the AI agent.
    - **Conversational AI Backend (`retell-custom-llm-python-demo`):** A FastAPI WebSocket server that bridges Retell AI with a Google Gemini-powered agent, enabling tool use for live data retrieval during the emergency call.
3.  **Data Access & Persistence Layer:**
    - **SQLite Databases:** Two separate databases (`fire_incident.db` for occupancy data and `incident_details.db` for the initial alert) provide a simple, file-based persistence solution ideal for on-premise deployment.
4.  **Presentation Layer:**
    - **Web Dashboard (`templates/` & `static/`):** The user-facing interface for security personnel, built with HTML, CSS, and JavaScript (Chart.js).
    - **External Notifications:** Utilizes Retell AI for voice calls and can be extended via n8n for other channels like Telegram.

![Screenshot of the human detection window in action](https://drive.google.com/uc?export=view&id=1ZFlT45-Ef4LN30cGtp6ew_JcGzI-HU1z)
*Example of the human detection window, which activates during an emergency.*

![Screenshot of the n8n workflow](https://drive.google.com/uc?export=view&id=1yEZOWRybMu-J2TSiyHPgYSjIfyBCoSEv)
*The n8n workflow, which orchestrates the AI-powered emergency response.*

### Deployment Strategy: On-Premise
The system is designed for an **on-premise deployment**. The server components run on a physical machine within the building's Local Area Network (LAN). This strategy was chosen for:
- **Reliability & Low Latency:** Communication between sensors and the server is extremely fast and does not depend on internet connectivity, ensuring the core detection loop is always operational.
- **Cost-Effectiveness:** Avoids recurring cloud service fees for data ingress and processing, making it more economical over the long term.
- **Data Security:** All sensitive sensor data remains within the building's private network, enhancing security.

---

## 🛠️ Technology Stack
- **Backend:** Python, Flask, FastAPI, Uvicorn, Gunicorn
- **Frontend:** HTML, CSS, JavaScript
- **Data Visualization:** Chart.js, Luxon.js
- **AI & Machine Learning:** Google Gemini, OpenCV, Ultralytics YOLOv8
- **AI Voice Platform:** Retell AI
- **Automation & Orchestration:** n8n.io
- **Database:** SQLite
- **Containerization:** Docker (recommended for production)

---

## 🚀 Setup and Installation
To run this project, you need to run two main servers simultaneously: the Flask server for the core application and the Uvicorn server for the LLM backend.

### Prerequisites
- Python 3.9+
- `pip` package manager
- A camera (webcam) connected to the computer
- [Retell AI](https://retellai.com/) and [Google AI Studio](https://aistudio.google.com/) accounts to obtain API keys.
- [n8n.io](https://n8n.io/) instance (local or cloud) with a configured webhook trigger.
- [ngrok](https://ngrok.com/) to expose local servers to the internet.

### Installation Steps

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/your-username/iris.git
    cd iris
    ```

2.  **Install Main Server Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Install LLM Backend Dependencies:**
    ```bash
    cd retell-custom-llm-python-demo
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    - Create a `.env` file inside the `retell-custom-llm-python-demo/` directory.
    - Fill the file with your API keys:
      ```
      RETELL_API_KEY="YOUR_RETELL_API_KEY"
      GOOGLE_API_KEY="YOUR_GEMINI_API_KEY"
      ```

5.  **Return to the Main Directory:**
    ```bash
    cd ..
    ```

### Running the Application

1.  **Run the Main Server (Flask):**
    Open a terminal and run:
    ```bash
    python app.py
    ```
    This server will run at `http://localhost:5000`.

2.  **Run the LLM Backend Server (Uvicorn):**
    Open a second terminal, navigate to the `retell-custom-llm-python-demo` directory, and run:
    ```bash
    cd retell-custom-llm-python-demo
    uvicorn app.server:app --reload --port=8080
    ```
    This server will run at `http://localhost:8080`.

3.  **Expose Servers to the Internet with Ngrok:**
    - **For the LLM Backend:** Open a third terminal and run:
      ```bash
      ngrok http 8080
      ```
      You will get a public URL like `https://<unique-id>.ngrok-free.app`. Copy this URL.
    - **Configure in Retell AI:** Create a new agent in the Retell AI dashboard and use the WebSocket URL from ngrok with the format `wss://<unique-id>.ngrok-free.app/llm-websocket/{call_id}`.

4.  **Run the Sensor Simulator (Optional):**
    To send mock sensor data to the system, open a fourth terminal and run:
    ```bash
    python sensor_simulator.py
    ```

---

## ⚙️ System Workflow

1.  **Access the Dashboard:** Open a browser and navigate to `http://localhost:5000` to see the monitoring dashboard.
2.  **Normal Conditions:** The dashboard will show an "All Systems Normal" status and incoming sensor data from `sensor_simulator.py`.
3.  **Fire Incident:** When the simulator sends data that exceeds the thresholds (e.g., temperature > 35°C or smoke > 400), the `app.py` server detects the anomaly.
4.  **Parallel Process Activation:**
    - The server immediately starts the `detector.py` script to begin real-time human detection.
    - Simultaneously, it sends a webhook to **n8n.io** to trigger the emergency workflow.
5.  **n8n Workflow Execution:**
    - n8n receives the webhook with incident data.
    - It initiates the automated voice call to emergency services via the Retell AI agent.
6.  **AI Emergency Call:** The Retell agent (powered by the custom Gemini LLM backend) handles the call, using its tools to fetch live data from the database to answer questions accurately.

---

## 📄 License

This project is licensed under the **MIT License**. See the `LICENSE` file for more details.
