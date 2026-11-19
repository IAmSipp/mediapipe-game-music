from math import sqrt, atan2, degrees, isfinite
from setting import control_settings as settings
from setting import hand_controls


def distance(point_a, point_b):
    return sqrt((point_a.x-point_b.x)**2 + (point_a.y-point_b.y)**2 + (point_a.z-point_b.z)**2)


PRESETS = {}
for suffix, side in (("ซ้าย", "Left"), ("ขวา", "Right")):
    for gesture in ("กำมือ", "แบมือ", "ชูนิ้วชี้", "ชูสองนิ้ว", "จีบนิ้ว"):
        PRESETS[gesture + suffix] = ("hand", gesture, side)
    for gesture in ("ยกแขน", "เอียงตัว", "เอียงศีรษะ"):
        PRESETS[gesture + suffix] = ("pose", gesture, side)

for gesture in ("กำมือ", "แบมือ", "ชูนิ้วชี้", "ชูสองนิ้ว", "จีบนิ้ว"):
    PRESETS[gesture + "สองข้าง"] = ("hand", gesture, "Both")


def pose_is_visible(pose_landmarks, indices):
    if len(pose_landmarks) != 33:
        return False
    for index in indices:
        point = pose_landmarks[index]
        if point.visibility is None or point.visibility < 0.6:
            return False
        if not (0 <= point.x <= 1 and 0 <= point.y <= 1):
            return False
    return True


def hand_matches(landmarks, gesture):

    if len(landmarks) != 21:
        return False
    closed_ratio = 0.95 + 0.1 * settings.SENSITIVITY
    open_ratio = 1.25 - 0.1 * settings.SENSITIVITY
    wrist = landmarks[0]
    closed = []
    opened = []
    for tip, joint in ((8, 6), (12, 10), (16, 14), (20, 18)):
        tip_distance = distance(landmarks[tip], wrist)
        joint_distance = distance(landmarks[joint], wrist)
        if joint_distance < 0.000001:
            return False
        closed.append(tip_distance < joint_distance * closed_ratio)
        opened.append(tip_distance > joint_distance * open_ratio)

    if gesture == "กำมือ":
        return all(closed)
    elif gesture == "แบมือ":
        return all(opened)
    elif gesture == "ชูนิ้วชี้":
        return opened[0] and closed[1] and closed[2] and closed[3]
    elif gesture == "ชูสองนิ้ว":
        return opened[0] and opened[1] and closed[2] and closed[3]
    elif gesture == "จีบนิ้ว":
        palm_width = distance(landmarks[5], landmarks[17])
        pinch_distance = distance(landmarks[4], landmarks[8])
        return palm_width > 0.000001 and pinch_distance < palm_width * 0.3 * settings.SENSITIVITY
    else:
        return False


def preset_state(action, hands, pose_landmarks):
    source, gesture, side = PRESETS[action]
    if source == "hand" and side == "Both":
        left_active, left_seen = preset_state(gesture + "ซ้าย", hands, pose_landmarks)
        right_active, right_seen = preset_state(gesture + "ขวา", hands, pose_landmarks)
        return left_active and right_active, left_seen and right_seen
    if source == "hand":
        found = False
        active = False
        for hand in hands:
            if hand["side"] == side and hand.get("confidence", 1.0) >= 0.6:
                found = True
                if hand_matches(hand["landmarks"], gesture):
                    active = True
        return active, found

    if gesture == "ยกแขน":
        shoulder, wrist = (11, 15) if side == "Left" else (12, 16)
        if not pose_is_visible(pose_landmarks, (11, 12, shoulder, wrist)):
            return False, False
        shoulder_width = abs(pose_landmarks[11].x - pose_landmarks[12].x)
        if shoulder_width < 0.02:
            return False, False
        margin = shoulder_width * 0.1 / settings.SENSITIVITY
        return pose_landmarks[wrist].y < pose_landmarks[shoulder].y - margin, True
    elif gesture == "เอียงตัว":
        if not pose_is_visible(pose_landmarks, (11, 12, 23, 24)):
            return False, False
        shoulder_width = abs(pose_landmarks[11].x - pose_landmarks[12].x)
        if shoulder_width < 0.02:
            return False, False
        shoulders_x = (pose_landmarks[11].x + pose_landmarks[12].x) / 2
        hips_x = (pose_landmarks[23].x + pose_landmarks[24].x) / 2
        lean = (shoulders_x - hips_x) / shoulder_width
        threshold = 0.18 / settings.SENSITIVITY

        if side == "Left":
            return lean > threshold, True
        else:
            return lean < -threshold, True
    elif gesture == "เอียงศีรษะ":
        if not pose_is_visible(pose_landmarks, (7, 8)):
            return False, False
        left_ear = pose_landmarks[7]
        right_ear = pose_landmarks[8]
        ear_width = abs(left_ear.x - right_ear.x) * 640
        if ear_width < 10:
            return False, False

        angle = degrees(atan2((left_ear.y - right_ear.y) * 480, ear_width))
        threshold = 15 / settings.SENSITIVITY
        if side == "Left":
            return angle > threshold, True
        else:
            return angle < -threshold, True
    return False, False


