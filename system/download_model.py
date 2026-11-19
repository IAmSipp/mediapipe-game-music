from pathlib import Path
import urllib.request
import zipfile


MODEL_PATH = Path(__file__).resolve().parent / "models" / "hand_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)
POSE_MODEL_PATH = MODEL_PATH.parent / "pose_landmarker_lite.task"
POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
)


def download_model(model_path=MODEL_PATH, model_url=MODEL_URL):
    if model_path.is_file() and zipfile.is_zipfile(model_path):
        print(f"Model ready: {model_path}")
        return

    model_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = model_path.with_suffix(".part")
    print(f"Downloading official model: {model_path.name}")
    try:
        with urllib.request.urlopen(model_url, timeout=60) as response:
            temporary_path.write_bytes(response.read())
        if not zipfile.is_zipfile(temporary_path):
            raise ValueError("Downloaded file is not a MediaPipe task bundle")
        temporary_path.replace(model_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    print(f"Model ready: {model_path}")


if __name__ == "__main__":
    try:
        download_model()
        download_model(POSE_MODEL_PATH, POSE_MODEL_URL)
    except (OSError, ValueError) as error:
        print(f"Download failed: {error}")
        print(f"Download manually from {MODEL_URL}")
        print(f"Save as {MODEL_PATH}")
        print(f"Pose model: {POSE_MODEL_URL}")
        print(f"Save as {POSE_MODEL_PATH}")
        raise SystemExit(1)
