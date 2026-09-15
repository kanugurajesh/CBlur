# CBlur

CBlur is a Windows desktop app that protects your webcam locally. It can blur the full frame when you turn your head, protect the frame when you leave, and hide additional people who enter the camera view.

## Quick start

1. Install Python 3.11 (64-bit), then run `setup.ps1` from PowerShell. This creates `.venv`, installs dependencies, and downloads the two pinned MediaPipe models into `models/`.
2. Launch with **Launch CBlur.cmd**, or run `.\venv\Scripts\python.exe main.py`.
3. Start the camera, face forward, and click your outline. This calibrates your normal head direction for the session.
4. Adjust **Turn angle**. The updated default is 20 degrees, and the slider supports 10–70 degrees. Lower values blur after smaller turns.

The first launch after version 0.1.1 lowers an old saved threshold above 20 degrees to 20 degrees. Later changes are saved normally. Other preferences are preserved.

The camera feed stays protected until you select yourself. If tracking is lost, people overlap, or the app cannot safely identify your selected track, it protects the frame and requires reselection.

## Controls

- **Blur when looking away**: optional full-frame privacy based on head rotation. Turn it off if you want profile views to remain clear.
- **Turn angle**: 10–70 degrees relative to your calibrated forward direction. Activation requires 0.4 seconds of sustained rotation; recovery is deliberately slower to prevent flicker.
- **Hide other people**: hides every additional detected person while leaving your selected track visible.
- **Hold privacy until I resume**: keeps the frame protected after a look-away event until you press Resume.
- **Blur / Solid cover / Be right back**: choose the privacy appearance.
- **Privacy now**: immediately replaces the whole output with a solid cover.
- **Ctrl + Shift + Space**: global emergency privacy shortcut when the app is running.
- **Mirror local preview**: mirrors only the local preview. The outgoing virtual-camera feed is not mirrored by CBlur.

## Use in a meeting app

CBlur sends protected frames through OBS Virtual Camera.

1. Install OBS Studio. Its virtual-camera component is required; CBlur does not install a camera driver.
2. Keep OBS’s own virtual-camera output stopped.
3. Start CBlur, calibrate yourself, and enable **Enable virtual camera**.
4. In Zoom, Teams, Google Meet, Discord, or another call app, choose **OBS Virtual Camera** instead of the physical webcam.

The outgoing feed contains the protected image only. CBlur does not capture audio, record video, upload frames, or require an account. Video protection does not mute your microphone.

## Privacy and limits

Processing is local and offline after setup. Calibration and temporary appearance signatures live in memory; no biometric identity is stored. Blurring can still reveal colors and movement, so use **Solid cover** or **Privacy now** when stronger concealment is needed.

Person detection can miss someone in low light, at the edge of the frame, behind an object, or during rapid movement. The app uses position and appearance continuity rather than biometric recognition. It protects the frame when tracking is uncertain, but live hardware testing is still important.

## Development and tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/check_vision.py
.\.venv\Scripts\python.exe main.py --demo
.\.venv\Scripts\python.exe main.py --diagnostics artifacts\diagnostics.json --camera-check
```

The test suite covers privacy transitions, low-angle head turns in both directions, recovery timing, absence, ambiguous tracking, bystander masks, emergency overrides, stale output, preference migration, and the demo UI. `check_vision.py` runs the actual models against a bundled public sample image and verifies that a selected person stays clear while a second person is masked.

## Build a portable executable

```powershell
.\.venv\Scripts\python.exe -m PyInstaller CBlur.spec --noconfirm
.\.venv\Scripts\python.exe scripts/package_docs.py
```

The executable is written to `dist\CBlur\CBlur.exe`. The tested 0.1.1 build is in `releases\0.1.1\CBlur\CBlur.exe`. Keep the complete folder together; Python is not required to run the packaged app.

## Project layout

- `cblur/core.py`: privacy state machine and owner continuity.
- `cblur/vision.py`: face landmarks, head direction, person detection, and temporary appearance signatures.
- `cblur/render.py`: full-frame and bystander rendering.
- `cblur/worker.py`: webcam worker, demo scenes, virtual-camera output, and stale-frame watchdog.
- `cblur/ui.py`: desktop controls, saved preferences, tray actions, and emergency shortcut.
- `cblur/diagnostics.py`: explicit local diagnostics; it saves counts and timings, not camera frames.
- `scripts/download_models.py`: downloads and verifies the pinned model files.

See [THIRD_PARTY.md](THIRD_PARTY.md) for dependency and model notices, and [VALIDATION.md](VALIDATION.md) for the verification record.
