from pathlib import Path
import math
import sys
import cv2
import numpy as np
from .core import Box, Person


def model_dir():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "models"


class Vision:
    def __init__(self):
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        self.mp = mp
        root = model_dir()
        for name in ("face_landmarker.task", "efficientdet_lite0.tflite"):
            if not (root / name).is_file():
                raise RuntimeError("Models missing. Run setup.ps1 to download the local vision models.")
        self.faces = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(root / "face_landmarker.task")),
            running_mode=vision.RunningMode.VIDEO, num_faces=8,
            min_face_detection_confidence=.4, min_face_presence_confidence=.4,
            output_facial_transformation_matrixes=True))
        try:
            self.detector = vision.ObjectDetector.create_from_options(vision.ObjectDetectorOptions(
                base_options=python.BaseOptions(model_asset_path=str(root / "efficientdet_lite0.tflite")),
                running_mode=vision.RunningMode.VIDEO, score_threshold=.30,
                category_allowlist=["person"]))
        except Exception:
            self.faces.close()
            raise

    def analyze(self, frame, timestamp):
        # Both detectors analyze the exact frame that is subsequently rendered.
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        small = cv2.resize(rgb, (640, 360))
        source = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=small)
        faces = self.faces.detect_for_video(source, timestamp)
        detections = self.detector.detect_for_video(source, timestamp)
        people = []
        for d in detections.detections:
            b = d.bounding_box
            x, y = max(0., b.origin_x / 640), max(0., b.origin_y / 360)
            right, bottom = min(1., (b.origin_x+b.width)/640), min(1., (b.origin_y+b.height)/360)
            if right > x and bottom > y:
                people.append(Person(Box(x, y, right-x, bottom-y)))
        assigned = set()
        for landmarks, matrix in zip(faces.face_landmarks, faces.facial_transformation_matrixes):
            xs, ys = [p.x for p in landmarks], [p.y for p in landmarks]
            face = Box(min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys))
            cx, cy = face.center
            # Head yaw derived from the canonical-to-observed rotation.
            yaw = math.degrees(math.atan2(float(matrix[0, 2]), float(matrix[2, 2])))
            matches = [i for i, p in enumerate(people) if p.box.contains(cx, cy)]
            if len(matches) == 1 and matches[0] not in assigned:
                people[matches[0]].yaw = yaw
                assigned.add(matches[0])
            else:
                # A face missed by the body detector still gets a generous privacy mask.
                x, y = max(0., face.x-face.w*.8), max(0., face.y-face.h*.25)
                right = min(1., face.x+face.w*1.8)
                people.append(Person(Box(x, y, right-x, 1-y), yaw))
        hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV)
        for p in people:
            b = p.box
            # Central body colors help reject sudden track swaps; no biometric identity stored.
            x1, x2 = int((b.x+b.w*.2)*640), int((b.x+b.w*.8)*640)
            y1, y2 = int((b.y+b.h*.25)*360), int((b.y+b.h*.8)*360)
            roi = hsv[max(0,y1):min(360,y2), max(0,x1):min(640,x2)]
            if roi.size:
                hist = cv2.calcHist([roi], [0, 1], None, [12, 8], [0, 180, 0, 256]).flatten()
                p.appearance = tuple((hist / max(1, hist.sum())).tolist())
        return people

    def close(self):
        self.faces.close()
        self.detector.close()
