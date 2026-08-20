import asyncio
from pathlib import Path

from propeller_vision.poller import Poller
from propeller_vision.protocol import EngineClient
from tests.conftest import wait_until
from tests.fake_engine import FakeEngine


async def test_poller_exposes_latest_position_status_and_project(fake_engine: FakeEngine) -> None:
    fake_engine.set_response("get-position", {"tick": 42, "loop_duration": 960, "loop_count": 0})
    fake_engine.set_response("status", {"status": "ok", "mode": "standalone", "bpm": 120})
    fake_engine.set_response("project", {"current": {"header": {"bpm": 120}}})

    poller = Poller(
        client_factory=lambda: EngineClient(str(fake_engine.socket_path)),
        position_interval=0.01,
        status_interval=0.01,
    )
    poller.start()
    try:
        await wait_until(lambda: poller.position is not None)
        await wait_until(lambda: poller.status is not None)
        await wait_until(lambda: poller.project is not None)

        assert poller.position == {"tick": 42, "loop_duration": 960, "loop_count": 0}
        assert poller.status == {"status": "ok", "mode": "standalone", "bpm": 120}
        assert poller.project == {"current": {"header": {"bpm": 120}}}
    finally:
        await poller.stop()


async def test_poller_position_and_status_intervals_are_independent(fake_engine: FakeEngine) -> None:
    fake_engine.set_response("get-position", {"tick": 1, "loop_duration": 960, "loop_count": 0})
    fake_engine.set_response("status", {"status": "ok", "mode": "standalone", "bpm": 120})
    fake_engine.set_response("project", {})

    poller = Poller(
        client_factory=lambda: EngineClient(str(fake_engine.socket_path)),
        position_interval=0.01,
        status_interval=1.0,
    )
    poller.start()
    try:
        await wait_until(lambda: poller.position is not None)
        await wait_until(lambda: poller.status is not None)
        position_requests_before = fake_engine.request_counts.get("get-position", 0)
        await asyncio.sleep(0.1)
        # position polls repeatedly at 10ms; status stays on its 1s cadence
        assert fake_engine.request_counts.get("get-position", 0) > position_requests_before + 3
        assert fake_engine.request_counts.get("status", 0) == 1
    finally:
        await poller.stop()


async def test_poller_starts_disconnected_and_never_crashes_when_socket_is_missing(
    short_tmp_path: Path,
) -> None:
    missing_socket = short_tmp_path / "does-not-exist.sock"

    poller = Poller(
        client_factory=lambda: EngineClient(str(missing_socket)),
        position_interval=0.01,
        status_interval=0.01,
    )
    poller.start()
    try:
        await asyncio.sleep(0.1)
        assert poller.connected is False
        assert poller.position is None
        assert poller.status is None
    finally:
        await poller.stop()


async def test_poller_becomes_connected_after_first_successful_poll(fake_engine: FakeEngine) -> None:
    fake_engine.set_response("get-position", {"tick": 1, "loop_duration": 960, "loop_count": 0})
    fake_engine.set_response("status", {"status": "ok", "mode": "standalone", "bpm": 120})
    fake_engine.set_response("project", {})

    poller = Poller(
        client_factory=lambda: EngineClient(str(fake_engine.socket_path)),
        position_interval=0.01,
        status_interval=0.01,
    )
    assert poller.connected is False
    poller.start()
    try:
        await wait_until(lambda: poller.connected is True)
    finally:
        await poller.stop()


async def test_poller_disconnects_when_engine_stops_and_reconnects_when_it_returns(fake_engine: FakeEngine) -> None:
    fake_engine.set_response("get-position", {"tick": 1, "loop_duration": 960, "loop_count": 0})
    fake_engine.set_response("status", {"status": "ok", "mode": "standalone", "bpm": 120})
    fake_engine.set_response("project", {})
    socket_path = fake_engine.socket_path
    assert socket_path is not None

    poller = Poller(
        client_factory=lambda: EngineClient(str(socket_path)),
        position_interval=0.01,
        status_interval=0.01,
    )
    poller.start()
    try:
        await wait_until(lambda: poller.connected is True)

        await fake_engine.stop()
        # each poll loop notices the engine is gone on its own next cycle,
        # so wait for both fields to clear rather than asserting the instant
        # `connected` first flips.
        await wait_until(lambda: poller.position is None)
        await wait_until(lambda: poller.status is None)
        assert poller.connected is False

        await fake_engine.start(socket_path)
        fake_engine.set_response("get-position", {"tick": 2, "loop_duration": 960, "loop_count": 0})
        fake_engine.set_response("status", {"status": "ok", "mode": "standalone", "bpm": 120})
        fake_engine.set_response("project", {})
        await wait_until(lambda: poller.connected is True)
        assert poller.position == {"tick": 2, "loop_duration": 960, "loop_count": 0}
    finally:
        await poller.stop()


async def test_poller_reconnects_promptly_with_no_backoff_once_the_socket_appears(
    short_tmp_path: Path,
) -> None:
    socket_path = short_tmp_path / "appears-later.sock"
    fake_engine = FakeEngine()

    poller = Poller(
        client_factory=lambda: EngineClient(str(socket_path)),
        position_interval=0.01,
        status_interval=0.01,
    )
    poller.start()
    try:
        # give it several failed attempts against the missing socket first
        await asyncio.sleep(0.1)
        assert poller.connected is False

        fake_engine.set_response("get-position", {"tick": 1, "loop_duration": 960, "loop_count": 0})
        fake_engine.set_response("status", {"status": "ok", "mode": "standalone", "bpm": 120})
        fake_engine.set_response("project", {})
        await fake_engine.start(socket_path)

        # a fixed backoff schedule would delay this well past one interval;
        # connecting within a small multiple of position_interval proves
        # there isn't one.
        await wait_until(lambda: poller.connected is True, timeout=0.5)
    finally:
        await poller.stop()
        await fake_engine.stop()
