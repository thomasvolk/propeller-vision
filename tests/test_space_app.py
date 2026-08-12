import asyncio
from pathlib import Path

from propeller_vision.app import PropellerVisionApp
from propeller_vision.dashboard import WAITING_FOR_ENGINE_MESSAGE
from propeller_vision.plasma import ProjectPoller
from propeller_vision.poller import Poller
from propeller_vision.protocol import EngineClient
from propeller_vision.space import FRAME_INTERVAL, SpaceView
from tests.conftest import wait_until
from tests.fake_engine import FakeEngine


def _build_app(fake_engine: FakeEngine) -> tuple[PropellerVisionApp, Poller, ProjectPoller]:
    poller = Poller(
        client_factory=lambda: EngineClient(str(fake_engine.socket_path)),
        position_interval=0.01,
        status_interval=0.01,
    )
    project_poller = ProjectPoller(
        client_factory=lambda: EngineClient(str(fake_engine.socket_path)),
        interval=0.01,
    )
    app = PropellerVisionApp(poller, view="space", project_poller=project_poller)
    return app, poller, project_poller


async def test_space_view_renders_a_full_grid_once_connected(fake_engine: FakeEngine) -> None:
    fake_engine.set_response(
        "project",
        {
            "current": {
                "header": {"bpm": 120, "loop_duration": 960},
                "tracks": [
                    {"name": "bass", "channel": 1, "instrument": 32, "notes": [[0, 960, 36, 100]]},
                ],
            }
        },
    )
    fake_engine.set_response("get_position", {"type": "position", "tick": 100, "loop_duration": 960})
    fake_engine.set_response("status", {"status": "ok", "mode": "standalone", "bpm": 120, "clock_state": "running"})

    app, poller, project_poller = _build_app(fake_engine)

    async with app.run_test() as pilot:
        await wait_until(lambda: poller.connected and project_poller.connected)
        await asyncio.sleep(FRAME_INTERVAL * 2)
        await pilot.pause()

        view = app.query_one(SpaceView)
        content = str(view.render())

        assert WAITING_FOR_ENGINE_MESSAGE not in content
        assert "▲" in content  # the ship glyph


async def test_space_view_freezes_while_the_engine_is_paused(fake_engine: FakeEngine) -> None:
    fake_engine.set_response(
        "project",
        {"current": {"header": {"bpm": 120, "loop_duration": 960}, "tracks": []}},
    )
    fake_engine.set_response("get_position", {"type": "position", "tick": 100, "loop_duration": 960})
    fake_engine.set_response("status", {"status": "ok", "mode": "standalone", "bpm": 120, "clock_state": "paused"})

    app, poller, project_poller = _build_app(fake_engine)

    async with app.run_test() as pilot:
        await wait_until(lambda: poller.connected and project_poller.connected)
        await asyncio.sleep(FRAME_INTERVAL * 2)
        await pilot.pause()

        view = app.query_one(SpaceView)
        first = str(view.render())

        await asyncio.sleep(FRAME_INTERVAL * 3)
        await pilot.pause()

        second = str(view.render())

        assert first == second


async def test_space_view_ship_returns_to_center_with_no_active_notes(fake_engine: FakeEngine) -> None:
    fake_engine.set_response(
        "project",
        {"current": {"header": {"bpm": 120, "loop_duration": 960}, "tracks": []}},
    )
    fake_engine.set_response("get_position", {"type": "position", "tick": 100, "loop_duration": 960})
    fake_engine.set_response("status", {"status": "ok", "mode": "standalone", "bpm": 120, "clock_state": "running"})

    app, poller, project_poller = _build_app(fake_engine)

    async with app.run_test() as pilot:
        await wait_until(lambda: poller.connected and project_poller.connected)
        await asyncio.sleep(FRAME_INTERVAL * 2)
        await pilot.pause()

        view = app.query_one(SpaceView)
        rows = str(view.render()).split("\n")
        expected_col = view.size.width // 2

        assert rows[-1][expected_col] == "■"
        assert rows[-2][expected_col] == "■"
        assert rows[-3][expected_col] == "▲"


async def test_space_view_shows_disconnected_indicator_when_engine_never_started(
    short_tmp_path: Path,
) -> None:
    missing_socket = short_tmp_path / "does-not-exist.sock"

    poller = Poller(
        client_factory=lambda: EngineClient(str(missing_socket)),
        position_interval=0.01,
        status_interval=0.01,
    )
    project_poller = ProjectPoller(
        client_factory=lambda: EngineClient(str(missing_socket)),
        interval=0.01,
    )
    app = PropellerVisionApp(poller, view="space", project_poller=project_poller)

    async with app.run_test() as pilot:
        await asyncio.sleep(0.1)
        await asyncio.sleep(FRAME_INTERVAL * 2)
        await pilot.pause()

        rendered = str(app.query_one(SpaceView).render())
        assert WAITING_FOR_ENGINE_MESSAGE in rendered
