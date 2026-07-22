import pytest

from propeller_vision.plasma import (
    DECAY_SECONDS,
    ActiveNote,
    Glow,
    glow_intensity,
    update_glow,
)


def test_update_glow_lights_up_a_newly_active_note() -> None:
    active = {(0, 100, 60): ActiveNote(track_index=0, pitch=60, velocity=127)}

    result = update_glow({}, active, now=10.0)

    assert result == {(0, 100, 60): Glow(track_index=0, pitch=60, peak_intensity=1.0, deactivated_at=None)}


def test_update_glow_scales_peak_intensity_from_velocity() -> None:
    active = {(0, 100, 60): ActiveNote(track_index=0, pitch=60, velocity=64)}

    result = update_glow({}, active, now=10.0)

    assert result[(0, 100, 60)].peak_intensity == pytest.approx(64 / 127)


def test_update_glow_keeps_a_still_active_note_lit_with_no_deactivation_time() -> None:
    previous = {(0, 100, 60): Glow(track_index=0, pitch=60, peak_intensity=1.0, deactivated_at=None)}
    active = {(0, 100, 60): ActiveNote(track_index=0, pitch=60, velocity=127)}

    result = update_glow(previous, active, now=10.05)

    assert result[(0, 100, 60)].deactivated_at is None


def test_update_glow_starts_decay_the_moment_a_note_goes_inactive() -> None:
    previous = {(0, 100, 60): Glow(track_index=0, pitch=60, peak_intensity=1.0, deactivated_at=None)}

    result = update_glow(previous, {}, now=10.0)

    assert result[(0, 100, 60)].deactivated_at == 10.0
    assert result[(0, 100, 60)].peak_intensity == 1.0


def test_update_glow_does_not_reset_deactivation_time_on_subsequent_cycles() -> None:
    previous = {(0, 100, 60): Glow(track_index=0, pitch=60, peak_intensity=1.0, deactivated_at=10.0)}

    result = update_glow(previous, {}, now=10.05)

    assert result[(0, 100, 60)].deactivated_at == 10.0


def test_update_glow_drops_a_note_once_fully_decayed() -> None:
    previous = {
        (0, 100, 60): Glow(track_index=0, pitch=60, peak_intensity=1.0, deactivated_at=10.0)
    }

    result = update_glow(previous, {}, now=10.0 + DECAY_SECONDS * 2)

    assert result == {}


def test_glow_intensity_is_full_while_active() -> None:
    glow = Glow(track_index=0, pitch=60, peak_intensity=0.8, deactivated_at=None)

    assert glow_intensity(glow, now=999.0) == pytest.approx(0.8)


def test_glow_intensity_decays_linearly_after_note_off() -> None:
    glow = Glow(track_index=0, pitch=60, peak_intensity=1.0, deactivated_at=10.0)

    halfway = glow_intensity(glow, now=10.0 + DECAY_SECONDS / 2)

    assert halfway == pytest.approx(0.5, abs=0.01)


def test_glow_intensity_never_goes_negative_past_full_decay() -> None:
    glow = Glow(track_index=0, pitch=60, peak_intensity=1.0, deactivated_at=10.0)

    assert glow_intensity(glow, now=10.0 + DECAY_SECONDS * 10) == 0.0
