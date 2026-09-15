import cv2
import numpy as np
from .core import Box, Decision, Settings


def cover(frame, box, settings):
    h, w = frame.shape[:2]
    x1, y1 = max(0, int(box.x * w)), max(0, int(box.y * h))
    x2, y2 = min(w, int((box.x + box.w) * w + 1)), min(h, int((box.y + box.h) * h + 1))
    if x2 <= x1 or y2 <= y1:
        return
    roi = frame[y1:y2, x1:x2]
    if settings.style != "Blur":
        roi[:] = (31, 25, 22)
        return
    # Downsample first: effective strong blur at modest CPU cost.
    scale = max(2, int(26 - settings.strength * .23))
    tiny = cv2.resize(roi, (scale, scale), interpolation=cv2.INTER_AREA)
    blurred = cv2.GaussianBlur(tiny, (5, 5), 0)
    roi[:] = cv2.resize(blurred, (x2 - x1, y2 - y1), interpolation=cv2.INTER_LINEAR)


def safe_frame(width=1280, height=720, message="Camera protected"):
    frame = np.full((height, width, 3), (31, 25, 22), np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    size = cv2.getTextSize(message, font, .9, 2)[0]
    cv2.putText(frame, message, ((width - size[0]) // 2, height // 2), font, .9, (220, 233, 229), 2, cv2.LINE_AA)
    return frame


def render(frame, decision: Decision, settings: Settings, emergency=False):
    result = frame.copy()
    if emergency:
        return safe_frame(frame.shape[1], frame.shape[0], "Privacy locked")
    if decision.protected:
        cover(result, Box(0, 0, 1, 1), settings)
        if settings.style == "Be right back":
            return safe_frame(frame.shape[1], frame.shape[0], "Be right back")
    else:
        # Union masks before rendering: overlapping regions must not repeatedly blur.
        mask = np.zeros(frame.shape[:2], np.uint8)
        h, w = mask.shape
        for b in decision.regions:
            cv2.rectangle(mask, (max(0, int(b.x*w)), max(0, int(b.y*h))),
                          (min(w-1, int((b.x+b.w)*w)), min(h-1, int((b.y+b.h)*h))), 255, -1)
        if mask.any():
            hidden = frame.copy()
            cover(hidden, Box(0, 0, 1, 1), settings)
            result[mask > 0] = hidden[mask > 0]
    return result
