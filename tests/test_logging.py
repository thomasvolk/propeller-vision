from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from propeller_vision.cli import configure_logging
from propeller_vision.poller import Poller
from propeller_vision.protocol import EngineClient
from tests.conftest import wait_until


def test_without_debug_nothing_is_written_to_a_log_file(tmp_path: Path) -> None:
    log_path = tmp_path / "propeller-vision.log"

    configure_logging(False, log_path)
    logging.getLogger("propeller_vision.somewhere").warning("should never be written")

    assert not log_path.exists()


def test_with_debug_a_log_call_is_written_to_the_log_file(tmp_path: Path) -> None:
    log_path = tmp_path / "propeller-vision.log"

    configure_logging(True, log_path)
    logging.getLogger("propeller_vision.somewhere").info("hello from debug mode")

    assert log_path.exists()
    assert "hello from debug mode" in log_path.read_text()


async def test_poller_logs_poll_failures_when_debug_is_enabled(tmp_path: Path) -> None:
    log_path = tmp_path / "propeller-vision.log"
    configure_logging(True, log_path)

    # Short path, no listening server -- guarantees an OSError on every poll,
    # same length-cap reasoning as tests/conftest.py's fake_engine fixture.
    socket_dir = tempfile.mkdtemp()
    unreachable_socket = Path(socket_dir) / "nonexistent.sock"

    poller = Poller(
        client_factory=lambda: EngineClient(str(unreachable_socket)),
        position_interval=0.01,
        status_interval=0.01,
    )
    poller.start()
    try:
        await wait_until(lambda: log_path.exists() and log_path.stat().st_size > 0)
        assert "poll failed" in log_path.read_text()
    finally:
        await poller.stop()
        shutil.rmtree(socket_dir, ignore_errors=True)
