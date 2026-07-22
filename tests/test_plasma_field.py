import math

import pytest

from propeller_vision.plasma import (
    IDLE_SATURATION,
    IDLE_VALUE,
    RIPPLE_REACH,
    Glow,
    PlasmaClock,
    base_field_value,
    blend_hue,
    clock_is_running,
    pitch_source,
    pixel_hsv,
    render_pixel,
    render_plasma_frame,
    ripple_distance,
    ripple_wave,
    ripple_weight,
    track_hue,
    update_plasma_clock,
)


def test_base_field_value_is_deterministic_for_given_inputs() -> None:
    assert base_field_value(x=10, y=5, t=1.5) == base_field_value(x=10, y=5, t=1.5)


def test_pitch_source_places_low_pitch_at_left_and_high_pitch_at_right() -> None:
    low_x, _ = pitch_source(pitch=0, cols=100, lines=20)
    high_x, _ = pitch_source(pitch=127, cols=100, lines=20)

    assert low_x == 0
    assert high_x == 99


def test_pitch_source_y_is_fixed_mid_row() -> None:
    _, y = pitch_source(pitch=60, cols=100, lines=20)

    assert y == 10.0


def test_ripple_distance_is_zero_at_the_pitch_source() -> None:
    x, y = pitch_source(pitch=60, cols=100, lines=20)

    assert ripple_distance(pitch=60, x=x, y=y, cols=100, lines=20) == 0.0


def test_ripple_wave_scales_linearly_with_intensity() -> None:
    single = ripple_wave(pitch=60, x=50, y=10, cols=100, lines=20, t=0.7, intensity=1.0)
    doubled = ripple_wave(pitch=60, x=50, y=10, cols=100, lines=20, t=0.7, intensity=2.0)

    assert doubled == single * 2


def test_ripple_weight_is_full_intensity_at_the_source() -> None:
    x, y = pitch_source(pitch=60, cols=100, lines=20)

    assert ripple_weight(pitch=60, x=x, y=y, cols=100, lines=20, intensity=0.7) == 0.7


def test_ripple_weight_fades_to_zero_beyond_reach() -> None:
    x, y = pitch_source(pitch=60, cols=100, lines=20)

    weight = ripple_weight(pitch=60, x=x + RIPPLE_REACH + 1, y=y, cols=100, lines=20, intensity=1.0)

    assert weight == 0.0


def test_track_hue_is_stable_for_the_same_track() -> None:
    assert track_hue(3) == track_hue(3)


def test_track_hue_differs_across_tracks() -> None:
    assert track_hue(0) != track_hue(1)
    assert track_hue(1) != track_hue(2)


def test_blend_hue_at_zero_weight_stays_at_base_hue() -> None:
    assert blend_hue(base_hue=0.2, target_hue=0.9, weight=0.0) == 0.2


def test_blend_hue_at_full_weight_reaches_target_hue() -> None:
    assert blend_hue(base_hue=0.2, target_hue=0.9, weight=1.0) == pytest.approx(0.9)


def test_blend_hue_takes_the_shortest_path_around_the_circle() -> None:
    # 0.05 -> 0.95 is a distance of 0.1 going backward through 0, not 0.9 forward.
    result = blend_hue(base_hue=0.05, target_hue=0.95, weight=1.0)

    assert math.isclose(result, 0.95, abs_tol=1e-9)


def test_pixel_hsv_at_zero_weight_is_the_idle_baseline() -> None:
    hue, saturation, value = pixel_hsv(base_hue=0.3, best_track_hue=0.7, weight=0.0)

    assert hue == 0.3
    assert saturation == IDLE_SATURATION
    assert value == IDLE_VALUE


def test_pixel_hsv_at_full_weight_reaches_full_brightness_and_track_hue() -> None:
    hue, saturation, value = pixel_hsv(base_hue=0.3, best_track_hue=0.7, weight=1.0)

    assert hue == pytest.approx(0.7)
    assert saturation == 1.0
    assert value == 1.0


def test_render_pixel_returns_rgb_bytes() -> None:
    r, g, b = render_pixel(x=5, y=5, cols=50, lines=20, t=1.0, glows=[], now=1.0)

    for channel in (r, g, b):
        assert 0 <= channel <= 255


def test_render_pixel_is_brighter_near_an_active_glow_than_far_away() -> None:
    glow = Glow(track_index=0, pitch=64, peak_intensity=1.0, deactivated_at=None)
    x, y = pitch_source(pitch=64, cols=100, lines=20)

    near = render_pixel(x=round(x), y=round(y), cols=100, lines=20, t=0.0, glows=[glow], now=0.0)
    far = render_pixel(x=0, y=0, cols=100, lines=20, t=0.0, glows=[glow], now=0.0)

    assert near != far
    assert sum(near) > sum(far)


def test_render_pixel_ignores_a_fully_decayed_glow() -> None:
    glow = Glow(track_index=0, pitch=64, peak_intensity=1.0, deactivated_at=0.0)
    x, y = pitch_source(pitch=64, cols=100, lines=20)

    with_decayed_glow = render_pixel(x=round(x), y=round(y), cols=100, lines=20, t=0.0, glows=[glow], now=10.0)
    with_no_glow = render_pixel(x=round(x), y=round(y), cols=100, lines=20, t=0.0, glows=[], now=10.0)

    assert with_decayed_glow == with_no_glow


def test_render_plasma_frame_has_one_styled_cell_per_grid_position() -> None:
    frame = render_plasma_frame(cols=5, lines=3, t=0.0, glows={}, now=0.0)

    # one character per cell, plus a newline between each row
    assert len(frame.plain) == 5 * 3 + (3 - 1)
    assert frame.plain.count("\n") == 2


def test_clock_is_running_when_status_reports_running() -> None:
    assert clock_is_running({"clock_state": "running"}) is True


def test_clock_is_running_is_false_when_paused() -> None:
    assert clock_is_running({"clock_state": "paused"}) is False


def test_clock_is_running_is_false_when_stopped() -> None:
    assert clock_is_running({"clock_state": "stopped"}) is False


def test_clock_is_running_defaults_true_when_clock_state_missing() -> None:
    assert clock_is_running({"mode": "standalone"}) is True


def test_clock_is_running_defaults_true_when_status_is_none() -> None:
    assert clock_is_running(None) is True


def test_update_plasma_clock_stays_running_while_running() -> None:
    clock = PlasmaClock(running=True, paused_since=None, paused_total=0.0)

    result = update_plasma_clock(clock, running=True, now=10.0)

    assert result == PlasmaClock(running=True, paused_since=None, paused_total=0.0)


def test_update_plasma_clock_records_when_a_pause_begins() -> None:
    clock = PlasmaClock(running=True, paused_since=None, paused_total=0.0)

    result = update_plasma_clock(clock, running=False, now=10.0)

    assert result == PlasmaClock(running=False, paused_since=10.0, paused_total=0.0)


def test_update_plasma_clock_accumulates_paused_time_on_resume() -> None:
    clock = PlasmaClock(running=False, paused_since=10.0, paused_total=0.0)

    result = update_plasma_clock(clock, running=True, now=13.5)

    assert result == PlasmaClock(running=True, paused_since=None, paused_total=3.5)


def test_update_plasma_clock_keeps_accumulating_across_multiple_pauses() -> None:
    clock = PlasmaClock(running=False, paused_since=20.0, paused_total=3.5)

    result = update_plasma_clock(clock, running=True, now=21.0)

    assert result == PlasmaClock(running=True, paused_since=None, paused_total=4.5)
