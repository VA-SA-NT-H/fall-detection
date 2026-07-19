import cv2
import time
import asyncio
import os
from fastapi import FastAPI, Response, Query, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Database and Auth Imports
from app.core.database import Base, engine, get_db, SessionLocal
from app.models.models import User
from app.core.auth import get_password_hash, verify_password, create_access_token, get_current_user
from app.detection import FallDetector
from app.services.event_recorder import EventRecorder
from app.alerts.sms_service import send_fall_sms_alert

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Fall Detection System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
detector = FallDetector()
recorder = EventRecorder()
camera_running = False
sms_alert_cooldown = {}  # Per person cooldown: {person_id: last_alert_time}

# Schema definitions
class UserAuth(BaseModel):
    username: str
    password: str

class UserSettings(BaseModel):
    phone_number: str
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_phone: str = ""

def gen_frames(source):
    global camera_running
    camera_running = True
    
    if source.isdigit():
        cap = cv2.VideoCapture(int(source))
    else:
        cap = cv2.VideoCapture(source)
        
    fps_limit = 30.0
    if not source.isdigit():
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        if video_fps > 0:
            fps_limit = video_fps
            
    frame_delay = 1.0 / fps_limit
    prev_time = time.time()
    
    db = SessionLocal()
    
    while camera_running and cap.isOpened():
        start_loop = time.time()
        success, frame = cap.read()
        if not success:
            if not source.isdigit():
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            else:
                break
                
        # Run fall detection pipeline
        processed_frame, features = detector.process_frame(frame)
        
        # Add frame to rolling buffer and trigger on fall
        recorder.add_frame(processed_frame)
        if detector.state == "Fall Detected":
            recorder.trigger_recording()
            
            # Send SMS Alert with cooldown (60 seconds)
            person_id = features.get("person_id", 1)
            now = time.time()
            if now - sms_alert_cooldown.get(person_id, 0) > 60:
                sms_alert_cooldown[person_id] = now
                
                # Fetch caregiver phone config from DB
                user = db.query(User).first()
                user_config = {}
                if user:
                    user_config = {
                        "phone_number": user.phone_number,
                        "twilio_sid": user.twilio_sid,
                        "twilio_token": user.twilio_token,
                        "twilio_phone": user.twilio_phone
                    }
                
                # Trigger SMS Alert
                msg = f"⚠️ AegisFall ALERT: A fall has been detected for Person ID {person_id}."
                send_fall_sms_alert(user_config.get("phone_number"), msg, user_config)
        
        # Calculate Live FPS
        current_time = time.time()
        fps = 1.0 / (current_time - prev_time)
        prev_time = current_time
        
        # Draw Live FPS on frame
        cv2.putText(processed_frame, f"FPS: {fps:.1f}", (20, 215), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Encode to jpeg
        ret, buffer = cv2.imencode('.jpg', processed_frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
               
        # Throttle processing to match video file FPS
        if not source.isdigit():
            elapsed = time.time() - start_loop
            sleep_time = frame_delay - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
               
    cap.release()
    db.close()
    camera_running = False

# --- AUTH ENDPOINTS ---

@app.post("/api/auth/register")
def register(user_data: UserAuth, db: Session = Depends(get_db)):
    """Registers a new caregiver user account."""
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
        
    hashed = get_password_hash(user_data.password)
    new_user = User(username=user_data.username, hashed_password=hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"status": "success", "message": "User registered successfully"}

@app.post("/api/auth/login")
def login(user_data: UserAuth, db: Session = Depends(get_db)):
    """Authenticates caregiver and issues JWT token."""
    user = db.query(User).filter(User.username == user_data.username).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Returns profile of logged-in user."""
    return {
        "username": current_user.username,
        "phone_number": current_user.phone_number,
        "twilio_sid": current_user.twilio_sid,
        "twilio_token": current_user.twilio_token,
        "twilio_phone": current_user.twilio_phone
    }

@app.post("/api/auth/settings")
def update_settings(settings: UserSettings, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Updates the Twilio SMS alerting configurations."""
    current_user.phone_number = settings.phone_number
    current_user.twilio_sid = settings.twilio_sid
    current_user.twilio_token = settings.twilio_token
    current_user.twilio_phone = settings.twilio_phone
    db.commit()
    return {"status": "success", "message": "Notification configurations updated successfully"}

# --- SYSTEM MONITORING ENDPOINTS ---

@app.get("/api/stream")
def video_stream(source: str = Query("0", description="Camera index (e.g. 0) or path to a test video file")):
    """Exposes a live MJPEG stream with fall detection overlays."""
    return StreamingResponse(gen_frames(source), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/status")
def get_status():
    """Returns the current state and latest features calculated by the detector."""
    return {
        "state": detector.state,
        "potential_fall_start": detector.potential_fall_start_time,
        "verification_duration": detector.verification_duration,
        "last_features": getattr(detector, "last_fall_features", {})
    }

@app.post("/api/reset")
def reset_detector():
    """Resets the fall detector state back to normal."""
    detector.state = "Normal"
    detector.potential_fall_start_time = None
    detector.landmark_history.clear()
    return {"status": "success", "message": "Detector state reset to Normal"}

@app.post("/api/stop")
def stop_stream():
    """Stops the active video capture."""
    global camera_running
    camera_running = False
    return {"status": "success", "message": "Stream stopped"}

@app.get("/api/events")
def list_events():
    """Lists all recorded fall event videos."""
    dir_path = recorder.output_dir
    if not os.path.exists(dir_path):
        return []
    
    files = sorted([f for f in os.listdir(dir_path) if f.endswith(".mp4")], reverse=True)
    events = []
    for f in files:
        filepath = os.path.join(dir_path, f)
        stat = os.stat(filepath)
        events.append({
            "filename": f,
            "size": stat.st_size,
            "created_at": time.ctime(stat.st_mtime)
        })
    return events

@app.get("/api/events/{filename}")
def get_event_file(filename: str):
    """Serves the specified fall event video file."""
    filepath = os.path.join(recorder.output_dir, filename)
    if not os.path.exists(filepath):
        return Response(status_code=404, content="Event video not found")
    return FileResponse(filepath, media_type="video/mp4")
