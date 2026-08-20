import asyncio
from pathlib import Path

import pytest

from propeller_vision.protocol import EngineClient, EngineUnavailable
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


async def test_get_position_uses_command_field(fake_engine: FakeEngine) -> None:
    fake_engine.set_response("get-position", {"type": "position", "tick": 42, "loop_duration": 960})

    client = EngineClient(str(fake_engine.socket_path))
    response = await client.get_position()

    assert response == {"type": "position", "tick": 42, "loop_duration": 960}


async def test_missing_socket_raises_engine_unavailable(short_tmp_path: Path) -> None:
    client = EngineClient(str(short_tmp_path / "does-not-exist.sock"))

    with pytest.raises(EngineUnavailable):
        await client.status()


async def test_connection_closed_without_a_response_raises_engine_unavailable(
    short_tmp_path: Path,
) -> None:
    socket_path = short_tmp_path / "s.sock"

    async def close_immediately(
        _reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_unix_server(close_immediately, path=str(socket_path))
    try:
        client = EngineClient(str(socket_path))
        with pytest.raises(EngineUnavailable):
            await client.status()
    finally:
        server.close()
        await server.wait_closed()


async def test_a_connection_that_never_responds_times_out_as_engine_unavailable(
    short_tmp_path: Path,
) -> None:
    socket_path = short_tmp_path / "s.sock"

    async def hang_forever(
        _reader: asyncio.StreamReader, _writer: asyncio.StreamWriter
    ) -> None:
        await asyncio.sleep(3600)

    server = await asyncio.start_unix_server(hang_forever, path=str(socket_path))
    try:
        client = EngineClient(str(socket_path), timeout=0.05)
        with pytest.raises(EngineUnavailable):
            await client.status()
    finally:
        server.close()
        await server.wait_closed()
