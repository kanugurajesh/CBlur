"""Exercise real inference with Matplotlib's bundled public sample portrait."""
from pathlib import Path
import sys
import json
import time
import cv2
import numpy as np
import matplotlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cblur.vision import Vision
from cblur.core import PrivacyPolicy, Settings
from cblur.render import render


def main():
    sample = Path(matplotlib.get_data_path()) / "sample_data" / "grace_hopper.jpg"
    portrait = cv2.imread(str(sample))
    assert portrait is not None, "Matplotlib sample portrait is missing"
    portrait = cv2.resize(portrait, (440, 600))
    one = np.full((720, 1280, 3), 25, np.uint8)
    one[60:660, 70:510] = portrait
    two = one.copy()
    two[60:660, 770:1210] = portrait
    vision = Vision()
    try:
        first = vision.analyze(one, 1)
        assert len(first) == 1 and first[0].yaw is not None, f"Expected one selectable person, got {first}"
        policy = PrivacyPolicy()
        assert policy.select(first, first[0].box.center)
        assert not policy.update(first, 0, Settings()).protected
        started = time.perf_counter()
        second = vision.analyze(two, 100)
        inference_ms = (time.perf_counter()-started)*1000
        decision = policy.update(second, .1, Settings())
        assert len(second) == 2, f"Expected two people, got {len(second)}"
        assert not decision.protected and decision.regions, decision
        result = render(two, decision, Settings())
        assert np.array_equal(result[100:500, 100:400], two[100:500, 100:400]), "Owner should remain clear"
        assert not np.array_equal(result[100:500, 800:1100], two[100:500, 800:1100]), "Visitor should be hidden"
        artifacts = ROOT / "artifacts"
        artifacts.mkdir(exist_ok=True)
        cv2.imwrite(str(artifacts / "vision-protected-sample.jpg"), result)
        report = {"sample": "Matplotlib bundled grace_hopper.jpg; duplicated for two-person scene",
                  "single_person_detected": len(first), "two_people_detected": len(second),
                  "faces_detected": sum(p.yaw is not None for p in second),
                  "owner_preserved": True, "visitor_masked": True,
                  "inference_ms": round(inference_ms, 1)}
        (artifacts / "vision-integration.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    finally:
        vision.close()


if __name__ == "__main__":
    main()
