# Third-party components

Keep component licenses with redistributed builds. PyInstaller collects package license metadata where supplied; this list identifies the principal dependencies and upstream sources.

| Component | Upstream / license information |
| --- | --- |
| PySide6 / Qt | https://doc.qt.io/qtforpython-6/licenses.html — LGPLv3/GPLv3 or commercial; dynamically linked in this build. |
| OpenCV | https://github.com/opencv/opencv/blob/4.x/LICENSE — Apache 2.0 for current versions. |
| NumPy | https://github.com/numpy/numpy/blob/main/LICENSE.txt — BSD 3-Clause and bundled-component notices. |
| MediaPipe | https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE — Apache 2.0. |
| pyvirtualcam | https://github.com/letmaik/pyvirtualcam — GPLv2; see upstream LICENSE. |
| Matplotlib | https://matplotlib.org/stable/project/license.html — Matplotlib license and bundled notices; imported by MediaPipe. |
| OBS Studio | https://github.com/obsproject/obs-studio — GPLv2 or later; installed separately. |

## Models

Google's versioned MediaPipe Face Landmarker (float16, v1) and EfficientDet-Lite0 (int8, v1) are downloaded from the official `mediapipe-models` Google Cloud Storage bucket. Exact URLs, sizes, and SHA-256 digests are in `models/manifest.json`.

- https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker
- https://ai.google.dev/edge/mediapipe/solutions/vision/object_detector

EfficientDet uses COCO person-category detection. It does not identify individuals. No model is trained on user images by this application.
