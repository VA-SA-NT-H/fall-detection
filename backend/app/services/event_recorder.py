import os
import cv2
import time
from collections import deque
from threading import Thread

class EventRecorder:
    def __init__(self, output_dir: str = "events", buffer_size: int = 90):
        self.output_dir = output_dir
        self.buffer_size = buffer_size
        self.frame_buffer = deque(maxlen=buffer_size)
        self.is_recording = False
        self.recorded_frames = []
        self.target_frame_count = 180  # ~6 seconds total at 30fps (3s pre-fall + 3s post-fall)
        
        # Ensure output directory exists
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def add_frame(self, frame):
        """Adds a copy of the current frame to the rolling buffer."""
        self.frame_buffer.append(frame.copy())
        if self.is_recording:
            self.recorded_frames.append(frame.copy())
            if len(self.recorded_frames) >= self.target_frame_count:
                self._save_recording_async()

    def trigger_recording(self):
        """Triggers the post-fall capture and subsequent file export."""
        if self.is_recording:
            return
        
        self.is_recording = True
        # Initialize recording array with the pre-fall history buffer
        self.recorded_frames = list(self.frame_buffer)

    def _save_recording_async(self):
        self.is_recording = False
        frames_to_save = self.recorded_frames.copy()
        self.recorded_frames = []
        
        # Run saving in a background thread to prevent blocking main video generator
        thread = Thread(target=self._write_video_file, args=(frames_to_save,))
        thread.start()

    def _write_video_file(self, frames):
        if not frames:
            return
            
        h, w, _ = frames[0].shape
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"fall_event_{timestamp}.mp4"
        filepath = os.path.join(self.output_dir, filename)
        
        # Define codec and create VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(filepath, fourcc, 25.0, (w, h))
        
        for frame in frames:
            out.write(frame)
        out.release()
        
        print(f"[EventRecorder] Saved fall incident video clip to: {filepath}")
