from propeller_vision.dashboard import format_playhead, format_status_panel


def test_playhead_shows_waiting_message_before_first_poll() -> None:
    assert format_playhead(None) == "Waiting for engine..."


def test_playhead_shows_no_project_message_when_loop_duration_is_null() -> None:
    assert format_playhead({"tick": None, "loop_duration": None}) == "No project loaded"


def test_playhead_renders_bar_scaled_to_loop_duration() -> None:
    text = format_playhead({"tick": 480, "loop_duration": 960})
    assert "480/960" in text
    assert text.count("#") == 20
    assert text.count(".") == 20


def test_status_panel_shows_waiting_message_before_first_poll() -> None:
    assert format_status_panel(None, None) == "Waiting for engine..."


def test_status_panel_shows_mode_bpm_and_clock_state() -> None:
    status = {"status": "ok", "mode": "standalone", "bpm": 120, "clock_state": "stopped"}
    text = format_status_panel(status, None)
    assert "Mode: standalone" in text
    assert "BPM: 120" in text
    assert "Clock: stopped" in text


def test_status_panel_omits_sync_clock_state_outside_sync_mode() -> None:
    status = {"status": "ok", "mode": "standalone", "bpm": 120, "clock_state": "stopped"}
    text = format_status_panel(status, None)
    assert "Sync:" not in text


def test_status_panel_shows_sync_clock_state_in_sync_mode() -> None:
    status = {
        "status": "ok",
        "mode": "sync",
        "bpm": 120,
        "clock_state": "running",
        "sync_clock_state": "tracking",
    }
    text = format_status_panel(status, None)
    assert "Sync: tracking" in text


def test_status_panel_reports_current_and_pending_project_presence() -> None:
    status = {"status": "ok", "mode": "standalone", "bpm": 120, "clock_state": "stopped"}
    project = {"current": {"header": {"bpm": 120}}, "pending": {"header": {"bpm": 140}}}
    text = format_status_panel(status, project)
    assert "current=yes" in text
    assert "pending=yes" in text


def test_status_panel_reports_no_project_when_absent() -> None:
    status = {"status": "ok", "mode": "standalone", "bpm": 120, "clock_state": "stopped"}
    text = format_status_panel(status, {})
    assert "current=no" in text
    assert "pending=no" in text


def test_status_panel_omits_loop_count_when_position_is_none() -> None:
    status = {"status": "ok", "mode": "standalone", "bpm": 120, "clock_state": "stopped"}
    text = format_status_panel(status, None)
    assert "Loop:" not in text


def test_status_panel_shows_loop_count_from_position() -> None:
    status = {"status": "ok", "mode": "standalone", "bpm": 120, "clock_state": "stopped"}
    position = {"tick": 10, "loop_duration": 960, "loop_count": 3}
    text = format_status_panel(status, None, position)
    assert "Loop: 3" in text
