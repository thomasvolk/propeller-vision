"""The Plasma View: a continuously flowing field that Active Notes perturb.

Active Notes are derived by cross-referencing each Track's note data
against the current Position -- computed here, not in the shared Poller
(ADR-0004/ADR-0005 draw that boundary at the view, not the data layer).

Rendering is decoupled from the poll cadence: `update_from` (called on
each poll tick) only updates which notes are sounding (`_glows`); a
separate per-frame timer redraws the field on its own clock, so the flow
stays smooth regardless of how often the Engine is polled.
"""

from __future__ import annotations

import asyncio
import colorsys
import logging
import math
import time
from dataclasses import dataclass
from typing import Callable, Iterable

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

# How long a ripple keeps fading after the note stops sounding.
DECAY_SECONDS = 0.1

# Golden-angle hue step: gives evenly spread, distinguishable per-Track hues
# regardless of how many Tracks a Project has.
_HUE_STEP = 0.618033988749895

# MIDI pitches run 0-127; used to place each note's ripple horizontally.
PITCH_RANGE = 128

# Animation frame cadence -- deliberately decoupled from the poll interval
# so the flow reads as smooth motion, not a series of poll-driven jumps.
FRAME_INTERVAL = 1 / 20

# Idle (no nearby note) HSV: a calm, dim baseline that notes brighten out of.
IDLE_SATURATION = 0.5
IDLE_VALUE = 0.4

# How tightly a ripple's rings are spaced, and how fast they travel outward.
RIPPLE_SPREAD = 6.0
RIPPLE_SPEED = 6.0

# How far (in cells) a ripple's color/brightness influence reaches before
# fading to nothing -- keeps a note's presence spatially legible rather than
# tinting the whole screen.
RIPPLE_REACH = 16.0


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


_NOT_RUNNING_CLOCK_STATES = {"paused", "stopped"}


def clock_is_running(status: JsonDict | None) -> bool:
    """Whether the Engine's transport is actively advancing -- the flow
    freezes only on an explicit paused/stopped `clock_state`. Missing status
    (or a status without `clock_state`) defaults to running, since that's an
    incomplete read rather than a confirmed pause."""
    if status is None:
        return True
    return status.get("clock_state") not in _NOT_RUNNING_CLOCK_STATES


def music_rate(bpm: float | None) -> float | None:
    """Converts BPM into beats-per-second -- the rate `t` advances at, so the
    base flow's speed is directly proportional to tempo (a 120 BPM track
    flows twice as fast as a 60 BPM one). None (missing/non-positive BPM)
    means the rate is unknown, and the flow should freeze rather than guess."""
    if bpm is None or bpm <= 0:
        return None
    return bpm / 60.0


def track_hue(track_index: int) -> float:
    return (track_index * _HUE_STEP) % 1.0


def base_field_value(x: float, y: float, t: float) -> float:
    """The calm, note-independent flow -- same sine-sum shape as the ascii_plasma.py demo."""
    return (
        math.sin(x / 8.0 + t)
        + math.sin(y / 4.0 + t)
        + math.sin((x + y) / 8.0 + t)
        + math.sin(math.sqrt(x * x + y * y) / 4.0 + t)
    )


def pitch_source(pitch: int, cols: int, lines: int) -> tuple[float, float]:
    """Where a note's ripple originates: horizontal position by pitch, fixed mid-row."""
    x_center = (pitch / (PITCH_RANGE - 1)) * max(cols - 1, 0)
    y_center = lines / 2.0
    return x_center, y_center


def ripple_distance(pitch: int, x: float, y: float, cols: int, lines: int) -> float:
    x_center, y_center = pitch_source(pitch, cols, lines)
    return math.hypot(x - x_center, y - y_center)


def ripple_wave(pitch: int, x: float, y: float, cols: int, lines: int, t: float, intensity: float) -> float:
    """Outward-travelling rings from a note's pitch-position, added into the flow field."""
    distance = ripple_distance(pitch, x, y, cols, lines)
    return intensity * math.sin(distance / RIPPLE_SPREAD - t * RIPPLE_SPEED)


def ripple_weight(pitch: int, x: float, y: float, cols: int, lines: int, intensity: float) -> float:
    """How strongly a note's Track color/brightness should show at this cell."""
    distance = ripple_distance(pitch, x, y, cols, lines)
    falloff = max(0.0, 1.0 - distance / RIPPLE_REACH)
    return intensity * falloff


