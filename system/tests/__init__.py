from types import SimpleNamespace


def make_hand(side, gesture="กำมือ"):
    points = [SimpleNamespace(x=0.5, y=0.85, z=0.0) for _ in range(21)]
    for finger, joint, tip, x in ((0, 6, 8, 0.38), (1, 10, 12, 0.46),
                                   (2, 14, 16, 0.54), (3, 18, 20, 0.62)):
        opened = gesture == "แบมือ" or (gesture == "ชูนิ้วชี้" and finger == 0)
        opened = opened or (gesture == "ชูสองนิ้ว" and finger in (0, 1))
        points[joint] = SimpleNamespace(x=x, y=0.55, z=0.0)
        points[tip] = SimpleNamespace(x=x, y=0.2 if opened else 0.72, z=0.0)
    points[5] = SimpleNamespace(x=0.35, y=0.65, z=0.0)
    points[17] = SimpleNamespace(x=0.65, y=0.65, z=0.0)
    points[4] = SimpleNamespace(x=0.25, y=0.6, z=0.0)
    if gesture == "จีบนิ้ว":
        points[8] = SimpleNamespace(x=0.39, y=0.5, z=0.0)
        points[4] = SimpleNamespace(x=0.40, y=0.5, z=0.0)
    return {"side": side, "landmarks": points, "confidence": 0.99}


def make_pose(gesture="กลาง", side="Left"):
    points = [SimpleNamespace(x=0.5, y=0.5, z=0.0, visibility=0.99) for _ in range(33)]
    for index, x, y in ((11, 0.65, 0.4), (12, 0.35, 0.4), (23, 0.62, 0.75),
                        (24, 0.38, 0.75), (15, 0.7, 0.65), (16, 0.3, 0.65),
                        (7, 0.56, 0.18), (8, 0.44, 0.18)):
        points[index].x = x
        points[index].y = y
    if gesture == "ยกแขน":
        points[15 if side == "Left" else 16].y = 0.25
    elif gesture == "เอียงตัว":
        offset = 0.08 if side == "Left" else -0.08
        points[11].x += offset
        points[12].x += offset
    elif gesture == "เอียงศีรษะ":
        points[7 if side == "Left" else 8].y += 0.06
    return points
