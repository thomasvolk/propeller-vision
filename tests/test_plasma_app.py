import asyncio
from pathlib import Path

from textual.content import Content

from propeller_vision.app import PropellerVisionApp
from propeller_vision.dashboard import WAITING_FOR_ENGINE_MESSAGE
from propeller_vision.plasma import FRAME_INTERVAL, PlasmaView, ProjectPoller
from propeller_vision.poller import Poller
from propeller_vision.protocol import EngineClient
from tests.conftest import wait_until
from tests.fake_engine import FakeEngine


def _bg_color_at(content: Content, index: int) -> tuple[int, int, int]:
    style = content.get_style_at_offset(index)
    assert style.background is not None
    color = style.background
    return (color.r, color.g, color.b)


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
    app = PropellerVisionApp(poller, view="plasma", project_poller=project_poller)
    return app, poller, project_poller


async def test_plasma_view_renders_a_full_screen_flowing_field_once_connected(
    fake_engine: FakeEngine,
) -> None:
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
    fake_engine.set_response("status", {"status": "ok", "mode": "standalone", "bpm": 120})

    app, poller, project_poller = _build_app(fake_engine)

    async with app.run_test() as pilot:
        await wait_until(lambda: poller.connected and project_poller.connected)
        await asyncio.sleep(FRAME_INTERVAL * 2)
        await pilot.pause()

        view = app.query_one(PlasmaView)
        content = view.render()
        assert isinstance(content, Content)

        width, height = view.size.width, view.size.height
        assert width > 0 and height > 0
        # one styled space per cell, plus a newline between each row
        assert len(content.plain) == width * height + max(height - 1, 0)
        assert WAITING_FOR_ENGINE_MESSAGE not in content.plain


async def test_plasma_view_freezes_while_the_engine_is_paused(fake_engine: FakeEngine) -> None:
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
    fake_engine.set_response("status", {"status": "ok", "mode": "standalone", "bpm": 120, "clock_state": "paused"})

    app, poller, project_poller = _build_app(fake_engine)

    async with app.run_test() as pilot:
        await wait_until(lambda: poller.connected and project_poller.connected)
        await asyncio.sleep(FRAME_INTERVAL * 2)
        await pilot.pause()

        view = app.query_one(PlasmaView)
        sample_offsets = list(range(min(view.size.width, 5)))

        first = view.render()
        assert isinstance(first, Content)
        first_colors = [_bg_color_at(first, i) for i in sample_offsets]

        await asyncio.sleep(FRAME_INTERVAL * 3)
        await pilot.pause()

        second = view.render()
        assert isinstance(second, Content)
        second_colors = [_bg_color_at(second, i) for i in sample_offsets]

        assert first_colors == second_colors


async def test_plasma_view_flow_advances_while_playing(fake_engine: FakeEngine) -> None:
    fake_engine.set_response(
        "project",
        {
            "current": {
                "header": {"bpm": 120, "loop_duration": 960},
                "tracks": [],
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

        view = app.query_one(PlasmaView)
        sample_offsets = list(range(min(view.size.width, 5)))

        first = view.render()
        assert isinstance(first, Content)
        first_colors = [_bg_color_at(first, i) for i in sample_offsets]

        await asyncio.sleep(FRAME_INTERVAL * 10)
        await pilot.pause()

        second = view.render()
        assert isinstance(second, Content)
        second_colors = [_bg_color_at(second, i) for i in sample_offsets]

        assert first_colors != second_colors


async def test_plasma_view_shows_disconnected_indicator_when_engine_never_started(
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
    app = PropellerVisionApp(poller, view="plasma", project_poller=project_poller)

    async with app.run_test() as pilot:
        await asyncio.sleep(0.1)
        await asyncio.sleep(FRAME_INTERVAL * 2)
        await pilot.pause()

        rendered = app.query_one(PlasmaView).render()
        assert WAITING_FOR_ENGINE_MESSAGE in str(rendered)
