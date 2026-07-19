from pathlib import Path

from propeller_vision.plasma import ProjectPoller
from propeller_vision.protocol import EngineClient
from tests.conftest import wait_until
from tests.fake_engine import FakeEngine


async def test_project_poller_starts_disconnected_and_never_crashes_when_socket_is_missing(
    short_tmp_path: Path,
) -> None:
    missing_socket = short_tmp_path / "does-not-exist.sock"

    poller = ProjectPoller(
        client_factory=lambda: EngineClient(str(missing_socket)),
        interval=0.01,
    )
    poller.start()
    try:
        await wait_until(lambda: poller.connected is False)
        assert poller.project is None
    finally:
        await poller.stop()


async def test_project_poller_exposes_latest_project(fake_engine: FakeEngine) -> None:
    fake_engine.set_response("project", {"current": {"header": {"bpm": 120}, "tracks": []}})

    poller = ProjectPoller(
        client_factory=lambda: EngineClient(str(fake_engine.socket_path)),
        interval=0.01,
    )
    poller.start()
    try:
        await wait_until(lambda: poller.project is not None)
        assert poller.project == {"current": {"header": {"bpm": 120}, "tracks": []}}
        assert poller.connected is True
    finally:
        await poller.stop()


async def test_project_poller_disconnects_and_reconnects_when_engine_restarts(
    fake_engine: FakeEngine,
) -> None:
    fake_engine.set_response("project", {"current": {"header": {"bpm": 120}, "tracks": []}})
    socket_path = fake_engine.socket_path
    assert socket_path is not None

    poller = ProjectPoller(
        client_factory=lambda: EngineClient(str(socket_path)),
        interval=0.01,
    )
    poller.start()
    try:
        await wait_until(lambda: poller.connected is True)

        await fake_engine.stop()
        await wait_until(lambda: poller.connected is False)
        assert poller.project is None

        await fake_engine.start(socket_path)
        fake_engine.set_response("project", {"current": {"header": {"bpm": 140}, "tracks": []}})
        await wait_until(lambda: poller.connected is True)
        assert poller.project == {"current": {"header": {"bpm": 140}, "tracks": []}}
    finally:
        await poller.stop()
