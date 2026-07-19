import unittest
from app.detection.fall_detector import FallDetector

class TestFallDetector(unittest.TestCase):
    def setUp(self):
        self.detector = FallDetector()

    def test_calculate_angle_vertical(self):
        # p1 (hip) at (0.5, 0.8), p2 (shoulder) at (0.5, 0.4) - straight vertical line
        angle = self.detector._calculate_angle((0.5, 0.8), (0.5, 0.4))
        self.assertAlmostEqual(angle, 0.0, places=2)

    def test_calculate_angle_horizontal(self):
        # p1 at (0.5, 0.8), p2 at (0.8, 0.8) - horizontal line
        angle = self.detector._calculate_angle((0.5, 0.8), (0.8, 0.8))
        self.assertAlmostEqual(angle, 90.0, places=2)

    def test_state_transitions(self):
        # Initial state should be Normal
        self.assertEqual(self.detector.state, "Normal")

    def test_tracking_assignment(self):
        # Initial empty tracked list
        detections = [
            {"centroid": (0.5, 0.5), "mid_hip": (0.5, 0.5), "hip_height": 0.6, "body_angle": 10.0, "aspect_ratio": 0.4}
        ]
        matched_ids = self.detector._track_and_assign(detections, 100.0)
        self.assertEqual(len(matched_ids), 1)
        self.assertEqual(matched_ids[0], 1)
        
        # Second frame: Close detection matches ID 1
        new_detections = [
            {"centroid": (0.51, 0.51), "mid_hip": (0.51, 0.51), "hip_height": 0.6, "body_angle": 12.0, "aspect_ratio": 0.4}
        ]
        matched_ids_2 = self.detector._track_and_assign(new_detections, 101.0)
        self.assertEqual(len(matched_ids_2), 1)
        self.assertEqual(matched_ids_2[0], 1)

if __name__ == '__main__':
    unittest.main()
