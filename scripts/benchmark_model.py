"""Compare the official int8 detector before selecting it for distribution."""
import sys
from pathlib import Path
import urllib.request
import time
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    target = ROOT / "artifacts" / "efficientdet_lite0_int8.tflite"
    target.parent.mkdir(exist_ok=True)
    if not target.exists():
        urllib.request.urlretrieve("https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/int8/1/efficientdet_lite0.tflite", target)
    original = ROOT / "artifacts" / "efficientdet_lite0_float32.tflite"
    if not original.exists():
        urllib.request.urlretrieve("https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float32/1/efficientdet_lite0.tflite", original)
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    result = {}
    source = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.zeros((360, 640, 3), np.uint8))
    for name, path in (("float32", original), ("int8", target)):
        with vision.ObjectDetector.create_from_options(vision.ObjectDetectorOptions(
                base_options=python.BaseOptions(model_asset_path=str(path)),
                running_mode=vision.RunningMode.VIDEO, category_allowlist=["person"], score_threshold=.3)) as detector:
            times = []
            for i in range(8):
                start = time.perf_counter()
                detector.detect_for_video(source, i+1)
                times.append((time.perf_counter()-start)*1000)
        result[name] = round(sum(times[2:])/len(times[2:]), 1)
    print(json.dumps(result))
    (ROOT / "artifacts" / "model-benchmark.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
