"""Download Google's versioned MediaPipe models; no images leave this machine."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    "face_landmarker.task": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
    "efficientdet_lite0.tflite": "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/int8/1/efficientdet_lite0.tflite",
}


def main():
    folder = ROOT / "models"
    folder.mkdir(exist_ok=True)
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for name, url in MODELS.items():
        target = folder / name
        expected = manifest.get(name, {}).get("sha256")
        if target.exists() and expected and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            print(f"Verified {name}", flush=True)
            continue
        print(f"Downloading {name}…", flush=True)
        request = urllib.request.Request(url, headers={"User-Agent": "CBlur-Setup/0.1"})
        partial = target.with_suffix(target.suffix + ".part")
        try:
            with urllib.request.urlopen(request, timeout=120) as source, partial.open("wb") as out:
                while chunk := source.read(1024 * 1024):
                    out.write(chunk)
            digest = hashlib.sha256(partial.read_bytes()).hexdigest()
            if expected and digest != expected:
                raise RuntimeError(f"Checksum mismatch for {name}; refusing the download")
            if partial.stat().st_size < 100_000:
                raise RuntimeError(f"Incomplete model: {name}")
            partial.replace(target)
            manifest[name] = {"url": url, "sha256": digest, "bytes": target.stat().st_size}
        finally:
            partial.unlink(missing_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("Models ready. Camera processing works offline.", flush=True)


if __name__ == "__main__":
    main()
