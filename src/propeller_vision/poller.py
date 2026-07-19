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
from typing import Awaitable, Callable, TypeVar

from propeller_vision.protocol import EngineClient, EngineUnavailable, JsonDict

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def run_resilient_poll(
    fetch: Callable[[], Awaitable[T]],
    interval: float,
    on_success: Callable[[T], None],
    on_failure: Callable[[EngineUnavailable], None],
) -> None:
    """Shared retry-forever poll loop: no backoff, keeps calling `fetch` at
    `interval` regardless of success/failure. Used by both this module's
    Poller and Plasma's own ProjectPoller (ADR-0005) so the ticket-02
    resilience contract -- clear state and log on failure, retry at the same
    interval -- has one implementation instead of a copy per poller.
    """
    while True:
        try:
            result = await fetch()
        except EngineUnavailable as exc:
            on_failure(exc)
        else:
            on_success(result)
        await asyncio.sleep(interval)


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

        def on_success(position: JsonDict) -> None:
            self.position = position
            self.connected = True

        def on_failure(exc: EngineUnavailable) -> None:
            logger.warning("get_position poll failed: %s", exc)
            self.position = None
            self.connected = False

        await run_resilient_poll(client.get_position, self.position_interval, on_success, on_failure)

    async def _poll_status_and_project(self) -> None:
        client = self._client_factory()

        async def fetch() -> tuple[JsonDict, JsonDict]:
            status = await client.status()
            project = await client.project()
            return status, project

        def on_success(result: tuple[JsonDict, JsonDict]) -> None:
            self.status, self.project = result
            self.connected = True

        def on_failure(exc: EngineUnavailable) -> None:
            logger.warning("status/project poll failed: %s", exc)
            self.status = None
            self.project = None
            self.connected = False

        await run_resilient_poll(fetch, self.status_interval, on_success, on_failure)
