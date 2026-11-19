"""ไฟล์เปิดเกม: รัน python main.py แล้วแก้ค่าต่าง ๆ ในโฟลเดอร์ setting"""

import argparse


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Three-lane gesture piano game")
    parser.add_argument("--camera", type=int, default=0, help="Camera number (default: 0)")
    args = parser.parse_args()

    from system.app import main

    main(args.camera)
