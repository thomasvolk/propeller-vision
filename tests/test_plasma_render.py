from propeller_vision.plasma import PITCH_RANGE, Glow, render_plasma_row, track_color


def test_render_plasma_row_has_one_slot_per_midi_pitch() -> None:
    row = render_plasma_row({}, now=0.0)

    assert len(row) == PITCH_RANGE


def test_render_plasma_row_is_blank_with_no_glows() -> None:
    row = render_plasma_row({}, now=0.0)

    assert all(cell is None for cell in row)


def test_render_plasma_row_places_a_glow_at_its_pitch_column() -> None:
    glows = {(0, 100, 60): Glow(track_index=0, pitch=60, peak_intensity=1.0, deactivated_at=None)}

    row = render_plasma_row(glows, now=0.0)

    assert row[60] == track_color(0, intensity=1.0)
    assert row[59] is None
    assert row[61] is None


def test_render_plasma_row_omits_fully_decayed_glows() -> None:
    glows = {(0, 100, 60): Glow(track_index=0, pitch=60, peak_intensity=1.0, deactivated_at=0.0)}

    row = render_plasma_row(glows, now=10.0)

    assert row[60] is None


def test_render_plasma_row_handles_multiple_simultaneous_pitches() -> None:
    glows = {
        (0, 0, 36): Glow(track_index=0, pitch=36, peak_intensity=1.0, deactivated_at=None),
        (1, 50, 72): Glow(track_index=1, pitch=72, peak_intensity=0.5, deactivated_at=None),
    }

    row = render_plasma_row(glows, now=0.0)

    assert row[36] == track_color(0, intensity=1.0)
    assert row[72] == track_color(1, intensity=0.5)
