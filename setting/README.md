# ปรับแต่งเกม

| ไฟล์ | ใช้ปรับอะไร |
|---|---|
| `control_settings.py` | เลือกท่าสามช่อง |
| `hand_controls.py` | เขียนกฎเองเมื่อ USE_PRESET = False |
| `game_settings.py` | ความเร็ว อัตราเร่ง จังหวะ เสียงสุ่ม คะแนน และสี |

เริ่มจาก `control_settings.py` เช่น เปลี่ยนเป็นชูสองนิ้ว:

```python
USE_PRESET = True
LEFT_ACTION = "ชูสองนิ้วซ้าย"
CENTER_ACTION = "ชูสองนิ้วสองข้าง"
RIGHT_ACTION = "ชูสองนิ้วขวา"
```

คัดลอกชื่อท่าในไฟล์เดียวกัน ปรับ SENSITIVITY ให้ตรวจง่ายขึ้น หรือ HOLD_SECONDS ให้ค้างนานขึ้น
ตั้ง `USE_PRESET = False` แล้วแก้ `get_note_command()` ใน `hand_controls.py` เพื่อเขียนเอง
เริ่มเกมหรือเล่นใหม่ด้วยปุ่มเมาส์
แบบเขียนเองไม่อ่านชื่อท่า ความไว และเวลาค้างของสำเร็จรูป สลับกลับ True ได้โดยโค้ดเดิมยังอยู่
เกมสุ่มต่อเนื่อง ปรับ START_SPEED และ ACCELERATION ใน game_settings.py เพื่อกำหนดความเร็วและอัตราเร่ง
แก้แล้วบันทึก ปิดและเปิดเกมใหม่
[ตัวอย่างละเอียด](../system/docs/CONTROL_DETAILS.md)
