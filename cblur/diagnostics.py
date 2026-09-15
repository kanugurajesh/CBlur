"""Explicit diagnostics. Camera frames are never saved or uploaded."""
import json
from pathlib import Path
import time
import traceback
import cv2
from .vision import Vision
from .render import safe_frame


def diagnose(destination, camera_check=False):
    report = {"models": False, "camera_test_requested": camera_check}
    vision = capture = None
    try:
        vision = Vision()
        report["models"] = True
        durations = []
        for i in range(6):
            start = time.perf_counter()
            people = vision.analyze(safe_frame(), i+1)
            durations.append((time.perf_counter()-start)*1000)
        report["blank_frame_people"] = len(people)
        report["warm_inference_ms"] = round(sum(durations[1:])/len(durations[1:]), 1)
        if camera_check:
            capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not capture.isOpened():
                capture.release()
                capture = cv2.VideoCapture(0, cv2.CAP_MSMF)
            report["camera_opened"] = capture.isOpened()
            counts = []
            if capture.isOpened():
                for i in range(5):
                    ok, frame = capture.read()
                    if not ok:
                        break
                    people = vision.analyze(cv2.resize(frame, (1280, 720)), i+100)
                    counts.append({"people": len(people), "faces": sum(p.yaw is not None for p in people)})
            report["camera_frames_analyzed"] = len(counts)
            report["detections"] = counts
        try:
            import pyvirtualcam
            with pyvirtualcam.Camera(width=1280, height=720, fps=30, fmt=pyvirtualcam.PixelFormat.BGR) as output:
                output.send(safe_frame(message="CBlur setup check"))
                report["virtual_camera"] = output.device
        except Exception as exc:
            report["virtual_camera"] = None
            report["virtual_camera_error"] = str(exc)
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        if capture is not None:
            capture.release()
        if vision is not None:
            vision.close()
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2))
    return 0 if report["models"] and "error" not in report else 1
