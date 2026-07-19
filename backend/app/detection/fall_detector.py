import time
import math
import numpy as np
import cv2
import mediapipe as mp
from typing import Dict, List, Tuple, Optional

class TrackedPerson:
    def __init__(self, person_id: int, fps: float = 30.0):
        self.person_id = person_id
        self.state = "Normal"
        self.potential_fall_start_time: Optional[float] = None
        self.verification_duration = 3.0
        self.landmark_history: List[Dict] = []
        self.history_limit = 90
        self.last_features: Dict = {}
        self.fps = fps
        self.centroid: Tuple[float, float] = (0.0, 0.0)
        self.last_seen = time.time()
        
        # Thresholds - fine-tuned for video streams
        self.VELOCITY_THRESHOLD = -0.35  # slightly more sensitive
        self.ANGLE_THRESHOLD = 50.0      # lower threshold to catch tilts earlier
        self.ASPECT_RATIO_THRESHOLD = 1.0

    def update_features(self, features: Dict, current_time: float):
        self.last_seen = current_time
        self.centroid = features["centroid"]
        
        # Add to history
        self.landmark_history.append({
            "timestamp": current_time,
            "mid_hip": features["mid_hip"],
            "hip_height": features["hip_height"]
        })
        if len(self.landmark_history) > self.history_limit:
            self.landmark_history.pop(0)
            
        # Velocity Calculation
        velocity = 0.0
        if len(self.landmark_history) >= 3:
            prev = self.landmark_history[-3]
            dt = current_time - prev["timestamp"]
            if dt > 0:
                velocity = (features["hip_height"] - prev["hip_height"]) / dt
        features["velocity"] = float(velocity)
        
        # Run state machine
        self._update_state_machine(features, current_time)
        self.last_features = features.copy()

    def _update_state_machine(self, features: Dict, current_time: float):
        angle = features["body_angle"]
        aspect_ratio = features["aspect_ratio"]
        velocity = features["velocity"]
        hip_height = features["hip_height"]
        
        is_sudden_drop = (velocity < self.VELOCITY_THRESHOLD)
        is_horizontal = (angle > self.ANGLE_THRESHOLD or aspect_ratio > self.ASPECT_RATIO_THRESHOLD)
        
        if self.state == "Normal":
            if is_sudden_drop and is_horizontal:
                self.state = "Potential Fall"
                self.potential_fall_start_time = current_time
            elif is_horizontal and hip_height < 0.35:
                self.state = "Potential Fall"
                self.potential_fall_start_time = current_time
                
        elif self.state == "Potential Fall":
            # Standing up definition
            is_recovered = (angle < 35.0 and hip_height > 0.45)
            if is_recovered:
                self.state = "Normal"
                self.potential_fall_start_time = None
            else:
                elapsed = current_time - self.potential_fall_start_time
                features["time_to_alert"] = float(max(0.0, self.verification_duration - elapsed))
                if elapsed >= self.verification_duration:
                    self.state = "Fall Detected"
                    
        elif self.state == "Fall Detected":
            is_recovered = (angle < 35.0 and hip_height > 0.45)
            if is_recovered:
                self.state = "Normal"
                self.potential_fall_start_time = None
                
        features["state"] = self.state
        features["alert_triggered"] = (self.state == "Fall Detected")


