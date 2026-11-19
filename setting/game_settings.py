# แก้ค่าแล้วบันทึก ปิดและเปิดเกมใหม่
GAME_TITLE = "HAND PIANO"

# จังหวะเริ่มต้น และระยะห่างขั้นต่ำของโน้ตเป็นวินาที
BPM = 76
MIN_NOTE_INTERVAL = 0.55

# ความเร็วพิกเซล/วินาที และความเร็วที่เพิ่มทุกวินาที
START_SPEED = 240.0
ACCELERATION = 4.0
FIRST_NOTE_DELAY = 2.6
HIT_WINDOW_SECONDS = 0.24
PERFECT_WINDOW_SECONDS = 0.10

SCORE_PER_HIT = 100
PERFECT_BONUS = 50
MAX_MISSES = 5

# เสียง MIDI ที่สุ่มใช้ แต่ละโน้ตสุ่มหนึ่งในสามช่อง
NOTE_POOL = [60, 62, 64, 65, 67, 69, 72]

NOTE_WIDTH = 112
NOTE_HEIGHT = 64
LANE_COLORS = [(58, 209, 199), (183, 145, 250), (245, 177, 92)]
BOARD_COLOR = (29, 40, 58)
LINE_COLOR = (224, 232, 245)
SOUND_ENABLED = True
SOUND_VOLUME = 0.35
