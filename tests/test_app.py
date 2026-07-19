import asyncio
from pathlib import Path

import pytest
from textual.widgets import Static

from propeller_vision.app import PropellerVisionApp
from propeller_vision.dashboard import Dashboard
from propeller_vision.poller import Poller
from propeller_vision.protocol import EngineClient
from tests.conftest import wait_until
from tests.fake_engine import FakeEngine


def test_plasma_view_requires_a_project_poller() -> None:
    poller = Poller(
        client_factory=lambda: EngineClient("/tmp/unused.sock"),
        position_interval=0.1,
        status_interval=1.0,
    )

    with pytest.raises(ValueError):
        PropellerVisionApp(poller, view="plasma", project_poller=None)


async def test_dashboard_renders_live_position_and_status_from_the_engine(fake_engine: FakeEngine) -> None:
    fake_engine.set_response("get_position", {"type": "position", "tick": 480, "loop_duration": 960})
    fake_engine.set_response(
        "status",
        {"status": "ok", "mode": "standalone", "bpm": 120, "clock_state": "running"},
    )
    fake_engine.set_response("project", {"current": {"header": {"bpm": 120}}})

    poller = Poller(
        client_factory=lambda: EngineClient(str(fake_engine.socket_path)),
        position_interval=0.01,
        status_interval=0.01,
    )
    app = PropellerVisionApp(poller)

    async with app.run_test() as pilot:
        await wait_until(lambda: poller.position is not None and poller.status is not None)
        await pilot.pause()

        dashboard = app.query_one(Dashboard)
        playhead_text = str(dashboard.query_one("#playhead", Static).render())
        status_text = str(dashboard.query_one("#status-panel", Static).render())

        assert "480/960" in playhead_text
        assert "Mode: standalone" in status_text
        assert "BPM: 120" in status_text
        assert "current=yes" in status_text
        assert "pending=no" in status_text


async def test_dashboard_shows_sync_clock_state_only_in_sync_mode(fake_engine: FakeEngine) -> None:
    fake_engine.set_response("get_position", {"type": "position", "tick": 0, "loop_duration": 960})
    fake_engine.set_response(
        "status",
        {
            "status": "ok",
            "mode": "sync",
            "bpm": 120,
            "clock_state": "running",
            "sync_clock_state": "tracking",
        },
    )
    fake_engine.set_response("project", {})

    poller = Poller(
        client_factory=lambda: EngineClient(str(fake_engine.socket_path)),
        position_interval=0.01,
        status_interval=0.01,
    )
    app = PropellerVisionApp(poller)

    async with app.run_test() as pilot:
        await wait_until(lambda: poller.status is not None)
        await pilot.pause()

        dashboard = app.query_one(Dashboard)
        status_text = str(dashboard.query_one("#status-panel", Static).render())

        assert "Sync: tracking" in status_text


async def test_dashboard_shows_disconnected_indicator_and_recovers_when_engine_restarts(
    fake_engine: FakeEngine,
) -> None:
    fake_engine.set_response("get_position", {"type": "position", "tick": 100, "loop_duration": 960})
    fake_engine.set_response("status", {"status": "ok", "mode": "standalone", "bpm": 120})
    fake_engine.set_response("project", {})
    socket_path = fake_engine.socket_path
    assert socket_path is not None

    poller = Poller(
        client_factory=lambda: EngineClient(str(socket_path)),
        position_interval=0.01,
        status_interval=0.01,
    )
    app = PropellerVisionApp(poller)

    async with app.run_test() as pilot:
        await wait_until(lambda: poller.connected is True)
        await pilot.pause()
        dashboard = app.query_one(Dashboard)
        assert "100/960" in str(dashboard.query_one("#playhead", Static).render())

        await fake_engine.stop()
        await wait_until(lambda: poller.connected is False)
        await pilot.pause()
        assert "Waiting for engine..." in str(dashboard.query_one("#playhead", Static).render())
        assert "Waiting for engine..." in str(dashboard.query_one("#status-panel", Static).render())

        await fake_engine.start(socket_path)
        fake_engine.set_response("get_position", {"type": "position", "tick": 200, "loop_duration": 960})
        fake_engine.set_response("status", {"status": "ok", "mode": "standalone", "bpm": 120})
        fake_engine.set_response("project", {})
        await wait_until(lambda: poller.connected is True)
        await pilot.pause()
        assert "200/960" in str(dashboard.query_one("#playhead", Static).render())


async def test_dashboard_shows_disconnected_indicator_when_engine_never_started(
    short_tmp_path: Path,
) -> None:
    missing_socket = short_tmp_path / "does-not-exist.sock"

    poller = Poller(
        client_factory=lambda: EngineClient(str(missing_socket)),
        position_interval=0.01,
        status_interval=0.01,
    )
    app = PropellerVisionApp(poller)

    async with app.run_test() as pilot:
        # let several poll cycles genuinely fail against the missing socket
        # rather than trusting the pre-poll default state
        await asyncio.sleep(0.1)
        await pilot.pause()

        dashboard = app.query_one(Dashboard)
        assert "Waiting for engine..." in str(dashboard.query_one("#playhead", Static).render())
        assert "Waiting for engine..." in str(dashboard.query_one("#status-panel", Static).render())
        assert poller.connected is False
        assert poller.position is None
        assert poller.status is None