class FallDetector:
    def __init__(self, fps_estimate: float = 30.0):
        # MediaPipe Pose Initialization
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_draw = self.mp_pose.drawing_utils if hasattr(self.mp_pose, 'drawing_utils') else mp.solutions.drawing_utils
        
        # HOG descriptor for multi-person detection bounding boxes
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        
        # Tracking states
        self.tracked_people: Dict[int, TrackedPerson] = {}
        self.next_person_id = 1
        self.fps = fps_estimate
        
        # Fall state helper for backward compatibility / global status
        self.state = "Normal"
        self.potential_fall_start_time = None
        self.verification_duration = 3.0
        self.last_fall_features: Dict = {}

    def _calculate_angle(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        angle_rad = math.atan2(abs(dx), abs(dy))
        return math.degrees(angle_rad)

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict]:
        h, w, _ = frame.shape
        timestamp = time.time()
        
        # Try full frame first for maximum landmark reliability (prevents crop jumps)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_frame)
        
        current_frame_features = []
        
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            try:
                l_sh = landmarks[11]
                r_sh = landmarks[12]
                l_hip = landmarks[23]
                r_hip = landmarks[24]
                
                confidence = np.mean([l_sh.visibility, r_sh.visibility, l_hip.visibility, r_hip.visibility])
                
                if confidence > 0.4:
                    mid_shoulder = ((l_sh.x + r_sh.x) / 2.0, (l_sh.y + r_sh.y) / 2.0)
                    mid_hip = ((l_hip.x + r_hip.x) / 2.0, (l_hip.y + r_hip.y) / 2.0)
                    
                    xs = [lm.x for lm in landmarks if lm.visibility > 0.5]
                    ys = [lm.y for lm in landmarks if lm.visibility > 0.5]
                    aspect_ratio = (max(xs) - min(xs)) / (max(ys) - min(ys) + 1e-6) if xs and ys else 0.0
                    
                    bx = int(min(xs) * w) if xs else 0
                    by = int(min(ys) * h) if ys else 0
                    bw = int((max(xs) - min(xs)) * w) if xs else w
                    bh = int((max(ys) - min(ys)) * h) if ys else h
                    
                    feat = {
                        "confidence": float(confidence),
                        "body_angle": float(self._calculate_angle(mid_hip, mid_shoulder)),
                        "aspect_ratio": float(aspect_ratio),
                        "hip_height": float(1.0 - mid_hip[1]),
                        "centroid": (float(mid_hip[0]), float(mid_hip[1])),
                        "mid_hip": (float(mid_hip[0]), float(mid_hip[1])),
                        "state": "Normal",
                        "velocity": 0.0,
                        "time_to_alert": 0.0,
                        "alert_triggered": False,
                        "bbox": (int(bx), int(by), int(bw), int(bh))
                    }
                    
                    self.mp_draw.draw_landmarks(frame, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)
                    current_frame_features.append(feat)
            except Exception:
                pass
                
        # If full-frame landmarking didn't find anyone, try HOG as fallback
        if not current_frame_features:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            boxes, _ = self.hog.detectMultiScale(gray, winStride=(8,8), padding=(16,16), scale=1.05)
            
            for (bx, by, bw, bh) in boxes:
                crop = frame[by:by+bh, bx:bx+bw]
                if crop.size == 0:
                    continue
                rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                crop_results = self.pose.process(rgb_crop)
                
                if crop_results.pose_landmarks:
                    landmarks = crop_results.pose_landmarks.landmark
                    try:
                        l_sh = landmarks[11]
                        r_sh = landmarks[12]
                        l_hip = landmarks[23]
                        r_hip = landmarks[24]
                        
                        confidence = np.mean([l_sh.visibility, r_sh.visibility, l_hip.visibility, r_hip.visibility])
                        if confidence < 0.4:
                            continue
                            
                        mid_sh_local = ((l_sh.x + r_sh.x) / 2.0, (l_sh.y + r_sh.y) / 2.0)
                        mid_hip_local = ((l_hip.x + r_hip.x) / 2.0, (l_hip.y + r_hip.y) / 2.0)
                        
                        mid_shoulder = (bx/w + mid_sh_local[0]*bw/w, by/h + mid_sh_local[1]*bh/h)
                        mid_hip = (bx/w + mid_hip_local[0]*bw/w, by/h + mid_hip_local[1]*bh/h)
                        
                        xs = [bx/w + lm.x*bw/w for lm in landmarks if lm.visibility > 0.5]
                        ys = [by/h + lm.y*bh/h for lm in landmarks if lm.visibility > 0.5]
                        aspect_ratio = (max(xs) - min(xs)) / (max(ys) - min(ys) + 1e-6) if xs and ys else 0.0
                        
                        feat = {
                            "confidence": float(confidence),
                            "body_angle": float(self._calculate_angle(mid_hip, mid_shoulder)),
                            "aspect_ratio": float(aspect_ratio),
                            "hip_height": float(1.0 - mid_hip[1]),
                            "centroid": (float(mid_hip[0]), float(mid_hip[1])),
                            "mid_hip": (float(mid_hip[0]), float(mid_hip[1])),
                            "state": "Normal",
                            "velocity": 0.0,
                            "time_to_alert": 0.0,
                            "alert_triggered": False,
                            "bbox": (int(bx), int(by), int(bw), int(bh))
                        }
                        current_frame_features.append(feat)
                    except Exception:
                        pass

        # 2. Track & Match IDs using Euclidean Centroid Distance (larger threshold 0.6)
        matched_ids = self._track_and_assign(current_frame_features, timestamp)
        
        # Clean up stale tracks (not seen for > 3 seconds)
        stale_ids = [pid for pid, p in self.tracked_people.items() if timestamp - p.last_seen > 3.0]
        for pid in stale_ids:
            del self.tracked_people[pid]
            
        # 3. Aggregate State for Backward Compatibility (Global Alert)
        if self.tracked_people:
            states = [p.state for p in self.tracked_people.values()]
            if "Fall Detected" in states:
                self.state = "Fall Detected"
            elif "Potential Fall" in states:
                self.state = "Potential Fall"
                potential_starts = [p.potential_fall_start_time for p in self.tracked_people.values() if p.potential_fall_start_time]
                self.potential_fall_start_time = min(potential_starts) if potential_starts else None
            else:
                self.state = "Normal"
                self.potential_fall_start_time = None
                
            # Use features of the highest risk person for display
            highest_risk_person = None
            for p in self.tracked_people.values():
                if highest_risk_person is None or (p.state == "Fall Detected") or (p.state == "Potential Fall" and highest_risk_person.state == "Normal"):
                    highest_risk_person = p
            if highest_risk_person:
                self.last_fall_features = highest_risk_person.last_features
                self.last_fall_features["person_id"] = highest_risk_person.person_id
        else:
            self.state = "Normal"
            self.potential_fall_start_time = None
            self.last_fall_features = {}
            
        # Draw Overlays on the frame
        self._draw_multi_overlay(frame)
        return frame, self.last_fall_features

    def _track_and_assign(self, detections: List[Dict], timestamp: float) -> List[int]:
        matched_ids = []
        if not detections:
            return matched_ids
            
        if not self.tracked_people:
            for det in detections:
                pid = self.next_person_id
                self.next_person_id += 1
                self.tracked_people[pid] = TrackedPerson(pid, self.fps)
                self.tracked_people[pid].update_features(det, timestamp)
                matched_ids.append(pid)
            return matched_ids
            
        track_ids = list(self.tracked_people.keys())
        track_centroids = [self.tracked_people[tid].centroid for tid in track_ids]
        det_centroids = [det["centroid"] for det in detections]
        
        used_dets = set()
        for tid_idx, tid in enumerate(track_ids):
            t_c = track_centroids[tid_idx]
            best_dist = 0.6  # larger threshold to tolerate falls & fallback shifts
            best_det_idx = -1
            
            for d_idx, d_c in enumerate(det_centroids):
                if d_idx in used_dets:
                    continue
                dist = math.dist(t_c, d_c)
                if dist < best_dist:
                    best_dist = dist
                    best_det_idx = d_idx
                    
            if best_det_idx != -1:
                self.tracked_people[tid].update_features(detections[best_det_idx], timestamp)
                matched_ids.append(tid)
                used_dets.add(best_det_idx)
                
        for d_idx, det in enumerate(detections):
            if d_idx not in used_dets:
                pid = self.next_person_id
                self.next_person_id += 1
                self.tracked_people[pid] = TrackedPerson(pid, self.fps)
                self.tracked_people[pid].update_features(det, timestamp)
                matched_ids.append(pid)
                
        return matched_ids

    def _draw_multi_overlay(self, frame: np.ndarray):
        h, w, _ = frame.shape
        
        state_colors = {
            "Normal": (0, 255, 0),
            "Potential Fall": (0, 165, 255),
            "Fall Detected": (0, 0, 255)
        }
        
        for pid, p in self.tracked_people.items():
            features = p.last_features
            if "bbox" not in features:
                continue
                
            bx, by, bw, bh = features["bbox"]
            color = state_colors.get(p.state, (255, 255, 255))
            
            cv2.rectangle(frame, (bx, by), (bx+bw, by+bh), color, 2)
            label = f"ID:{pid} | {p.state}"
            cv2.putText(frame, label, (bx, max(20, by - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (320, 240), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        
        color = state_colors.get(self.state, (255, 255, 255))
        cv2.putText(frame, f"SYSTEM STATE: {self.state}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.putText(frame, f"Tracked People: {len(self.tracked_people)}", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        if self.tracked_people:
            feat = self.last_fall_features
            cv2.putText(frame, f"Target ID: {feat.get('person_id', 'N/A')}", (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, f"Body Angle: {feat.get('body_angle', 0.0):.1f} deg", (20, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, f"Aspect Ratio: {feat.get('aspect_ratio', 0.0):.2f}", (20, 155), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, f"Velocity: {feat.get('velocity', 0.0):.2f} unit/s", (20, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            if self.state == "Potential Fall":
                cv2.putText(frame, f"Verify Time: {feat.get('time_to_alert', 0.0):.1f}s", (20, 215), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
            elif self.state == "Fall Detected":
                cv2.putText(frame, "ALERT: FALL CONFIRMED!", (20, 215), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        else:
            cv2.putText(frame, "No targets tracked", (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120, 120, 120), 1)
