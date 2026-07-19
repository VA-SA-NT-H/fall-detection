# Real-Time AI Fall Detection and Emergency Alert System

An AI-powered, real-time fall detection and emergency warning system designed to monitor live video streams, estimate human poses, track multiple subjects, verify potential falls to minimize false alarms, and immediately dispatch alerts (SMS/Audio) to caregivers.

---

## System Architecture

```
                   Camera / Video Source
                             │
                             ▼
                  Video Capture (OpenCV)
                             │
                             ▼
              Full Frame / Bounding Box Crop
                             │
                             ▼
             Pose Estimation (MediaPipe Pose)
                             │
                             ▼
                Feature Extraction Engine
           ├── Body Orientation Angle (tilted/lying)
           ├── Bounding Box Aspect Ratio (width/height)
           ├── Downward Velocity Tracker (drop rate)
           └── Vertical Hip Height (ground proximity)
                             │
                             ▼
              Multi-Person Centroid Tracker
                             │
                             ▼
                  Fall Detection Logic
                    (Hybrid Rules)
                             │
               ┌─────────────┴─────────────┐
               │                           │
            Normal                   Potential Fall
                                           │
                                     Timer (3 sec)
                                           │
                                  Verify No Recovery
                                           │
                                           ▼
                                    Fall Confirmed
                               ┌───────────┴───────────┐
                               │                       │
                               ▼                       ▼
                        SMS Alert Dispatch       Local Recording
                          (Twilio API)         (.mp4 Event Buffer)
```

---

## ✨ Features

* **Multi-Person Centroid Tracking**: Assigns tracking IDs and maintains separate motion/pose history per person.
* **Fall Detection Engine**: A hybrid rule-based classifier that monitors body tilt angle, bounding box aspect ratio, hip vertical velocity, and height drops.
* **Recovery Verification**: Monitors potential falls for a configurable verification window (default 3 seconds) and automatically resets if the subject stands back up.
* **Incident Recording**: Maintains a rolling frame buffer. Upon a confirmed fall, it exports a 6-second `.mp4` clip containing the pre-fall and post-fall sequence to the local directory.
* **Interactive Player Dashboard**: Built with a sleek dark glassmorphism design that features live metrics overlay, event notifications log, settings configuration, and an incident player.
* **User Authentication**: Secure JWT-based operator registration and login powered by SQLite.

---

## Technology Stack

* **AI / Vision**: Python 3.12, OpenCV, MediaPipe Pose, NumPy, SciPy
* **Backend**: FastAPI, SQLAlchemy, SQLite, PyJWT, Twilio API
* **Frontend**: React 19, Vite, Axios, Lucide React

---

## Getting Started

### Prerequisites
* Python 3.12+
* Node.js 18+

### 1. Backend Setup
1. Navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the API server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

### 2. Frontend Setup
1. Navigate to the frontend folder:
   ```bash
   cd ../frontend
   ```
2. Install package dependencies:
   ```bash
   npm install
   ```
3. Launch the development server:
   ```bash
   npm run dev
   ```
4. Open the application in your browser: [http://localhost:5173/](http://localhost:5173/)

---

## Configuration & SMS Setup
1. Open the **Settings** tab in the dashboard.
2. Adjust verification duration, velocity thresholds, and orientation angle parameters.
3. Configure the caregiver phone number and your Twilio Account SID, Auth Token, and Virtual From Number. 
* *Note: If no Twilio keys are supplied, the backend will print a mock SMS payload directly to the console for testing.*
=======
