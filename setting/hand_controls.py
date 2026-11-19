# ใช้ไฟล์นี้เมื่อ USE_PRESET = False
from math import sqrt

USE_HANDS = True
USE_POSE = False
CLOSED_DISTANCE_RATIO = 1.0

LEFT_INSTRUCTION = "ซ้าย: กำมือซ้าย"
CENTER_INSTRUCTION = "กลาง: กำมือสองข้าง"
RIGHT_INSTRUCTION = "ขวา: กำมือขวา"


def distance(point_a, point_b):
    return sqrt(
        (point_a.x - point_b.x) ** 2
        + (point_a.y - point_b.y) ** 2
        + (point_a.z - point_b.z) ** 2
    )


def is_hand_closed(landmarks):
    # ข้อมือ 0; ปลายนิ้ว 8/12/16/20; ข้อ PIP 6/10/14/18
    wrist = landmarks[0]
    index_closed = distance(landmarks[8], wrist) < distance(landmarks[6], wrist) * CLOSED_DISTANCE_RATIO
    middle_closed = distance(landmarks[12], wrist) < distance(landmarks[10], wrist) * CLOSED_DISTANCE_RATIO
    ring_closed = distance(landmarks[16], wrist) < distance(landmarks[14], wrist) * CLOSED_DISTANCE_RATIO
    pinky_closed = distance(landmarks[20], wrist) < distance(landmarks[18], wrist) * CLOSED_DISTANCE_RATIO
    if index_closed and middle_closed and ring_closed and pinky_closed:
        return True
    else:
        return False


def get_note_command(hands, pose_landmarks=None):
    # hands เป็นรายการมือ ข้างจริง Left/Right และ landmarks 21 จุด
    left_closed = False
    right_closed = False
    for hand in hands:
        if hand["side"] == "Left":
            left_closed = is_hand_closed(hand["landmarks"])
        elif hand["side"] == "Right":
            right_closed = is_hand_closed(hand["landmarks"])

    # ตรวจสองข้างก่อน เพื่อไม่ให้สั่งช่องซ้ายหรือขวาซ้ำ
    if left_closed and right_closed:
        return "CENTER"
    elif left_closed:
        return "LEFT"
    elif right_closed:
        return "RIGHT"
    else:
        return None
