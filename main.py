import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="CBlur · local camera privacy")
    parser.add_argument("--demo", action="store_true", help="Use an illustrated scene instead of the webcam")
    parser.add_argument("--screenshot", help="Save a demo UI screenshot and exit without accessing the camera")
    parser.add_argument("--diagnostics", help="Write model and virtual-camera diagnostics to this JSON file, then exit")
    parser.add_argument("--camera-check", action="store_true", help="Also test the physical camera during diagnostics; no frames are saved")
    args = parser.parse_args()
    if args.diagnostics:
        from cblur.diagnostics import diagnose
        return diagnose(args.diagnostics, args.camera_check)
    if args.screenshot:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from cblur.ui import MainWindow, STYLE
    app = QApplication(sys.argv[:1])
    app.setApplicationName("CBlur")
    app.setOrganizationName("CBlur")
    # The offscreen Qt plugin does not discover Windows fonts on its own.
    if sys.platform == "win32":
        from pathlib import Path
        from PySide6.QtGui import QFontDatabase
        for name in ("segoeui.ttf", "seguisb.ttf", "segoeuib.ttf"):
            font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
            if font_path.exists():
                QFontDatabase.addApplicationFont(str(font_path))
    app.setStyleSheet(STYLE)
    window = MainWindow(demo=args.demo or bool(args.screenshot), persist=not bool(args.screenshot))
    window.show()
    if args.screenshot:
        from pathlib import Path
        from cblur.worker import demo_frame
        from cblur.core import PrivacyPolicy
        from cblur.render import render
        frame, people = demo_frame("Visitor")
        policy = PrivacyPolicy()
        policy.select(people, people[0].box.center)
        decision = policy.update(people, 0, window.settings)
        window.preview.show_frame(render(frame, decision, window.settings), people, decision.selected)
        window.status.setText("Other people hidden")
        window.metrics.setText("DEMO SCENE  ·  Local outlines are not sent to your call")
        window.notice.setText("You're selected. Other detected people are covered automatically.")
        def capture():
            Path(args.screenshot).parent.mkdir(parents=True, exist_ok=True)
            window.grab().save(args.screenshot)
            window.close()
        QTimer.singleShot(300, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