class GameControls:
    def __init__(self):
        if type(settings.USE_PRESET) is not bool:
            raise ValueError("setting/control_settings.py: USE_PRESET ต้องเป็น True หรือ False")
        self.custom = not settings.USE_PRESET
        if self.custom:
            self.detect_hands = hand_controls.USE_HANDS
            self.detect_pose = hand_controls.USE_POSE
            self.left_instruction = hand_controls.LEFT_INSTRUCTION
            self.center_instruction = hand_controls.CENTER_INSTRUCTION
            self.right_instruction = hand_controls.RIGHT_INSTRUCTION
        else:
            self.actions = {
                "LEFT": settings.LEFT_ACTION, "CENTER": settings.CENTER_ACTION,
                "RIGHT": settings.RIGHT_ACTION,
            }
            for name, action in self.actions.items():
                if action not in PRESETS:
                    raise ValueError(f"setting/control_settings.py: {name} = {action!r} ไม่อยู่ในรายการท่า")
            if len(set(self.actions.values())) != 3:
                raise ValueError("setting/control_settings.py: เลือกสามท่าให้ต่างกัน")
            if (not isfinite(settings.SENSITIVITY) or not 0.5 <= settings.SENSITIVITY <= 1.5
                    or not isfinite(settings.HOLD_SECONDS) or settings.HOLD_SECONDS < 0):
                raise ValueError("setting/control_settings.py: SENSITIVITY 0.5–1.5; HOLD_SECONDS >= 0")
            sources = [PRESETS[action][0] for action in self.actions.values()]
            self.detect_hands = "hand" in sources
            self.detect_pose = "pose" in sources
            self.left_instruction = f"ซ้าย: {settings.LEFT_ACTION}"
            self.center_instruction = f"กลาง: {settings.CENTER_ACTION}"
            self.right_instruction = f"ขวา: {settings.RIGHT_ACTION}"
        if not self.detect_hands and not self.detect_pose:
            raise ValueError("setting/hand_controls.py: เปิด USE_HANDS หรือ USE_POSE อย่างน้อยหนึ่งอย่าง")
        self.reset()

    def reset(self):
        self.command = None
        self.pending_command = None
        self.held_seconds = 0.0
        self.left_seen = False
        self.right_seen = False

    def update(self, hands, pose_landmarks, delta_seconds):
        self.left_seen = any(hand["side"] == "Left" for hand in hands)
        self.right_seen = any(hand["side"] == "Right" for hand in hands)
        if self.detect_pose and pose_landmarks:
            self.left_seen = self.right_seen = True
        if self.custom:
            self.command = hand_controls.get_note_command(hands, pose_landmarks)
            if self.command not in ("LEFT", "CENTER", "RIGHT", None):
                raise ValueError("setting/hand_controls.py: get_note_command ต้องคืน LEFT, CENTER, RIGHT หรือ None")
            return self.command
        active = [command for command, action in self.actions.items()
                  if preset_state(action, hands, pose_landmarks)[0]]
        both = [command for command in active if PRESETS[self.actions[command]][2] == "Both"]
        if both:
            active = both
        candidate = active[0] if len(active) == 1 else None
        if candidate is None:
            self.pending_command = None
            self.held_seconds = 0.0
            self.command = None
        else:
            if candidate != self.pending_command:
                self.pending_command = candidate
                self.held_seconds = 0.0
            else:
                self.held_seconds += max(0.0, delta_seconds)
            self.command = candidate if self.held_seconds + 1e-9 >= settings.HOLD_SECONDS else None
        return self.command
