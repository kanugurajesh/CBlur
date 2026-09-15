"""Privacy policy, independent of camera, inference and GUI."""
from dataclasses import dataclass, field
import math


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def center(self):
        return self.x + self.w / 2, self.y + self.h / 2

    def contains(self, x, y):
        return self.x <= x <= self.x + self.w and self.y <= y <= self.y + self.h

    def iou(self, other):
        ix = max(0., min(self.x + self.w, other.x + other.w) - max(self.x, other.x))
        iy = max(0., min(self.y + self.h, other.y + other.h) - max(self.y, other.y))
        intersection = ix * iy
        return intersection / max(1e-9, self.w * self.h + other.w * other.h - intersection)

    def expanded(self, margin=.12):
        x, y = max(0., self.x - self.w * margin), max(0., self.y - self.h * margin)
        return Box(x, y, min(1., self.x + self.w * (1 + margin)) - x,
                   min(1., self.y + self.h * (1 + margin)) - y)


@dataclass
class Person:
    box: Box
    yaw: float | None = None
    appearance: tuple[float, ...] = ()


@dataclass
class Settings:
    look_away: bool = True
    hide_others: bool = True
    turn_angle: int = 20
    sensitivity_revision: int = 1
    turn_delay: float = .4
    resume_delay: float = .65
    strength: int = 75
    style: str = "Blur"
    manual_resume: bool = False
    mirror: bool = True
    virtual_camera: bool = False
    camera_id: int = 0


@dataclass
class Decision:
    protected: bool
    reason: str
    regions: list[Box] = field(default_factory=list)
    selected: Box | None = None
    yaw: float | None = None


class PrivacyPolicy:
    def __init__(self):
        self.owner: Person | None = None
        self.baseline = 0.
        self.turned = False
        self.turn_since = None
        self.clear_since = None
        self.resume_latched = False
        self.last_time = None
        self.history: list[tuple[float, Box]] = []

    def select(self, people, point):
        candidates = [p for p in people if p.box.contains(*point)]
        # Overlapping tracks cannot be safely distinguished by a click.
        if len(candidates) != 1 or candidates[0].yaw is None:
            return False
        self.owner = candidates[0]
        self.baseline = self.owner.yaw
        self.turned = False
        self.turn_since = self.clear_since = None
        self.resume_latched = False
        return True

    def release(self):
        self.owner = None
        self.turned = False
        self.turn_since = self.clear_since = None

    @staticmethod
    def appearance_distance(a, b):
        if not a or not b:
            return 0.
        return math.sqrt(sum((math.sqrt(x) - math.sqrt(y)) ** 2 for x, y in zip(a, b)) / 2)

    def update(self, people, now, settings, emergency=False):
        stale = self.last_time is not None and now - self.last_time > .8
        self.last_time = now
        reason = None
        primary = None
        if stale:
            self.release()
        if self.owner is not None:
            ranked = sorted(((self.owner.box.iou(p.box), i) for i, p in enumerate(people)), reverse=True)
            if not ranked or ranked[0][0] < .30:
                self.release()
                reason = "You left the frame · select yourself to resume"
            elif len(ranked) > 1 and ranked[0][0] - ranked[1][0] < .18:
                self.release()
                reason = "People overlap · select yourself again"
            else:
                primary = ranked[0][1]
                person = people[primary]
                overlap = any(person.box.iou(p.box) > .20 for i, p in enumerate(people) if i != primary)
                changed = self.appearance_distance(self.owner.appearance, person.appearance) > .48
                if overlap or changed:
                    self.release()
                    primary = None
                    reason = "Tracking uncertain · select yourself again"
                else:
                    # Keep the original appearance reference to avoid gradual identity drift.
                    self.owner = Person(person.box, person.yaw, self.owner.appearance)

        if self.owner is None:
            reason = reason or "Select yourself to start"
        elif settings.look_away:
            yaw = self.owner.yaw
            if yaw is None:
                self.turned = True
                self.clear_since = None
            elif abs(yaw - self.baseline) >= settings.turn_angle:
                self.clear_since = None
                if self.turn_since is None:
                    self.turn_since = now
                if now - self.turn_since >= settings.turn_delay:
                    self.turned = True
            elif abs(yaw - self.baseline) < settings.turn_angle - min(10, settings.turn_angle * .35):
                self.turn_since = None
                if self.clear_since is None:
                    self.clear_since = now
                if now - self.clear_since >= settings.resume_delay:
                    self.turned = False
            else:
                self.turn_since = self.clear_since = None
            if self.turned:
                reason = "Looking away" if yaw is not None else "Face direction unavailable"
                if settings.manual_resume:
                    self.resume_latched = True
        else:
            self.turned = False
            self.turn_since = self.clear_since = None

        if not settings.manual_resume:
            self.resume_latched = False
        if self.resume_latched:
            reason = reason or "Privacy held · press Resume"
        if emergency:
            reason = "Privacy locked · press Resume"

        if settings.hide_others:
            regions = [p.box.expanded() for i, p in enumerate(people) if i != primary]
            # Keep recent masks briefly so one missed detection does not expose a bystander.
            self.history = [(t, b) for t, b in self.history if now - t < .45]
            self.history.extend((now, b) for b in regions)
            regions = [b for _, b in self.history]
        else:
            regions = []
            self.history.clear()
        return Decision(bool(reason), reason or ("Other people hidden" if regions else "You're in view"),
                        regions, self.owner.box if self.owner else None,
                        self.owner.yaw - self.baseline if self.owner and self.owner.yaw is not None else None)
