"""The Plasma View: reacts to played notes.

Active Notes are derived by cross-referencing each Track's note data
against the current Position -- computed here, not in the shared Poller
(ADR-0004/ADR-0005 draw that boundary at the view, not the data layer).
"""

from __future__ import annotations

import asyncio
import colorsys
import logging
import time
from dataclasses import dataclass
from typing import Callable

from rich.style import Style
from rich.text import Text
from textual.widgets import Static

from propeller_vision.dashboard import WAITING_FOR_ENGINE_MESSAGE
from propeller_vision.poller import Poller, run_resilient_poll
from propeller_vision.protocol import EngineClient, EngineUnavailable, JsonDict

logger = logging.getLogger(__name__)

# (track_index, start_tick, pitch) identifies one note occurrence within a
# Track's fixed note list -- stable across polls of the same Project.
NoteKey = tuple[int, int, int]

# How long a flash keeps fading after the note stops sounding.
DECAY_SECONDS = 0.1

# Golden-angle hue step: gives evenly spread, distinguishable per-Track hues
# regardless of how many Tracks a Project has.
_HUE_STEP = 0.618033988749895

# MIDI pitches run 0-127; one spatial column per pitch.
PITCH_RANGE = 128


@dataclass(frozen=True)
class ActiveNote:
    track_index: int
    pitch: int
    velocity: int


@dataclass(frozen=True)
class Glow:
    track_index: int
    pitch: int
    peak_intensity: float
    deactivated_at: float | None


def is_active(start_tick: int, duration: int, position_tick: int, loop_duration: int) -> bool:
    end_tick = start_tick + duration
    if end_tick <= loop_duration:
        return start_tick <= position_tick < end_tick
    wrapped_end = end_tick - loop_duration
    return position_tick >= start_tick or position_tick < wrapped_end


def active_notes(project: JsonDict | None, position: JsonDict | None) -> dict[NoteKey, ActiveNote]:
    if project is None or position is None:
        return {}
    current = project.get("current")
    if not current:
        return {}
    position_tick = position.get("tick")
    loop_duration = position.get("loop_duration")
    if position_tick is None or not loop_duration:
        return {}

    result: dict[NoteKey, ActiveNote] = {}
    for track_index, track in enumerate(current.get("tracks", [])):
        for start_tick, duration, pitch, velocity in track.get("notes", []):
            if is_active(start_tick, duration, position_tick, loop_duration):
                key = (track_index, start_tick, pitch)
                result[key] = ActiveNote(track_index=track_index, pitch=pitch, velocity=velocity)
    return result


def update_glow(
    previous: dict[NoteKey, Glow], active: dict[NoteKey, ActiveNote], now: float
) -> dict[NoteKey, Glow]:
    updated: dict[NoteKey, Glow] = {}
    for key, note in active.items():
        updated[key] = Glow(
            track_index=note.track_index,
            pitch=note.pitch,
            peak_intensity=note.velocity / 127,
            deactivated_at=None,
        )
    for key, glow in previous.items():
        if key in active:
            continue
        deactivated_at = glow.deactivated_at if glow.deactivated_at is not None else now
        if now - deactivated_at >= DECAY_SECONDS:
            continue
        updated[key] = Glow(
            track_index=glow.track_index,
            pitch=glow.pitch,
            peak_intensity=glow.peak_intensity,
            deactivated_at=deactivated_at,
        )
    return updated


def glow_intensity(glow: Glow, now: float) -> float:
    if glow.deactivated_at is None:
        return glow.peak_intensity
    elapsed = now - glow.deactivated_at
    fraction_remaining = max(0.0, 1.0 - elapsed / DECAY_SECONDS)
    return glow.peak_intensity * fraction_remaining


def track_color(track_index: int, intensity: float) -> tuple[int, int, int]:
    hue = (track_index * _HUE_STEP) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, max(0.0, min(1.0, intensity)))
    return (round(r * 255), round(g * 255), round(b * 255))


def render_plasma_row(glows: dict[NoteKey, Glow], now: float) -> list[tuple[int, int, int] | None]:
    row: list[tuple[int, int, int] | None] = [None] * PITCH_RANGE
    for glow in glows.values():
        intensity = glow_intensity(glow, now)
        if intensity <= 0:
            continue
        if 0 <= glow.pitch < PITCH_RANGE:
            row[glow.pitch] = track_color(glow.track_index, intensity)
    return row


class ProjectPoller:
    """Plasma's own independent `project` poll -- deliberately separate from
    the shared Poller (ADR-0005), with the same resilience contract as
    ticket 02: a failed poll clears `project` and sets `connected` False,
    retrying at the same interval with no backoff.
    """

    def __init__(self, client_factory: Callable[[], EngineClient], interval: float) -> None:
        self._client_factory = client_factory
        self.interval = interval
        self.project: JsonDict | None = None
        self.connected = False
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._poll())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _poll(self) -> None:
        client = self._client_factory()

        def on_success(project: JsonDict) -> None:
            self.project = project
            self.connected = True

        def on_failure(exc: EngineUnavailable) -> None:
            logger.warning("project poll failed: %s", exc)
            self.project = None
            self.connected = False

        await run_resilient_poll(client.project, self.interval, on_success, on_failure)


def _row_to_text(row: list[tuple[int, int, int] | None]) -> Text:
    text = Text()
    for cell in row:
        if cell is None:
            text.append(" ")
        else:
            r, g, b = cell
            text.append("█", style=Style(color=f"rgb({r},{g},{b})"))
    return text


class PlasmaView(Static):
    def __init__(self) -> None:
        super().__init__(WAITING_FOR_ENGINE_MESSAGE)
        self._glows: dict[NoteKey, Glow] = {}

    def update_from(self, poller: Poller, project_poller: ProjectPoller) -> None:
        if not poller.connected or not project_poller.connected:
            self._glows = {}
            self.update(WAITING_FOR_ENGINE_MESSAGE)
            return
        now = time.monotonic()
        active = active_notes(project_poller.project, poller.position)
        self._glows = update_glow(self._glows, active, now)
        self.update(_row_to_text(render_plasma_row(self._glows, now)))
