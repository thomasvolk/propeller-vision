import asyncio

from propeller_vision.poller import Poller
from propeller_vision.protocol import EngineClient
from tests.conftest import wait_until
from tests.fake_engine import FakeEngine


async def test_poller_exposes_latest_position_status_and_project(fake_engine: FakeEngine) -> None:
    fake_engine.set_response("get_position", {"type": "position", "tick": 42, "loop_duration": 960})
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

        assert poller.position == {"type": "position", "tick": 42, "loop_duration": 960}
        assert poller.status == {"status": "ok", "mode": "standalone", "bpm": 120}
        assert poller.project == {"current": {"header": {"bpm": 120}}}
    finally:
        await poller.stop()


async def test_poller_position_and_status_intervals_are_independent(fake_engine: FakeEngine) -> None:
    fake_engine.set_response("get_position", {"type": "position", "tick": 1, "loop_duration": 960})
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
        position_requests_before = fake_engine.request_counts.get("get_position", 0)
        await asyncio.sleep(0.1)
        # position polls repeatedly at 10ms; status stays on its 1s cadence
        assert fake_engine.request_counts.get("get_position", 0) > position_requests_before + 3
        assert fake_engine.request_counts.get("status", 0) == 1
    finally:
        await poller.stop()
