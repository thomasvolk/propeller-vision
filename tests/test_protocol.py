from propeller_vision.protocol import EngineClient
from tests.fake_engine import FakeEngine


async def test_status_round_trips_through_the_socket(fake_engine: FakeEngine) -> None:
    fake_engine.set_response("status", {"status": "ok", "mode": "standalone", "bpm": 120})

    client = EngineClient(str(fake_engine.socket_path))
    response = await client.status()

    assert response == {"status": "ok", "mode": "standalone", "bpm": 120}


async def test_project_round_trips_through_the_socket(fake_engine: FakeEngine) -> None:
    fake_engine.set_response("project", {"current": {"header": {"bpm": 100}}})

    client = EngineClient(str(fake_engine.socket_path))
    response = await client.project()

    assert response == {"current": {"header": {"bpm": 100}}}


async def test_get_position_uses_type_field_not_command(fake_engine: FakeEngine) -> None:
    fake_engine.set_response("get_position", {"type": "position", "tick": 42, "loop_duration": 960})

    client = EngineClient(str(fake_engine.socket_path))
    response = await client.get_position()

    assert response == {"type": "position", "tick": 42, "loop_duration": 960}
