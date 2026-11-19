import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from system.camera import HandCamera, draw_hands, mirrored_point
from system.tests import make_pose


def hand(side, closed=True, pointing=False):
    points = [SimpleNamespace(x=0.5, y=0.8, z=0.0) for _ in range(21)]
    for joint, tip in ((6, 8), (10, 12), (14, 16), (18, 20)):
        points[joint] = SimpleNamespace(x=0.5, y=0.5, z=0.0)
        points[tip] = SimpleNamespace(x=0.5, y=0.66 if closed else 0.25, z=0.0)
    if pointing:
        points[8].y = 0.25
    return {"side": side, "landmarks": points, "confidence": 0.99}


class CameraTests(unittest.TestCase):
    def test_mirror_maps_landmarks_without_swapping_hand_labels(self):
        point = SimpleNamespace(x=0.2, y=0.5)
        self.assertEqual(mirrored_point(point, 641, 481), (512, 240))
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        hands = [hand("Left"), hand("Right")]
        draw_hands(frame, hands)
        self.assertTrue(frame.any())
        self.assertEqual([h["side"] for h in hands], ["Left", "Right"])

    def test_real_inference_on_empty_frame_and_resource_cleanup(self):
        fake_capture = Mock()
        fake_capture.isOpened.return_value = True
        fake_capture.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        with patch("system.camera.cv2.VideoCapture", return_value=fake_capture):
            camera = HandCamera()
            self.assertEqual(camera.error, "")
            frame, hands = camera.read()
            self.assertEqual(camera.error, "")
            self.assertEqual(frame.shape, (480, 640, 3))
            self.assertEqual(hands, [])
            first_timestamp = camera.last_timestamp_ms
            camera.read()
            self.assertGreater(camera.last_timestamp_ms, first_timestamp)
            camera.close()
            camera.close()
            fake_capture.release.assert_called_once()
            self.assertIsNone(camera.landmarker)

    def test_camera_open_failure_releases_resources(self):
        capture = Mock()
        capture.isOpened.return_value = False
        landmarker = Mock()
        with patch("system.camera.cv2.VideoCapture", return_value=capture), patch(
            "system.camera.vision.HandLandmarker.create_from_options", return_value=landmarker,
        ):
            camera = HandCamera()
            self.assertIn("Camera unavailable", camera.error)
            self.assertEqual(camera.read(), (None, []))
            capture.release.assert_called_once()
            landmarker.close.assert_called_once()

    def test_read_failure_clears_old_hands(self):
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.return_value = (False, None)
        landmarker = Mock()
        with patch("system.camera.cv2.VideoCapture", return_value=capture), patch(
            "system.camera.vision.HandLandmarker.create_from_options", return_value=landmarker,
        ):
            camera = HandCamera()
            self.assertEqual(camera.read(), (None, []))
            self.assertIn("disconnected", camera.error)
            capture.release.assert_called_once()
            landmarker.close.assert_called_once()

    def test_missing_model_is_explained(self):
        with patch("system.camera.MODEL_PATH") as model_path:
            model_path.is_file.return_value = False
            camera = HandCamera()
        self.assertIn("python -m system.download_model", camera.error)
        self.assertEqual(camera.read(), (None, []))




class PoseCameraTests(unittest.TestCase):
    def test_real_pose_model_on_empty_frame_without_loading_hand_model(self):
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        with patch("system.camera.cv2.VideoCapture", return_value=capture), patch(
            "system.camera.vision.HandLandmarker.create_from_options",
        ) as hand_factory:
            camera = HandCamera(detect_hands=False, detect_pose=True)
            try:
                self.assertEqual(camera.error, "")
                frame, hands = camera.read()
                self.assertEqual(camera.error, "")
                self.assertEqual(frame.shape, (480, 640, 3))
                self.assertEqual(hands, [])
                self.assertEqual(camera.pose_landmarks, [])
                hand_factory.assert_not_called()
            finally:
                camera.close()
            self.assertIsNone(camera.pose_landmarker)
            capture.release.assert_called_once()

    def test_missing_pose_frame_clears_previous_pose(self):
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        detector = Mock()
        detector.detect_for_video.side_effect = [SimpleNamespace(pose_landmarks=[make_pose()]),
                                               SimpleNamespace(pose_landmarks=[])]
        with patch("system.camera.cv2.VideoCapture", return_value=capture), patch(
            "system.camera.vision.PoseLandmarker.create_from_options", return_value=detector,
        ):
            camera = HandCamera(detect_hands=False, detect_pose=True)
            camera.read()
            self.assertEqual(len(camera.pose_landmarks), 33)
            camera.read()
            self.assertEqual(camera.pose_landmarks, [])
            camera.close()
            detector.close.assert_called_once()

    def test_pose_initialization_failure_closes_already_loaded_hand_model(self):
        hand_detector = Mock()
        with patch("system.camera.vision.HandLandmarker.create_from_options", return_value=hand_detector), patch(
            "system.camera.vision.PoseLandmarker.create_from_options", side_effect=RuntimeError("pose failed"),
        ):
            camera = HandCamera(detect_hands=True, detect_pose=True)
            self.assertIn("pose failed", camera.error)
            hand_detector.close.assert_called_once()
            self.assertEqual(camera.pose_landmarks, [])
