import pytest

from propeller_vision.space import (
    SCROLL_ROWS_PER_BEAT,
    Alien,
    Marker,
    Shot,
    alien_column,
    alien_row,
    lane_bounds,
    marker_column,
    marker_glyph,
    marker_row,
    render_space_frame,
    resolve_hits,
    ship_column,
    shot_row,
    track_count,
    update_aliens,
    update_markers,
    update_shots,
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
    frame = render_space_frame(cols=5, lines=3, markers={}, aliens={}, shots={}, music_time=0.0, ship_col=2, lanes=1)

    assert len(frame.plain) == 5 * 3 + (3 - 1)
    assert frame.plain.count("\n") == 2


def test_render_space_frame_places_the_ship_on_the_bottom_row() -> None:
    frame = render_space_frame(cols=5, lines=3, markers={}, aliens={}, shots={}, music_time=0.0, ship_col=2, lanes=1)

    rows = frame.plain.split("\n")
    assert rows[-1] == "▲■■■▲"
    assert rows[-2] == " ▲■▲ "
    assert rows[-3] == "  ▲  "


def test_render_space_frame_places_a_marker_at_its_scrolled_row() -> None:
    markers = {(0, 0, 60): Marker(track_index=0, velocity=100, spawned_at=0.0)}

    frame = render_space_frame(
        cols=10, lines=10, markers=markers, aliens={}, shots={}, music_time=1.0, ship_col=5, lanes=1
    )

    rows = frame.plain.split("\n")
    expected_row = int(SCROLL_ROWS_PER_BEAT)
    assert rows[expected_row].strip() == "@"


def test_marker_column_centers_on_the_lane() -> None:
    assert marker_column(track_index=0, lanes=2, cols=100) == 25
    assert marker_column(track_index=1, lanes=2, cols=100) == 75


def test_alien_row_advances_with_music_time_like_a_marker() -> None:
    alien = Alien(track_index=0, spawned_at=1.0)

    assert alien_row(alien, music_time=1.0) == 0.0
    assert alien_row(alien, music_time=2.0) == pytest.approx(SCROLL_ROWS_PER_BEAT)


def test_alien_column_wobbles_around_the_lane_center() -> None:
    alien = Alien(track_index=0, spawned_at=0.0)

    center = marker_column(track_index=0, lanes=1, cols=100)
    at_zero_phase = alien_column(alien, music_time=0.0, lanes=1, cols=100)

    assert at_zero_phase == center
    # a quarter cycle in should have wobbled away from center
    quarter_cycle = 1.0  # ALIEN_WAVE_BEATS_PER_CYCLE / 4
    assert alien_column(alien, music_time=quarter_cycle, lanes=1, cols=100) != center


def test_update_aliens_spawns_alongside_a_newly_active_note() -> None:
    from propeller_vision.plasma import ActiveNote

    active = {(0, 0, 60): ActiveNote(track_index=0, pitch=60, velocity=100)}

    result = update_aliens({}, active, music_time=5.0, lines=20)

    assert result == {(0, 0, 60): Alien(track_index=0, spawned_at=5.0)}


def test_update_aliens_drops_one_once_it_scrolls_past_the_bottom() -> None:
    previous = {(0, 0, 60): Alien(track_index=0, spawned_at=0.0)}
    music_time = 20.0 / SCROLL_ROWS_PER_BEAT + 1.0

    result = update_aliens(previous, {}, music_time=music_time, lines=20)

    assert result == {}


def test_shot_row_travels_upward_from_its_spawn_row() -> None:
    shot = Shot(column=5, spawned_at=1.0, spawn_row=18.0)

    assert shot_row(shot, music_time=1.0) == 18.0
    assert shot_row(shot, music_time=2.0) == pytest.approx(18.0 - SCROLL_ROWS_PER_BEAT)


def test_update_shots_fires_once_per_newly_active_note_from_the_ships_column() -> None:
    from propeller_vision.plasma import ActiveNote

    active = {(0, 0, 60): ActiveNote(track_index=0, pitch=60, velocity=100)}

    result = update_shots({}, active, music_time=5.0, ship_col=7, spawn_row=18.0)

    assert result == {(0, 0, 60): Shot(column=7, spawned_at=5.0, spawn_row=18.0)}


def test_update_shots_drops_one_once_it_travels_past_the_top() -> None:
    previous = {(0, 0, 60): Shot(column=7, spawned_at=0.0, spawn_row=18.0)}
    music_time = 18.0 / SCROLL_ROWS_PER_BEAT + 1.0

    result = update_shots(previous, {}, music_time=music_time, ship_col=7, spawn_row=18.0)

    assert result == {}


def test_resolve_hits_destroys_a_marker_sharing_the_shots_cell() -> None:
    # A shot spawned to arrive exactly at the marker's row/column this instant.
    shot = Shot(column=25, spawned_at=0.0, spawn_row=2 * SCROLL_ROWS_PER_BEAT)
    marker = Marker(track_index=0, velocity=100, spawned_at=0.0)
    shots = {(0, 0, 60): shot}
    markers = {(0, 0, 60): marker}

    remaining_shots, remaining_markers, remaining_aliens = resolve_hits(
        shots, markers, {}, music_time=1.0, lanes=2, cols=100
    )

    assert remaining_shots == {}
    assert remaining_markers == {}
    assert remaining_aliens == {}


def test_resolve_hits_destroys_an_alien_sharing_the_shots_cell() -> None:
    alien = Alien(track_index=0, spawned_at=0.0)
    alien_col = alien_column(alien, music_time=1.0, lanes=1, cols=100)
    shot = Shot(column=alien_col, spawned_at=0.0, spawn_row=2 * SCROLL_ROWS_PER_BEAT)
    shots = {(0, 0, 60): shot}
    aliens = {(0, 0, 60): alien}

    remaining_shots, remaining_markers, remaining_aliens = resolve_hits(
        shots, {}, aliens, music_time=1.0, lanes=1, cols=100
    )

    assert remaining_shots == {}
    assert remaining_markers == {}
    assert remaining_aliens == {}


def test_resolve_hits_leaves_everything_when_no_shot_reaches_a_target() -> None:
    shot = Shot(column=99, spawned_at=0.0, spawn_row=18.0)
    marker = Marker(track_index=0, velocity=100, spawned_at=0.0)
    shots = {(0, 0, 60): shot}
    markers = {(0, 0, 60): marker}

    remaining_shots, remaining_markers, remaining_aliens = resolve_hits(
        shots, markers, {}, music_time=1.0, lanes=2, cols=100
    )

    assert remaining_shots == shots
    assert remaining_markers == markers
    assert remaining_aliens == {}
