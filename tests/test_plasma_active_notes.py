from propeller_vision.plasma import ActiveNote, active_notes, is_active


def test_is_active_within_normal_span() -> None:
    assert is_active(start_tick=100, duration=50, position_tick=120, loop_duration=960) is True


def test_is_active_before_start() -> None:
    assert is_active(start_tick=100, duration=50, position_tick=99, loop_duration=960) is False


def test_is_active_at_start_is_inclusive() -> None:
    assert is_active(start_tick=100, duration=50, position_tick=100, loop_duration=960) is True


def test_is_active_at_end_is_exclusive() -> None:
    assert is_active(start_tick=100, duration=50, position_tick=150, loop_duration=960) is False


def test_is_active_wraps_around_loop_boundary_near_end() -> None:
    # note starts near the end of a 960-tick loop and runs past the boundary
    assert is_active(start_tick=940, duration=40, position_tick=950, loop_duration=960) is True


def test_is_active_wraps_around_loop_boundary_after_restart() -> None:
    assert is_active(start_tick=940, duration=40, position_tick=10, loop_duration=960) is True


def test_is_active_wraps_around_loop_boundary_outside_span() -> None:
    assert is_active(start_tick=940, duration=40, position_tick=500, loop_duration=960) is False
    assert is_active(start_tick=940, duration=40, position_tick=20, loop_duration=960) is False


def test_active_notes_returns_empty_when_project_is_none() -> None:
    position = {"type": "position", "tick": 10, "loop_duration": 960}
    assert active_notes(None, position) == {}


def test_active_notes_returns_empty_when_position_is_none() -> None:
    project = {"current": {"header": {"bpm": 120, "loop_duration": 960}, "tracks": []}}
    assert active_notes(project, None) == {}


def test_active_notes_returns_empty_when_no_current_project() -> None:
    project = {"pending": {"header": {"bpm": 120, "loop_duration": 960}, "tracks": []}}
    position = {"type": "position", "tick": 10, "loop_duration": 960}
    assert active_notes(project, position) == {}


def test_active_notes_returns_empty_when_loop_duration_is_null() -> None:
    project = {"current": {"header": {"bpm": 120}, "tracks": []}}
    position = {"type": "position", "tick": 10, "loop_duration": None}
    assert active_notes(project, position) == {}


def test_active_notes_finds_note_across_one_track() -> None:
    project = {
        "current": {
            "header": {"bpm": 120, "loop_duration": 960},
            "tracks": [
                {"name": "lead", "channel": 1, "instrument": 0, "notes": [[100, 50, 60, 80]]},
            ],
        }
    }
    position = {"type": "position", "tick": 120, "loop_duration": 960}

    result = active_notes(project, position)

    assert result == {(0, 100, 60): ActiveNote(track_index=0, pitch=60, velocity=80)}


def test_active_notes_across_multiple_tracks_simultaneously() -> None:
    project = {
        "current": {
            "header": {"bpm": 120, "loop_duration": 960},
            "tracks": [
                {"name": "bass", "channel": 1, "instrument": 32, "notes": [[0, 200, 36, 100]]},
                {"name": "lead", "channel": 2, "instrument": 0, "notes": [[50, 200, 72, 90]]},
            ],
        }
    }
    position = {"type": "position", "tick": 100, "loop_duration": 960}

    result = active_notes(project, position)

    assert result == {
        (0, 0, 36): ActiveNote(track_index=0, pitch=36, velocity=100),
        (1, 50, 72): ActiveNote(track_index=1, pitch=72, velocity=90),
    }


def test_active_notes_ignores_notes_not_currently_sounding() -> None:
    project = {
        "current": {
            "header": {"bpm": 120, "loop_duration": 960},
            "tracks": [
                {"name": "lead", "channel": 1, "instrument": 0, "notes": [[500, 50, 60, 80]]},
            ],
        }
    }
    position = {"type": "position", "tick": 10, "loop_duration": 960}

    assert active_notes(project, position) == {}


def test_active_notes_handles_wraparound_note() -> None:
    project = {
        "current": {
            "header": {"bpm": 120, "loop_duration": 960},
            "tracks": [
                {"name": "pad", "channel": 1, "instrument": 89, "notes": [[940, 40, 48, 70]]},
            ],
        }
    }
    just_after_wrap = {"type": "position", "tick": 5, "loop_duration": 960}
    just_before_wrap = {"type": "position", "tick": 950, "loop_duration": 960}
    outside_span = {"type": "position", "tick": 500, "loop_duration": 960}

    assert active_notes(project, just_after_wrap) == {
        (0, 940, 48): ActiveNote(track_index=0, pitch=48, velocity=70)
    }
    assert active_notes(project, just_before_wrap) == {
        (0, 940, 48): ActiveNote(track_index=0, pitch=48, velocity=70)
    }
    assert active_notes(project, outside_span) == {}
