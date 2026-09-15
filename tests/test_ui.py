import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import time
import json
from PySide6.QtWidgets import QApplication
from cblur.ui import MainWindow


def test_saved_angle_migrates_once_and_preserves_later_choices(tmp_path):
    class SavedSettings:
        persist = True
        settings_path = tmp_path / "settings.json"

    saved = SavedSettings()
    saved.settings_path.write_text(json.dumps({"turn_angle": 40, "strength": 57}))
    settings = MainWindow.load_settings(saved)
    assert settings.turn_angle == 20
    assert settings.strength == 57
    assert settings.sensitivity_revision == 1
    saved.settings_path.write_text(json.dumps({"turn_angle": 40, "sensitivity_revision": 1}))
    assert MainWindow.load_settings(saved).turn_angle == 40
    saved.settings_path.write_text(json.dumps({"turn_angle": 10, "sensitivity_revision": 1}))
    assert MainWindow.load_settings(saved).turn_angle == 10


def test_demo_ui_selection_visitor_toggle_and_shutdown():
    app = QApplication.instance() or QApplication([])
    window = MainWindow(demo=True, persist=False)
    window.show()
    window.toggle_camera()
    def pump_until(predicate, timeout=5):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            app.processEvents()
            if predicate():
                return
            time.sleep(.02)
        raise AssertionError("UI condition timed out")
    try:
        pump_until(lambda: window.worker.snapshot() is not None)
        window.send("select", (600/1280, .5))
        pump_until(lambda: not window.worker.snapshot()[3].protected)
        window.scenario.setCurrentText("Visitor")
        pump_until(lambda: bool(window.worker.snapshot()[3].regions))
        window.look.setChecked(False)
        window.scenario.setCurrentText("Looking away")
        pump_until(lambda: window.worker.snapshot()[3].yaw == 60)
        assert not window.worker.snapshot()[3].protected
        window.lock_privacy()
        assert window.emergency.is_set()
        window.resume()
        assert not window.emergency.is_set()
        window.scenario.setCurrentText("Away")
        pump_until(lambda: window.worker.snapshot()[3].protected)
    finally:
        window.worker.stop()
        assert window.worker.wait(5000)
        app.processEvents()
        window.close()
