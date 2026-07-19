import asyncio
from pathlib import Path

from textual.content import Content

from propeller_vision.app import PropellerVisionApp
from propeller_vision.plasma import PlasmaView, ProjectPoller, track_color
from propeller_vision.poller import Poller
from propeller_vision.protocol import EngineClient
from tests.conftest import wait_until
from tests.fake_engine import FakeEngine


def _color_at(content: Content, index: int) -> tuple[int, int, int] | None:
    if content.plain[index] == " ":
        return None
    style = content.get_style_at_offset(index)
    assert style.foreground is not None
    color = style.foreground
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


async def test_plasma_view_renders_active_notes_positioned_and_colored_by_track(
    fake_engine: FakeEngine,
) -> None:
    fake_engine.set_response(
        "project",
        {
            "current": {
                "header": {"bpm": 120, "loop_duration": 960},
                "tracks": [
                    {"name": "bass", "channel": 1, "instrument": 32, "notes": [[0, 960, 36, 100]]},
                    {"name": "lead", "channel": 2, "instrument": 0, "notes": [[50, 200, 72, 64]]},
                ],
            }
        },
    )
    fake_engine.set_response("get_position", {"type": "position", "tick": 100, "loop_duration": 960})
    fake_engine.set_response("status", {"status": "ok", "mode": "standalone", "bpm": 120})

    app, poller, project_poller = _build_app(fake_engine)

    async with app.run_test() as pilot:
        await wait_until(lambda: poller.connected and project_poller.connected)
        await pilot.pause()

        text = app.query_one(PlasmaView).render()
        assert isinstance(text, Content)

        assert _color_at(text, 36) == track_color(0, intensity=100 / 127)
        assert _color_at(text, 72) == track_color(1, intensity=64 / 127)
        # an unrelated pitch stays blank
        assert _color_at(text, 90) is None


async def test_plasma_view_handles_a_note_spanning_the_loop_boundary(
    fake_engine: FakeEngine,
) -> None:
    fake_engine.set_response(
        "project",
        {
            "current": {
                "header": {"bpm": 120, "loop_duration": 960},
                "tracks": [
                    {"name": "pad", "channel": 1, "instrument": 89, "notes": [[940, 40, 48, 70]]},
                ],
            }
        },
    )
    fake_engine.set_response("status", {"status": "ok", "mode": "standalone", "bpm": 120})

    app, poller, project_poller = _build_app(fake_engine)

    async with app.run_test() as pilot:
        # just before the loop wraps: note should be active
        fake_engine.set_response("get_position", {"type": "position", "tick": 950, "loop_duration": 960})
        await wait_until(lambda: poller.connected and project_poller.connected)
        await wait_until(lambda: poller.position is not None and poller.position.get("tick") == 950)
        await pilot.pause()
        text = app.query_one(PlasmaView).render()
        assert isinstance(text, Content)
        assert _color_at(text, 48) == track_color(0, intensity=70 / 127)

        # squarely outside the note's span (mid-loop): not active
        fake_engine.set_response("get_position", {"type": "position", "tick": 500, "loop_duration": 960})
        await wait_until(lambda: poller.position is not None and poller.position.get("tick") == 500)
        await pilot.pause()
        text = app.query_one(PlasmaView).render()
        assert isinstance(text, Content)
        assert _color_at(text, 48) is None

        # just after the loop wraps back to the start: still active
        fake_engine.set_response("get_position", {"type": "position", "tick": 5, "loop_duration": 960})
        await wait_until(lambda: poller.position is not None and poller.position.get("tick") == 5)
        await pilot.pause()
        text = app.query_one(PlasmaView).render()
        assert isinstance(text, Content)
        assert _color_at(text, 48) == track_color(0, intensity=70 / 127)


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
        await pilot.pause()

        rendered = app.query_one(PlasmaView).render()
        assert "Waiting for engine..." in str(rendered)
