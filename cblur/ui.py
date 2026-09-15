from dataclasses import asdict, fields
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import sys
import threading
import time
import cv2
from PySide6.QtCore import Qt, QTimer, QRectF, QStandardPaths, QAbstractNativeEventFilter
from PySide6.QtGui import QColor, QPainter, QPen, QImage, QFont, QIcon, QPixmap, QAction
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox, QComboBox, QSlider, QFrame, QSystemTrayIcon, QMenu,
    QScrollArea, QMessageBox)
from .core import Settings
from .render import safe_frame
from .worker import CameraWorker


STYLE = """
QWidget { background: #101719; color: #dfeae7; font: 10pt 'Segoe UI'; }
QMainWindow { background: #101719; }
QLabel { background: transparent; }
QLabel#brand { font-size: 23pt; font-weight: 700; color: #f3faf6; }
QLabel#subtitle { color: #8fa49e; }
QLabel#eyebrow { color: #8da69d; font-size: 9pt; font-weight: 600; }
QLabel#status { color: #bcf2d5; font-size: 13pt; font-weight: 600; }
QLabel#hint { color: #9bb0a9; font-size: 9pt; }
QLabel#notice { color: #e1ca99; padding: 12px; background: #242720; border-radius: 8px; }
QFrame#panel { background: #182123; border: 1px solid #2a3737; border-radius: 12px; }
QFrame#panel QLabel, QFrame#panel QCheckBox { background: transparent; }
QPushButton { border: 1px solid #354843; border-radius: 8px; padding: 10px 16px; background: #25332f; font-weight: 600; }
QPushButton:hover { background: #334a40; border-color: #68977e; }
QPushButton:disabled { color: #71817c; background: #202926; }
QPushButton#primary { background: #b8edce; color: #10231a; border: none; }
QPushButton#primary:hover { background: #d2f9e1; }
QPushButton#privacy { background: #423029; border-color: #805b48; color: #f8d7bd; }
QComboBox { background: #202d2c; border: 1px solid #3a4a46; border-radius: 6px; padding: 8px; }
QComboBox QAbstractItemView { selection-background-color: #3b6250; }
QCheckBox { spacing: 10px; padding: 6px 0; }
QCheckBox::indicator { width: 20px; height: 20px; border-radius: 5px; border: 1px solid #526960; background: #22312b; }
QCheckBox::indicator:checked { background: #ace2c0; border: 5px solid #446b54; }
QSlider::groove:horizontal { height: 5px; background: #344940; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #a2d7b5; }
QSlider::handle:horizontal { background: #c8f4d6; width: 15px; margin: -5px 0; border-radius: 7px; }
QScrollArea { border: none; background: transparent; }
QToolTip { background: #243b30; color: #e7f5ed; border: 1px solid #5b8070; }
"""


def label(text, name=None):
    item = QLabel(text)
    item.setWordWrap(True)
    if name:
        item.setObjectName(name)
    return item


def icon():
    pix = QPixmap(64, 64)
    pix.fill(QColor("#b8edce"))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("#163523"), 5))
    p.drawRoundedRect(12, 17, 40, 30, 8, 8)
    p.drawEllipse(25, 25, 14, 14)
    p.end()
    return QIcon(pix)


class Preview(QWidget):
    def __init__(self, selected):
        super().__init__()
        self.selected = selected
        self.image = None
        self.people = []
        self.owner = None
        self.mirror = True
        self.setMinimumSize(480, 310)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setToolTip("Click your outline while facing forward. Outlines are local and are never sent to your call.")

    def image_rect(self):
        width = min(self.width(), self.height()*16/9)
        height = width*9/16
        return QRectF((self.width()-width)/2, (self.height()-height)/2, width, height)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#0c1214"))
        r = self.image_rect()
        if self.image is not None:
            p.drawImage(r, self.image)
        else:
            p.setPen(QColor("#b0c9be"))
            p.setFont(QFont("Segoe UI", 20, QFont.Weight.DemiBold))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "Your space. Your camera.")
            p.setFont(QFont("Segoe UI", 10))
            p.setPen(QColor("#79968a"))
            p.drawText(r.adjusted(0, 65, 0, 65), Qt.AlignmentFlag.AlignCenter, "Start your camera to set up automatic privacy")
        for i, person in enumerate(self.people):
            b = person.box
            x = 1-b.x-b.w if self.mirror else b.x
            box = QRectF(r.x()+x*r.width(), r.y()+b.y*r.height(), b.w*r.width(), b.h*r.height())
            is_owner = self.owner == b
            color = QColor("#bbf3ce" if is_owner else "#f0c28f")
            p.setPen(QPen(color, 2))
            p.drawRoundedRect(box, 8, 8)
            text = "YOU" if is_owner else f"PERSON {i+1} · CLICK TO SELECT"
            p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            text_width = p.fontMetrics().horizontalAdvance(text) + 16
            tag_x = max(r.x(), min(box.x(), r.right()-text_width))
            tag = QRectF(tag_x, max(r.y(), box.y()-26), text_width, 24)
            p.fillRect(tag, QColor("#14251d"))
            p.drawText(tag.adjusted(8, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, text)
        p.end()

    def mousePressEvent(self, event):
        r = self.image_rect()
        if r.contains(event.position()):
            x = (event.position().x()-r.x())/r.width()
            y = (event.position().y()-r.y())/r.height()
            self.selected((1-x if self.mirror else x, y))

    def show_frame(self, bgr, people=(), owner=None):
        if self.mirror:
            bgr = cv2.flip(bgr, 1)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        self.image = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format.Format_RGB888).copy()
        self.people, self.owner = people, owner
        self.update()


