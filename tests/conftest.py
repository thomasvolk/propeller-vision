import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import AsyncIterator, Callable

import pytest

from tests.fake_engine import FakeEngine


@pytest.fixture
async def fake_engine() -> AsyncIterator[FakeEngine]:
    # macOS AF_UNIX paths are capped at ~104 bytes; pytest's tmp_path nests
    # too deep, so use a short-path temp dir instead.
    tmp_dir = tempfile.mkdtemp()
    engine = FakeEngine()
    socket_path = Path(tmp_dir) / "s.sock"
    await engine.start(socket_path)
    yield engine
    await engine.stop()
    shutil.rmtree(tmp_dir, ignore_errors=True)


async def wait_until(predicate: Callable[[], bool], timeout: float = 2.0) -> None:
    async def _poll() -> None:
        while not predicate():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(_poll(), timeout=timeout)
