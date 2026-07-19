"""View-agnostic shared polling layer.

Polls the Engine's get_position on one timer and status/project on another,
independent timer, exposing the latest known values. Knows nothing about
Tracks/notes or which View (if any) is consuming its state -- that split is
deliberate: see ADR-0005.

If a poll fails (Engine unreachable), the corresponding data is cleared to
None and `connected` is set False; polling keeps retrying at the same
interval with no backoff. A later successful poll repopulates the data and
sets `connected` back to True.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from propeller_vision.protocol import EngineClient, EngineUnavailable, JsonDict

logger = logging.getLogger(__name__)


class Poller:
    def __init__(
        self,
        client_factory: Callable[[], EngineClient],
        position_interval: float,
        status_interval: float,
    ) -> None:
        self._client_factory = client_factory
        self.position_interval = position_interval
        self.status_interval = status_interval

        self.position: JsonDict | None = None
        self.status: JsonDict | None = None
        self.project: JsonDict | None = None
        self.connected = False

        self._tasks: list[asyncio.Task[None]] = []

    def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._poll_position()),
            asyncio.create_task(self._poll_status_and_project()),
        ]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks = []

    async def _poll_position(self) -> None:
        client = self._client_factory()
        while True:
            try:
                self.position = await client.get_position()
                self.connected = True
            except EngineUnavailable as exc:
                logger.warning("get_position poll failed: %s", exc)
                self.position = None
                self.connected = False
            await asyncio.sleep(self.position_interval)

    async def _poll_status_and_project(self) -> None:
        client = self._client_factory()
        while True:
            try:
                self.status = await client.status()
                self.project = await client.project()
                self.connected = True
            except EngineUnavailable as exc:
                logger.warning("status/project poll failed: %s", exc)
                self.status = None
                self.project = None
                self.connected = False
            await asyncio.sleep(self.status_interval)
