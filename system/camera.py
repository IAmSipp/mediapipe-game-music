import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from system.download_model import MODEL_PATH, POSE_MODEL_PATH


CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
)
POSE_CONNECTIONS = (
    (0, 7), (0, 8), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24), (23, 25), (25, 27), (24, 26), (26, 28),
)


def mirrored_point(landmark, width, height):
    return (round((1 - landmark.x) * (width - 1)), round(landmark.y * (height - 1)))


def draw_hands(mirrored_frame, hands):
    height, width = mirrored_frame.shape[:2]
    for hand in hands:
        color = (100, 235, 100) if hand["side"] == "Left" else (255, 200, 80)
        points = [mirrored_point(point, width, height) for point in hand["landmarks"]]
        for start, end in CONNECTIONS:
            cv2.line(mirrored_frame, points[start], points[end], color, 2)
        for point in points:
            cv2.circle(mirrored_frame, point, 4, (255, 255, 255), -1)
        wrist_x, wrist_y = points[0]
        cv2.putText(
            mirrored_frame, hand["side"],
            (max(5, min(wrist_x - 30, width - 130)), max(22, min(wrist_y + 24, height - 8))),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2,
        )


def draw_pose(mirrored_frame, landmarks):
    if not landmarks:
        return
    height, width = mirrored_frame.shape[:2]
    points = [mirrored_point(point, width, height) for point in landmarks]
    for start, end in POSE_CONNECTIONS:
        if landmarks[start].visibility >= 0.6 and landmarks[end].visibility >= 0.6:
            cv2.line(mirrored_frame, points[start], points[end], (80, 200, 255), 2)
    for index, point in enumerate(landmarks):
        if point.visibility >= 0.6:
            cv2.circle(mirrored_frame, points[index], 4, (255, 255, 255), -1)
    for index, label in ((15, "Left"), (16, "Right")):
        if landmarks[index].visibility >= 0.6:
            x, y = points[index]
            cv2.putText(mirrored_frame, label, (max(5, min(x, width - 140)), max(20, min(y - 10, height - 5))),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 200, 255), 2)


class HandCamera:
    def __init__(self, camera_index=0, detect_hands=True, detect_pose=False):
        self.capture = None
        self.landmarker = None
        self.pose_landmarker = None
        self.pose_landmarks = []
        self.last_timestamp_ms = -1
        self.error = ""
        try:
            if detect_hands:
                if not MODEL_PATH.is_file():
                    raise FileNotFoundError("Hand model missing. Run: python -m system.download_model")
                options = vision.HandLandmarkerOptions(

                    base_options=python.BaseOptions(model_asset_buffer=MODEL_PATH.read_bytes()),
                    running_mode=vision.RunningMode.VIDEO,
                    num_hands=2,
                    min_hand_detection_confidence=0.5,
                    min_hand_presence_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                self.landmarker = vision.HandLandmarker.create_from_options(options)
            if detect_pose:
                if not POSE_MODEL_PATH.is_file():
                    raise FileNotFoundError("Pose model missing. Run: python -m system.download_model")
                options = vision.PoseLandmarkerOptions(
                    base_options=python.BaseOptions(model_asset_buffer=POSE_MODEL_PATH.read_bytes()),
                    running_mode=vision.RunningMode.VIDEO,
                    num_poses=1,
                )
                self.pose_landmarker = vision.PoseLandmarker.create_from_options(options)
            self.capture = cv2.VideoCapture(camera_index)
            if not self.capture.isOpened():
                raise OSError("Camera unavailable. Close other camera apps and check permissions.")
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        except Exception as error:
            self.error = str(error)
            self.close()

    def read(self):
        if self.error:
            return None, []
        try:
            success, frame = self.capture.read()
            if not success:
                raise OSError("Camera disconnected or cannot read a frame. Check cable and restart.")
            frame = cv2.resize(frame, (640, 480))

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            timestamp_ms = max(int(time.perf_counter() * 1000), self.last_timestamp_ms + 1)
            self.last_timestamp_ms = timestamp_ms
            hands = []
            if self.landmarker is not None:
                result = self.landmarker.detect_for_video(image, timestamp_ms)
                for landmarks, categories in zip(result.hand_landmarks, result.handedness):
                    category = categories[0]
                    hands.append({
                        "side": category.category_name,
                        "landmarks": landmarks,
                        "confidence": category.score,
                    })
            self.pose_landmarks = []
            if self.pose_landmarker is not None:
                result = self.pose_landmarker.detect_for_video(image, timestamp_ms)
                if result.pose_landmarks:
                    self.pose_landmarks = result.pose_landmarks[0]

            mirrored_frame = cv2.flip(frame, 1)
            draw_hands(mirrored_frame, hands)
            draw_pose(mirrored_frame, self.pose_landmarks)
            return cv2.cvtColor(mirrored_frame, cv2.COLOR_BGR2RGB), hands
        except Exception as error:
            self.error = str(error)
            self.close()
            return None, []

    def close(self):
        self.pose_landmarks = []
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        if self.landmarker is not None:
            self.landmarker.close()
            self.landmarker = None
        if self.pose_landmarker is not None:
            self.pose_landmarker.close()
            self.pose_landmarker = None