class GlobalHotkey(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.registered = False
        if sys.platform == "win32":
            # Ctrl + Shift + Space. NOREPEAT prevents key-repeat toggling.
            self.registered = bool(ctypes.windll.user32.RegisterHotKey(None, 0xCB10, 0x4006, 0x20))

    def nativeEventFilter(self, event_type, message):
        if sys.platform == "win32":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam == 0xCB10:
                self.callback()
                return True, 0
        return False, 0

    def close(self):
        if self.registered:
            ctypes.windll.user32.UnregisterHotKey(None, 0xCB10)


class MainWindow(QMainWindow):
    def __init__(self, demo=False, persist=True):
        super().__init__()
        self.demo, self.persist = demo, persist
        self.worker = None
        self.emergency = threading.Event()
        self.last_stamp = 0
        self.settings_path = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)) / "settings.json"
        self.settings = self.load_settings()
        self.setWindowTitle("CBlur · Camera privacy" + (" · DEMO" if demo else ""))
        self.setWindowIcon(icon())
        self.resize(1240, 830)
        self.setMinimumSize(1030, 720)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(28, 22, 28, 20)
        outer.setSpacing(18)
        header = QHBoxLayout()
        branding = QVBoxLayout()
        branding.addWidget(label("cblur", "brand"))
        subtitle = label("A little privacy, automatically.", "subtitle")
        subtitle.setWordWrap(False)
        branding.addWidget(subtitle)
        header.addLayout(branding)
        header.addStretch()
        local_badge = label("●  LOCAL PROCESSING" + ("  /  DEMO" if demo else ""), "eyebrow")
        local_badge.setWordWrap(False)
        header.addWidget(local_badge)
        self.help_button = QPushButton("Connect to a call")
        self.help_button.clicked.connect(self.show_help)
        header.addWidget(self.help_button)
        outer.addLayout(header)
        content = QHBoxLayout()
        content.setSpacing(22)
        left = QVBoxLayout()
        left.addWidget(label("PROTECTED PREVIEW", "eyebrow"))
        self.preview = Preview(lambda point: self.send("select", point))
        left.addWidget(self.preview, 1)
        self.status = label("Camera is off", "status")
        left.addWidget(self.status)
        self.metrics = label("Your camera stays off until you start it.", "hint")
        left.addWidget(self.metrics)
        self.notice = label("Start the camera, face forward, then click your outline to calibrate.", "notice")
        self.notice.setMinimumHeight(56)
        left.addWidget(self.notice)
        controls = QHBoxLayout()
        self.camera = QComboBox()
        for i in range(6):
            self.camera.addItem(f"Camera {i}" + (" · default" if i == 0 else ""), i)
        self.camera.setCurrentIndex(self.settings.camera_id)
        controls.addWidget(self.camera, 1)
        self.start_button = QPushButton("Start camera" if not demo else "Start demo")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self.toggle_camera)
        controls.addWidget(self.start_button)
        self.calibrate = QPushButton("Recalibrate")
        self.calibrate.clicked.connect(lambda: self.send("reset"))
        controls.addWidget(self.calibrate)
        left.addLayout(controls)
        self.output_status = label("Virtual camera off · local preview only", "hint")
        left.addWidget(self.output_status)
        content.addLayout(left, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedWidth(315)
        panel = QFrame()
        panel.setObjectName("panel")
        side = QVBoxLayout(panel)
        side.setContentsMargins(20, 20, 20, 20)
        side.setSpacing(10)
        side.addWidget(label("PRIVACY RULES", "eyebrow"))
        self.look = QCheckBox("Blur when looking away")
        self.look.setChecked(self.settings.look_away)
        side.addWidget(self.look)
        side.addWidget(label("Turn your head to either side to protect the whole frame.", "hint"))
        self.angle_label = label("")
        side.addWidget(self.angle_label)
        self.angle = QSlider(Qt.Orientation.Horizontal)
        self.angle.setRange(10, 70)
        self.angle.setToolTip("Lower angles blur sooner. Try 10–20° for smaller head turns.")
        self.angle.setValue(self.settings.turn_angle)
        side.addWidget(self.angle)
        self.others = QCheckBox("Hide other people")
        self.others.setChecked(self.settings.hide_others)
        side.addWidget(self.others)
        side.addWidget(label("Covers detected body regions, including people facing away.", "hint"))
        side.addWidget(label("Always on: protection when you leave", "hint"))
        self.manual = QCheckBox("Hold privacy until I resume")
        self.manual.setChecked(self.settings.manual_resume)
        side.addWidget(self.manual)
        side.addWidget(label("APPEARANCE", "eyebrow"))
        self.effect = QComboBox()
        self.effect.addItems(["Blur", "Solid cover", "Be right back"])
        self.effect.setCurrentText(self.settings.style)
        side.addWidget(self.effect)
        self.strength_label = label("")
        side.addWidget(self.strength_label)
        self.strength = QSlider(Qt.Orientation.Horizontal)
        self.strength.setRange(30, 100)
        self.strength.setValue(self.settings.strength)
        side.addWidget(self.strength)
        self.mirror = QCheckBox("Mirror local preview")
        self.mirror.setChecked(self.settings.mirror)
        side.addWidget(self.mirror)
        self.virtual = QCheckBox("Enable virtual camera")
        self.virtual.setChecked(False)
        self.virtual.setEnabled(not demo)
        side.addWidget(self.virtual)
        side.addWidget(label("Requires OBS virtual camera. Select it in your meeting's camera settings.", "hint"))
        if demo:
            side.addWidget(label("DEMO SCENARIO", "eyebrow"))
            self.scenario = QComboBox()
            self.scenario.addItems(["Facing forward", "Looking away", "Visitor", "Away"])
            self.scenario.currentTextChanged.connect(lambda value: self.send("mode", value))
            side.addWidget(self.scenario)
        side.addStretch()
        self.privacy_button = QPushButton("Privacy now")
        self.privacy_button.setObjectName("privacy")
        self.privacy_button.clicked.connect(self.lock_privacy)
        self.resume_button = QPushButton("Resume")
        self.resume_button.clicked.connect(self.resume)
        self.shortcut_label = label("Ctrl + Shift + Space locks privacy", "hint")
        scroll.setWidget(panel)
        right = QVBoxLayout()
        right.addWidget(scroll, 1)
        quick_actions = QHBoxLayout()
        quick_actions.addWidget(self.privacy_button, 1)
        quick_actions.addWidget(self.resume_button)
        right.addLayout(quick_actions)
        right.addWidget(self.shortcut_label)
        content.addLayout(right)
        outer.addLayout(content, 1)
        outer.addWidget(label("ON YOUR DEVICE    /    No uploads. No recording.    /    Select yourself again after leaving the frame.", "hint"))
        for control in (self.look, self.others, self.manual, self.mirror, self.virtual):
            control.toggled.connect(self.update_settings)
        self.angle.valueChanged.connect(self.update_settings)
        self.strength.valueChanged.connect(self.update_settings)
        self.effect.currentTextChanged.connect(self.update_settings)
        self.camera.currentIndexChanged.connect(self.update_settings)
        self.update_settings()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(33)
        self.hotkey = GlobalHotkey(self.lock_privacy) if persist else None
        if self.hotkey:
            QApplication.instance().installNativeEventFilter(self.hotkey)
            if not self.hotkey.registered:
                self.shortcut_label.setText("Global shortcut unavailable · use Privacy now")
        self.tray = None
        if persist and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self.windowIcon(), self)
            self.tray.setToolTip("CBlur · camera privacy")
            menu = QMenu(self)
            for title, callback in (("Show CBlur", self.showNormal), ("Privacy now", self.lock_privacy),
                                    ("Resume", self.resume), ("Quit", self.close)):
                action = QAction(title, self)
                action.triggered.connect(callback)
                menu.addAction(action)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(lambda reason: self.showNormal() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
            self.tray.show()

    def load_settings(self):
        try:
            data = json.loads(self.settings_path.read_text()) if self.persist else {}
            allowed = {f.name for f in fields(Settings)}
            defaults = Settings()
            values = {k: v for k, v in data.items() if k in allowed and type(v) is type(getattr(defaults, k))}
            result = Settings(**values)
            # Apply the more sensitive setting once to existing installations.
            # Subsequent launches preserve any angle chosen on the new slider.
            if data.get("sensitivity_revision", 0) < 1:
                result.turn_angle = min(20, result.turn_angle)
            result.sensitivity_revision = 1
            result.turn_angle = min(70, max(10, result.turn_angle))
            result.strength = min(100, max(30, result.strength))
            result.camera_id = min(5, max(0, result.camera_id))
            result.turn_delay = .4
            result.resume_delay = .65
            if result.style not in ("Blur", "Solid cover", "Be right back"):
                result.style = "Blur"
            result.virtual_camera = False
            return result
        except (OSError, ValueError, TypeError, AttributeError):
            return Settings()

    def update_settings(self, *_):
        self.settings.look_away = self.look.isChecked()
        self.settings.hide_others = self.others.isChecked()
        self.settings.manual_resume = self.manual.isChecked()
        self.settings.turn_angle = self.angle.value()
        self.settings.strength = self.strength.value()
        self.settings.style = self.effect.currentText()
        self.settings.mirror = self.mirror.isChecked()
        self.settings.virtual_camera = self.virtual.isChecked()
        self.settings.camera_id = self.camera.currentData()
        self.preview.mirror = self.settings.mirror
        self.angle_label.setText(f"Turn angle   {self.settings.turn_angle}°")
        self.strength_label.setText(f"Blur strength   {self.settings.strength}%")
        self.angle.setEnabled(self.settings.look_away)
        self.strength.setEnabled(self.settings.style == "Blur")
        self.send("settings", self.settings)
        if self.persist:
            try:
                self.settings_path.parent.mkdir(parents=True, exist_ok=True)
                temp = self.settings_path.with_suffix(".tmp")
                temp.write_text(json.dumps(asdict(self.settings), indent=2))
                temp.replace(self.settings_path)
            except OSError:
                self.notice.setText("Preferences could not be saved; this session still works.")

    def send(self, command, value=None):
        if self.worker and self.worker.isRunning():
            self.worker.command(command, value)

    def toggle_camera(self):
        if self.worker and self.worker.isRunning():
            self.emergency.set()
            self.worker.stop()
            self.start_button.setEnabled(False)
            self.start_button.setText("Stopping…")
            return
        self.emergency.clear()
        self.last_stamp = 0
        self.worker = CameraWorker(self.settings, self.emergency, self.demo)
        self.worker.notice.connect(self.notice.setText)
        self.worker.output_notice.connect(self.output_status.setText)
        self.worker.finished.connect(self.camera_stopped)
        self.worker.start()
        self.camera.setEnabled(False)
        self.start_button.setText("Stop camera")
        self.status.setText("Starting protected…")

    def camera_stopped(self):
        self.camera.setEnabled(True)
        self.start_button.setEnabled(True)
        self.start_button.setText("Start demo" if self.demo else "Start camera")
        self.status.setText("Camera is off")
        self.preview.show_frame(safe_frame(message="Camera stopped"))
        self.output_status.setText("Virtual camera stopped")
        self.metrics.setText("No video is being captured.")

    def lock_privacy(self):
        self.emergency.set()
        self.preview.show_frame(safe_frame(message="Privacy locked"))
        self.status.setText("Privacy locked")

    def resume(self):
        self.emergency.clear()
        self.send("resume")

    def refresh(self):
        if not self.worker or not self.worker.isRunning():
            return
        value = self.worker.snapshot()
        if value is None or time.monotonic()-value[0] > .5:
            self.preview.show_frame(safe_frame())
            self.status.setText("Protected · waiting for camera")
            return
        stamp, frame, people, decision, fps, latency = value
        if self.emergency.is_set():
            self.preview.show_frame(safe_frame(message="Privacy locked"))
            self.status.setText("Privacy locked")
            return
        if stamp == self.last_stamp:
            return
        self.last_stamp = stamp
        self.preview.show_frame(frame, people, decision.selected)
        self.status.setText(decision.reason)
        yaw = f"  ·  head turn {abs(decision.yaw):.0f}°" if decision.yaw is not None else ""
        self.metrics.setText(f"1280 × 720  ·  {fps:.0f} processed fps  ·  {latency:.0f} ms processing{yaw}")

    def show_help(self):
        QMessageBox.information(self, "Use CBlur in your call",
            "1. Install OBS Studio from obsproject.com (includes its virtual camera).\n"
            "2. Start CBlur's camera and click your outline while facing forward.\n"
            "3. Enable virtual camera here. Keep OBS's own virtual output stopped.\n"
            "4. Choose OBS Virtual Camera in your meeting app, not your physical webcam.\n\n"
            "CBlur sends only the protected image. Outlines and status labels stay local. "
            "The local preview can be mirrored; the outgoing image is not mirrored.\n\n"
            "Detection can miss people, especially in low light or at the edge of the frame. "
            "Use Privacy now for a solid cover whenever you need certainty. "
            "This app does not mute your microphone.")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.emergency.set()
            self.worker.stop()
            self.notice.setText("Stopping camera safely…")
            self.worker.finished.connect(self.close)
            event.ignore()
            return
        if self.hotkey:
            QApplication.instance().removeNativeEventFilter(self.hotkey)
            self.hotkey.close()
        if self.tray:
            self.tray.hide()
        event.accept()