def blend_hue(base_hue: float, target_hue: float, weight: float) -> float:
    """Blend toward target_hue by the shortest path around the hue circle."""
    weight = max(0.0, min(1.0, weight))
    diff = (target_hue - base_hue + 0.5) % 1.0 - 0.5
    return (base_hue + diff * weight) % 1.0


def pixel_hsv(base_hue: float, best_track_hue: float, weight: float) -> tuple[float, float, float]:
    weight = max(0.0, min(1.0, weight))
    hue = blend_hue(base_hue % 1.0, best_track_hue, weight)
    saturation = IDLE_SATURATION + (1.0 - IDLE_SATURATION) * weight
    value = IDLE_VALUE + (1.0 - IDLE_VALUE) * weight
    return hue, saturation, value


def render_pixel(
    x: int, y: int, cols: int, lines: int, t: float, glows: Iterable[Glow], now: float
) -> tuple[int, int, int]:
    v = base_field_value(x, y, t)
    best_weight = 0.0
    best_hue = 0.0
    for glow in glows:
        intensity = glow_intensity(glow, now)
        if intensity <= 0:
            continue
        v += ripple_wave(glow.pitch, x, y, cols, lines, t, intensity)
        weight = ripple_weight(glow.pitch, x, y, cols, lines, intensity)
        if weight > best_weight:
            best_weight = weight
            best_hue = track_hue(glow.track_index)
    base_hue = (v + 4) / 8.0
    hue, saturation, value = pixel_hsv(base_hue, best_hue, best_weight)
    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
    return (round(r * 255), round(g * 255), round(b * 255))


def render_plasma_frame(cols: int, lines: int, t: float, glows: dict[NoteKey, Glow], now: float) -> Text:
    glow_list = list(glows.values())
    text = Text()
    for y in range(lines):
        for x in range(cols):
            r, g, b = render_pixel(x, y, cols, lines, t, glow_list, now)
            text.append(" ", style=Style(bgcolor=f"rgb({r},{g},{b})"))
        if y < lines - 1:
            text.append("\n")
    return text


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


class PlasmaView(Static):
    DEFAULT_CSS = """
    PlasmaView {
        width: 100%;
        height: 100%;
    }
    """

    def __init__(self, flow_speed: float = 1.0) -> None:
        super().__init__(WAITING_FOR_ENGINE_MESSAGE)
        self._flow_speed = flow_speed
        self._glows: dict[NoteKey, Glow] = {}
        self._connected = False
        self._running = False
        self._bpm: float | None = None
        self._music_time = 0.0
        self._last_tick_at: float | None = None
        self._has_rendered_frame = False

    def on_mount(self) -> None:
        self.set_interval(FRAME_INTERVAL, self._draw_frame)

    def update_from(self, poller: Poller, project_poller: ProjectPoller) -> None:
        if not poller.connected or not project_poller.connected:
            self._connected = False
            self._glows = {}
            return
        self._connected = True
        now = time.monotonic()
        self._running = clock_is_running(poller.status)
        self._bpm = poller.status.get("bpm") if poller.status else None
        active = active_notes(project_poller.project, poller.position)
        self._glows = update_glow(self._glows, active, now)

    def _advance_music_time(self, now: float) -> None:
        # Reset the tick reference on every call so a pause never counts
        # toward the next dt -- resuming continues from where it froze
        # instead of jumping forward by however long it was paused.
        if self._running:
            rate = music_rate(self._bpm)
            if rate is not None and self._last_tick_at is not None:
                self._music_time += (now - self._last_tick_at) * rate * self._flow_speed
        self._last_tick_at = now

    def _draw_frame(self) -> None:
        now = time.monotonic()
        if not self._connected:
            self.update(WAITING_FOR_ENGINE_MESSAGE, layout=False)
            self._has_rendered_frame = False
            self._last_tick_at = None
            return
        self._advance_music_time(now)
        # Freeze once at least one real frame is on screen; a fresh connection
        # that's paused from the start still needs its first frame drawn.
        if not self._running and self._has_rendered_frame:
            return
        cols, lines = self.size.width, self.size.height
        if cols <= 0 or lines <= 0:
            return
        frame = render_plasma_frame(cols, lines, self._music_time, self._glows, now)
        self.update(frame, layout=False)
        self._has_rendered_frame = True
