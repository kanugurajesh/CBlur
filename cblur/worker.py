from dataclasses import replace
import queue
import threading
import time
import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
from .core import PrivacyPolicy, Person, Box
from .render import render, safe_frame
from .vision import Vision


class VirtualOutput(threading.Thread):
    """Independent output clock: stale inference becomes a cover, never raw video."""
    def __init__(self, emergency, report):
        super().__init__(daemon=True)
        self.emergency = emergency
        self.report = report
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.latest = None

    def publish(self, frame):
        with self.lock:
            self.latest = (time.monotonic(), frame.copy())

    def output_frame(self, now):
        with self.lock:
            value = self.latest
        if self.emergency.is_set():
            return safe_frame(message="Privacy locked")
        if value is None or now - value[0] > .5:
            return safe_frame()
        return value[1]

    def run(self):
        try:
            import pyvirtualcam
            with pyvirtualcam.Camera(width=1280, height=720, fps=30,
                                     fmt=pyvirtualcam.PixelFormat.BGR) as camera:
                self.report("Sending to " + camera.device)
                while not self.stop_event.is_set():
                    camera.send(np.ascontiguousarray(self.output_frame(time.monotonic())))
                    camera.sleep_until_next_frame()
                camera.send(safe_frame(message="Camera stopped"))
        except Exception as exc:
            self.report("Virtual camera unavailable. Install OBS Studio, then restart output. " + str(exc))

    def stop(self):
        self.stop_event.set()
        self.join(timeout=3)


def demo_frame(mode):
    frame = np.zeros((720, 1280, 3), np.uint8)
    frame[:] = (51, 46, 38)
    for x in range(0, 1280, 80):
        cv2.line(frame, (x, 0), (x, 720), (61, 56, 47), 1)
    cv2.rectangle(frame, (70, 95), (380, 390), (85, 87, 70), -1)
    cv2.rectangle(frame, (92, 117), (357, 367), (125, 129, 104), -1)
    people = []
    def person(x, color, yaw=0):
        cv2.ellipse(frame, (x, 660), (180, 235), 0, 180, 360, color, -1)
        cv2.rectangle(frame, (x-180, 650), (x+180, 720), color, -1)
        cv2.ellipse(frame, (x, 290), (83, 112), 0, 0, 360, (169, 191, 205), -1)
        cv2.ellipse(frame, (x, 231), (87, 67), 0, 180, 360, (44, 42, 42), -1)
        shift = 33 if yaw else 0
        for eye in (-28, 28):
            cv2.circle(frame, (x+eye+shift, 283), 5, (42, 43, 47), -1)
        cv2.ellipse(frame, (x+shift, 327), (20, 9), 0, 0, 180, (74, 89, 116), 2)
        people.append(Person(Box((x-190)/1280, .22, 380/1280, .78), yaw))
    if mode != "Away":
        person(600, (167, 135, 86), 60 if mode == "Looking away" else 0)
    if mode in ("Visitor", "Away"):
        person(1050, (111, 105, 162))
    return frame, people


class CameraWorker(QThread):
    notice = Signal(str)
    output_notice = Signal(str)

    def __init__(self, settings, emergency, demo=False):
        super().__init__()
        self.settings = replace(settings)
        self.emergency = emergency
        self.demo = demo
        self.commands = queue.SimpleQueue()
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.latest = None
        self.output = None

    def command(self, kind, value=None):
        if kind == "settings":
            value = replace(value)
        self.commands.put((kind, value))

    def snapshot(self):
        with self.lock:
            return self.latest

    def run(self):
        capture = vision = None
        policy = PrivacyPolicy()
        mode = "Facing forward"
        count, fps, mark = 0, 0., time.monotonic()
        previous_timestamp = 0
        try:
            if not self.demo:
                self.notice.emit("Loading local vision models…")
                vision = Vision()
                self.notice.emit("Opening camera…")
                capture = cv2.VideoCapture(self.settings.camera_id, cv2.CAP_DSHOW)
                if not capture.isOpened():
                    capture.release()
                    capture = cv2.VideoCapture(self.settings.camera_id, cv2.CAP_MSMF)
                if not capture.isOpened():
                    raise RuntimeError("Cannot open this camera. Check Windows camera permissions, close other camera apps, or choose another camera.")
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                capture.set(cv2.CAP_PROP_FPS, 30)
            self.notice.emit("Select your outline while facing forward to calibrate.")
            pending_selection = None
            while not self.stop_event.is_set():
                started = time.monotonic()
                while not self.commands.empty():
                    kind, value = self.commands.get()
                    if kind == "settings":
                        self.settings = replace(value)
                    elif kind == "select":
                        pending_selection = value
                    elif kind == "resume":
                        policy.resume_latched = False
                    elif kind == "reset":
                        policy.release()
                    elif kind == "mode":
                        mode = value
                if self.settings.virtual_camera and not self.demo and self.output is None:
                    self.output = VirtualOutput(self.emergency, self.output_notice.emit)
                    self.output.start()
                elif not self.settings.virtual_camera and self.output is not None:
                    self.output.stop()
                    self.output = None
                    self.output_notice.emit("Virtual camera off · local preview only")

                if self.demo:
                    frame, people = demo_frame(mode)
                else:
                    ok, frame = capture.read()
                    if not ok:
                        raise RuntimeError("Camera disconnected or stopped delivering frames. Output is covered. Stop and restart to reconnect.")
                    frame = cv2.resize(frame, (1280, 720))
                    timestamp = max(previous_timestamp + 1, int(time.monotonic()*1000))
                    previous_timestamp = timestamp
                    people = vision.analyze(frame, timestamp)
                now = time.monotonic()
                if pending_selection is not None:
                    if policy.select(people, pending_selection):
                        self.notice.emit("Calibrated. Your normal head position is saved for this session.")
                    else:
                        self.notice.emit("Select one non-overlapping outline with your face visible.")
                    pending_selection = None
                decision = policy.update(people, now, self.settings, self.emergency.is_set())
                protected = render(frame, decision, self.settings, self.emergency.is_set())
                if self.output is not None:
                    self.output.publish(protected)
                count += 1
                if now - mark >= 1:
                    fps = count / (now-mark)
                    count, mark = 0, now
                with self.lock:
                    self.latest = (now, protected, people, decision, fps, (time.monotonic()-started)*1000)
                # The real pipeline never sends frames that skipped analysis.
                self.stop_event.wait(max(0., 1/30 - (time.monotonic()-started)))
        except Exception as exc:
            self.notice.emit(str(exc))
            with self.lock:
                self.latest = None
        finally:
            if self.output is not None:
                self.output.stop()
            if capture is not None:
                capture.release()
            if vision is not None:
                vision.close()

    def stop(self):
        self.stop_event.set()
