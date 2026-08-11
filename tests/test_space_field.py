import pytest

from propeller_vision.space import (
    SCROLL_ROWS_PER_BEAT,
    Marker,
    lane_bounds,
    marker_glyph,
    marker_row,
    render_space_frame,
    ship_column,
    track_count,
    update_markers,
)


def test_track_count_is_zero_when_project_is_none() -> None:
    assert track_count(None) == 0


def test_track_count_is_zero_when_no_current_project() -> None:
    assert track_count({"pending": {"tracks": [{}]}}) == 0


def test_track_count_counts_tracks_in_current_project() -> None:
    project = {"current": {"tracks": [{}, {}, {}]}}

    assert track_count(project) == 3


def test_lane_bounds_splits_width_evenly() -> None:
    assert lane_bounds(track_index=0, lanes=2, cols=100) == (0, 50)
    assert lane_bounds(track_index=1, lanes=2, cols=100) == (50, 100)


def test_lane_bounds_treats_zero_lanes_as_one() -> None:
    assert lane_bounds(track_index=0, lanes=0, cols=100) == (0, 100)


def test_marker_glyph_scales_with_velocity() -> None:
    assert marker_glyph(10) == "."
    assert marker_glyph(60) == "o"
    assert marker_glyph(120) == "@"


def test_marker_row_advances_with_music_time() -> None:
    marker = Marker(track_index=0, velocity=100, spawned_at=1.0)

    assert marker_row(marker, music_time=1.0) == 0.0
    assert marker_row(marker, music_time=2.0) == pytest.approx(SCROLL_ROWS_PER_BEAT)


def test_update_markers_spawns_a_marker_for_a_newly_active_note() -> None:
    from propeller_vision.plasma import ActiveNote

    active = {(0, 0, 60): ActiveNote(track_index=0, pitch=60, velocity=100)}

    result = update_markers({}, active, music_time=5.0, lines=20)

    assert result == {(0, 0, 60): Marker(track_index=0, velocity=100, spawned_at=5.0)}


def test_update_markers_keeps_an_existing_marker_scrolling_after_note_off() -> None:
    previous = {(0, 0, 60): Marker(track_index=0, velocity=100, spawned_at=5.0)}

    result = update_markers(previous, {}, music_time=5.1, lines=20)

    assert result == previous


def test_update_markers_does_not_reset_spawn_time_while_still_active() -> None:
    from propeller_vision.plasma import ActiveNote

    previous = {(0, 0, 60): Marker(track_index=0, velocity=100, spawned_at=5.0)}
    active = {(0, 0, 60): ActiveNote(track_index=0, pitch=60, velocity=100)}

    result = update_markers(previous, active, music_time=5.5, lines=20)

    assert result[(0, 0, 60)].spawned_at == 5.0


def test_update_markers_drops_a_marker_once_it_scrolls_past_the_bottom() -> None:
    previous = {(0, 0, 60): Marker(track_index=0, velocity=100, spawned_at=0.0)}
    music_time = 20.0 / SCROLL_ROWS_PER_BEAT + 1.0

    result = update_markers(previous, {}, music_time=music_time, lines=20)

    assert result == {}


def test_update_markers_respawns_a_note_that_retriggers_after_scrolling_off() -> None:
    from propeller_vision.plasma import ActiveNote

    previous = {(0, 0, 60): Marker(track_index=0, velocity=100, spawned_at=0.0)}
    music_time = 20.0 / SCROLL_ROWS_PER_BEAT + 1.0
    active = {(0, 0, 60): ActiveNote(track_index=0, pitch=60, velocity=90)}

    result = update_markers(previous, active, music_time=music_time, lines=20)

    assert result == {(0, 0, 60): Marker(track_index=0, velocity=90, spawned_at=music_time)}


def test_ship_column_rests_at_center_when_no_notes_are_active() -> None:
    assert ship_column({}, cols=100) == 50


def test_ship_column_follows_the_highest_pitch_note() -> None:
    from propeller_vision.plasma import ActiveNote

    active = {
        (0, 0, 40): ActiveNote(track_index=0, pitch=40, velocity=100),
        (1, 0, 100): ActiveNote(track_index=1, pitch=100, velocity=60),
    }

    col = ship_column(active, cols=128)

    high_col = ship_column({(0, 0, 100): ActiveNote(track_index=0, pitch=100, velocity=60)}, cols=128)
    assert col == high_col


def test_render_space_frame_has_one_char_per_grid_position() -> None:
    frame = render_space_frame(cols=5, lines=3, markers={}, music_time=0.0, ship_col=2, lanes=1)

    assert len(frame.plain) == 5 * 3 + (3 - 1)
    assert frame.plain.count("\n") == 2


def test_render_space_frame_places_the_ship_on_the_bottom_row() -> None:
    frame = render_space_frame(cols=5, lines=3, markers={}, music_time=0.0, ship_col=2, lanes=1)

    rows = frame.plain.split("\n")
    assert rows[-1][1:4] == "▲■▲"
    assert rows[-2][2] == "▲"


def test_render_space_frame_places_a_marker_at_its_scrolled_row() -> None:
    markers = {(0, 0, 60): Marker(track_index=0, velocity=100, spawned_at=0.0)}

    frame = render_space_frame(cols=10, lines=10, markers=markers, music_time=1.0, ship_col=5, lanes=1)

    rows = frame.plain.split("\n")
    expected_row = int(SCROLL_ROWS_PER_BEAT)
    assert rows[expected_row].strip() == "@"
