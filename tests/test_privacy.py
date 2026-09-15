from dataclasses import replace
import threading
import pytest
import numpy as np
from cblur.core import Box, Person, PrivacyPolicy, Settings, Decision
from cblur.render import render, safe_frame
from cblur.worker import VirtualOutput

OWNER = Person(Box(.1, .1, .3, .8), 0)
VISITOR = Person(Box(.65, .1, .3, .8), 0)


def selected():
    policy = PrivacyPolicy()
    assert policy.select([OWNER], OWNER.box.center)
    return policy


def test_startup_is_protected_even_when_people_are_visible():
    assert PrivacyPolicy().update([OWNER], 0, Settings()).protected


def test_click_requires_visible_face_and_unambiguous_person():
    p = PrivacyPolicy()
    assert not p.select([replace(OWNER, yaw=None)], OWNER.box.center)
    assert not p.select([OWNER, OWNER], OWNER.box.center)
    assert not p.select([OWNER], (.99, .99))


def test_forward_is_clear_and_calibrated_relative_to_normal_position():
    p = PrivacyPolicy()
    turned_seat = replace(OWNER, yaw=25)
    assert p.select([turned_seat], OWNER.box.center)
    d = p.update([turned_seat], 0, Settings())
    assert not d.protected and d.yaw == 0


def test_side_turn_requires_dwell_and_return_requires_stability():
    p, settings = selected(), Settings()
    turned = replace(OWNER, yaw=55)
    assert not p.update([turned], 0, settings).protected
    assert p.update([turned], .41, settings).protected
    assert p.update([OWNER], .5, settings).protected
    assert p.update([OWNER], 1., settings).protected
    assert not p.update([OWNER], 1.2, settings).protected


def test_quick_glance_does_not_trigger():
    p = selected()
    p.update([replace(OWNER, yaw=55)], 0, Settings())
    assert not p.update([OWNER], .2, Settings()).protected


@pytest.mark.parametrize("direction", [-1, 1])
@pytest.mark.parametrize("angle", [10, 20])
def test_small_turns_trigger_and_can_recover_at_low_thresholds(direction, angle):
    p, settings = selected(), Settings(turn_angle=angle)
    turned = replace(OWNER, yaw=direction * (angle + 1))
    assert not p.update([turned], 0, settings).protected
    assert p.update([turned], .41, settings).protected
    assert p.update([OWNER], .5, settings).protected
    assert p.update([OWNER], 1., settings).protected
    assert not p.update([OWNER], 1.2, settings).protected


def test_turn_toggle_does_not_disable_absence_or_bystanders():
    p, s = selected(), Settings(look_away=False)
    d = p.update([replace(OWNER, yaw=80), VISITOR], 0, s)
    assert not d.protected and d.regions
    assert p.update([VISITOR], .1, s).protected


def test_profile_with_toggle_off_keeps_continuous_body_track():
    d = selected().update([replace(OWNER, yaw=None)], 0, Settings(look_away=False))
    assert not d.protected


def test_missing_face_with_toggle_on_protects():
    assert selected().update([replace(OWNER, yaw=None)], 0, Settings()).protected


def test_departure_never_adopts_visitor_and_return_needs_selection():
    p = selected()
    assert p.update([], 0, Settings()).protected
    assert p.update([VISITOR], .1, Settings()).protected
    assert p.update([OWNER], .2, Settings()).protected
    assert p.select([OWNER], OWNER.box.center)
    assert not p.update([OWNER], .3, Settings()).protected


def test_overlapping_people_protect_and_release_owner():
    p = selected()
    other = Person(Box(.2, .1, .3, .8), 0)
    assert p.update([OWNER, other], 0, Settings()).protected
    assert p.owner is None


def test_sudden_appearance_change_releases_owner():
    p = PrivacyPolicy()
    p.select([replace(OWNER, appearance=(1., 0.))], OWNER.box.center)
    assert p.update([replace(OWNER, appearance=(0., 1.))], 0, Settings()).protected


def test_long_tracking_gap_requires_reselection():
    p = selected()
    p.update([OWNER], 0, Settings())
    assert p.update([OWNER], 1, Settings()).protected


def test_manual_hold_after_look_away():
    p, s = selected(), Settings(manual_resume=True)
    p.update([replace(OWNER, yaw=60)], 0, s)
    p.update([replace(OWNER, yaw=60)], .5, s)
    p.update([OWNER], .6, s)
    p.update([OWNER], 1.1, s)
    assert p.update([OWNER], 1.3, s).protected
    p.resume_latched = False
    assert not p.update([OWNER], 1.4, s).protected


def test_bystander_mask_survives_a_brief_missed_detection():
    p = selected()
    assert p.update([OWNER, VISITOR], 0, Settings()).regions
    assert p.update([OWNER], .2, Settings()).regions
    assert not p.update([OWNER], .5, Settings()).regions


def test_all_other_people_are_hidden():
    p = selected()
    third = Person(Box(.48, .2, .08, .3), None)
    d = p.update([OWNER, VISITOR, third], 0, Settings())
    assert not d.protected and len(d.regions) == 2


def test_bystander_toggle_clears_masks():
    p = selected()
    p.update([OWNER, VISITOR], 0, Settings())
    assert not p.update([OWNER, VISITOR], .1, Settings(hide_others=False)).regions


def test_emergency_overrides_all_settings():
    p = selected()
    d = p.update([OWNER], 0, Settings(look_away=False, hide_others=False), emergency=True)
    assert d.protected and "locked" in d.reason


def test_renderer_preserves_owner_pixels_and_covers_other_region():
    frame = np.random.default_rng(4).integers(0, 256, (100, 100, 3), dtype=np.uint8)
    original = frame.copy()
    d = Decision(False, "Other people hidden", [Box(.6, 0, .4, 1)])
    result = render(frame, d, Settings(style="Solid cover"))
    assert np.array_equal(result[:, :50], original[:, :50])
    assert not np.array_equal(result[:, 65:], original[:, 65:])
    assert np.array_equal(frame, original)


def test_emergency_output_contains_no_input_pixels():
    frame = np.full((720, 1280, 3), 255, np.uint8)
    assert np.array_equal(render(frame, Decision(False, ""), Settings(), True),
                          safe_frame(message="Privacy locked"))


def test_virtual_watchdog_covers_stale_frame_and_emergency():
    emergency = threading.Event()
    output = VirtualOutput(emergency, lambda _: None)
    assert np.array_equal(output.output_frame(0), safe_frame())
    frame = np.full((720, 1280, 3), 255, np.uint8)
    output.latest = (10, frame)
    assert np.array_equal(output.output_frame(10.1), frame)
    assert np.array_equal(output.output_frame(10.6), safe_frame())
    emergency.set()
    assert np.array_equal(output.output_frame(10.1), safe_frame(message="Privacy locked"))
