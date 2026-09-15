# CBlur validation — 2026-09-15

## Passed

- Dependency compatibility: `python -m pip check` reports no broken requirements.
- Automated tests: **26 passed** after the 0.1.1 sensitivity update. Covers rule transitions, timing, owner loss, ambiguity, bystander masks, rendering, watchdog, and interactive demo controls. Added both-direction checks at 10° and 20°, recovery at low thresholds, and migration of saved preferences.
- Both downloaded model files match their pinned SHA-256 checksums.
- Actual MediaPipe inference: blank frame produces zero people.
- Real-image integration: the bundled Matplotlib sample portrait yields one person and a face; a duplicated two-person scene yields two people and two faces. The selected person's test region stays unchanged and the visitor's region is masked.
- The Windows executable runs independently of the project Python environment, loads both models, and produces a protected-preview screenshot.
- Source and packaged interface screenshots visually reviewed; emergency buttons remain outside the scrolling settings panel.
- OBS Studio 32.2.1 installed successfully. The packaged app opened **OBS Virtual Camera** and sent a solid setup frame through the real backend.
- Final packaged check outside the sandbox: both models loaded, zero detections on a blank frame, **74.0 ms** average warm inference in that run.

## Performance observations

In a same-process warm detector benchmark, EfficientDet-Lite0 float32 averaged **104.2 ms** and int8 averaged **65.1 ms**. The build uses int8. Real two-person inference measured **134.1 ms** in one sample run. Load and sandbox conditions affect these measurements; they are not a sustained webcam frame-rate guarantee. New frames are analyzed before output, and the virtual camera repeats the latest processed frame at 30 fps.

## Hardware limits

Camera 0 did not open using DirectShow or Media Foundation, including outside the sandbox. No physical-camera video was captured or saved. Live head turns, departure/return, fast crossings, low light, and meeting-app compatibility still need a webcam-equipped target machine.

Diagnostic artifacts are stored under `artifacts/`. They contain counts, timing, a synthetic UI screenshot, and a processed public sample image; no user-camera images.
