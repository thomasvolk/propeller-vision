Status: ready-for-agent

# propeller-vision: read-only console monitor with multiple views

## Problem Statement

Someone running propeller-engine has no way to see what the Loop is actually doing while it plays. The engine exposes a JSON socket protocol with state (Mode, bpm, Loop position, current/pending Project), but there's no console tool that surfaces it — you'd have to hand-craft socket requests (e.g. via `nc -U`) and read raw JSON to know whether the Loop is even running, what tick Position it's at, or what's currently playing.

## Solution

`propeller-vision` is a read-only console application that connects to a running Engine over its Unix-socket protocol and renders its state as a live terminal dashboard. It polls the Engine (never sends control/mutation commands — see ADR-0001) and renders one of several selectable Views:

- **Dashboard** (default): a Position playhead plus a status panel (Mode, bpm, current/pending Project header).
- **Plasma**: a note-reactive view where each Active Note flashes/pulses, positioned by pitch, colored by Track, sized by velocity, decaying after note-off.

The View is chosen once via a CLI flag at startup and stays fixed for the session.

## User Stories

1. As an engine operator, I want to see whether the Loop is currently running, so that I know if my engine process is alive and doing something.
2. As an engine operator, I want to see the current Loop Position as a moving playhead, so that I can tell at a glance where in the Loop playback currently is.
3. As an engine operator, I want to see the current bpm, so that I can confirm the tempo matches what I expect.
4. As an engine operator, I want to see the Engine's Mode (standalone/clock/sync), so that I understand which control surface is driving playback.
5. As an engine operator running in sync mode, I want to see the sync clock state (waiting/tracking/lost), so that I can diagnose sync problems.
6. As an engine operator, I want to see whether a Project is currently loaded, so that I know if there's anything for the Loop to play.
7. As an engine operator, I want to see whether a Project change is pending, so that I know a change will take effect at the next loop boundary.
8. As a user starting propeller-vision, I want it to default to the Dashboard view when I don't specify one, so that I get sensible behavior without needing to know the flag syntax.
9. As a user starting propeller-vision, I want to choose the Plasma view via a CLI flag, so that I can watch a note-reactive visualization instead of the Dashboard.
10. As a user watching the Plasma view, I want each currently-sounding note to flash, so that I can see the music happening in real time.
11. As a user watching the Plasma view, I want a note's flash positioned by its pitch, so that low and high notes are visually distinguishable.
12. As a user watching the Plasma view, I want a note's flash colored by its Track, so that I can tell which instrument is playing which note when multiple tracks sound together.
13. As a user watching the Plasma view, I want a note's flash intensity to reflect its velocity, so that louder notes stand out visually.
14. As a user watching the Plasma view, I want a note's flash to last roughly as long as the note itself (plus a brief fade), so that the visualization reflects the actual rhythm of the music rather than flattening every note to the same blip.
15. As a user on an older terminal without truecolor support, I want the Plasma view to still render (in degraded 256-color form), so that I'm not blocked from using the tool at all.
16. As a user, I want propeller-vision to keep running and show a clear "disconnected" state if the Engine isn't reachable (not yet started, or restarted mid-session), so that the tool doesn't crash or hang when the engine isn't available.
17. As a user, I want propeller-vision to automatically resume showing live state once the Engine becomes reachable again, so that I don't have to restart the tool after an engine restart.
18. As a user, I want to point propeller-vision at a non-default socket path via the `PROPELLER_SOCK` environment variable, so that it matches whatever the engine itself is configured to use.
19. As a user, I want to override the socket path via a `--socket` CLI flag, so that I can point at a specific engine instance without changing my environment.
20. As a user, I want to control how frequently the Position is polled via a `--position-interval` flag (default 100ms), so that I can tune smoothness vs. socket traffic.
21. As a user, I want to control how frequently status/project are polled via a `--status-interval` flag (default 1s), so that I can tune freshness vs. socket traffic independently of the position poll.
22. As a user debugging a problem, I want to pass a `--debug` flag to enable file logging, so that I can inspect what happened without polluting the TUI or needing logging on by default.
23. As a maintainer, I want the Plasma view's Active Note computation kept out of the shared polling layer, so that the core poller stays free of note-level concerns and the boundary from ADR-0002/0004 is respected in the code structure, not just the docs.
24. As a maintainer, I want only one shared poller for status/position regardless of which View is active, so that adding a future View doesn't require re-implementing connection/poll logic.
25. As a packager, I want propeller-vision installable as a `propeller-vision` console-script via `uv`/`pyproject.toml`, so that it can be installed with standard Python tooling (e.g. `uv tool install .` / `pipx install .`).

## Implementation Decisions

- **Scope**: propeller-vision is read-only. It only issues `status`, `project`, and `get_position` queries against the Engine's socket protocol; it never issues control/mutation commands (`loop-start`, `loop-stop`, `set-bpm`, `set-mode`, `create-project`, `modify-project`, `stop`, clock commands). See ADR-0001.
- **Transport**: Unix domain socket. Default path `/tmp/propeller.sock`, overridden by the `PROPELLER_SOCK` environment variable, further overridden by a `--socket` CLI flag (flag wins over env var). Each request is one connection: connect, write one newline-terminated JSON command, read one JSON response line, disconnect — per the engine's protocol, there is no persistent session or subscribe/push mechanism.
- **Shared polling layer**: a single, View-agnostic poller issues `status` and `get_position` on independent timers and exposes the latest values to whichever View is active. Poll intervals: `get_position` at `--position-interval` (default 100ms / 10Hz); `status`/`project` together at `--status-interval` (default 1s / 1Hz). See ADR-0005.
- **View selection**: a `--view` CLI flag selects `dashboard` (default) or `plasma`. The View is fixed for the process lifetime — no runtime switching between Views in a single session.
- **Dashboard view**: renders the Position as a playhead/progress bar scaled against `loop_duration`, plus a status panel showing Mode, bpm, `clock_state`, `sync_clock_state` (only meaningful in `sync` Mode), and current/pending Project header info (no Track/note detail). See ADR-0002.
- **Plasma view**: additionally fetches `project` itself (not via the shared layer) to obtain Track/note data, and derives **Active Notes** by cross-referencing each Track's notes (`[start_tick, duration, pitch, velocity]`) against the current Position from the shared poller — a note is active when Position falls within `[start_tick, start_tick + duration)`, with loop-wraparound handled at the Loop boundary. See ADR-0004.
  - Rendering per Active Note: horizontal (or otherwise spatial) position mapped from pitch; color/hue assigned per-Track in Track order (stable per session); intensity/brightness mapped from velocity; the flash is lit for the note's actual duration-in-ticks (converted to wall-clock via current bpm) and then fades over a short fixed decay (~100ms) after note-off.
  - Color depth: use 24-bit truecolor when the terminal advertises support (textual's own detection); otherwise fall back to the nearest 256-color approximation. No hard truecolor requirement, no error on unsupported terminals.
  - No piano-roll/track-editor style rendering of full note detail — only the derived Active Note signal is consumed. See ADR-0002 (superseded in part by ADR-0004) and ADR-0004.
- **Resilience**: on connection failure to the Engine (socket missing, connection refused, etc.), don't exit — surface a visible "disconnected" indicator in whichever View is active and keep retrying at the existing poll interval (no separate backoff schedule). Resume normal rendering automatically once a poll succeeds again.
- **Diagnostics**: no logging by default. A `--debug` flag enables file logging (e.g. via Python's `logging` module to a log file). Unhandled exceptions are allowed to crash the process; textual restores the terminal on exit, and the traceback prints to stderr after teardown. No in-app log viewer in v1.
- **Stack/packaging**: Python 3.11+, `textual` for the TUI, `uv` + `pyproject.toml` for dependency management and packaging, exposing a `propeller-vision` console-script entry point. See ADR-0003.
- **Quit control**: standard textual keybinding to quit (e.g. `q` / `ctrl+c`) — not a distinct design decision, just the framework default.

## Testing Decisions

- **Seam**: a fake/test Engine — a small Unix-socket server started by the test suite, implementing the protocol subset propeller-vision actually uses (`status`, `project`, `get_position`, and connection-refused/absent-socket scenarios). Tests configure it to return specific canned responses (or to be unreachable) and point propeller-vision at it via `--socket`/`PROPELLER_SOCK`.
- **Assertions**: drive the app via textual's `App.run_test()` / `Pilot` test harness and assert on rendered widget state/text (e.g. the Dashboard panel shows the expected bpm/mode, the "disconnected" indicator appears when the fake engine is stopped, a Plasma flash appears for a note the fake engine reports as in-progress at the current Position). Only externally observable behavior is asserted — not internal poller/view class internals.
- **Coverage**: this single seam is the one place across the codebase where tests attach — no additional mocking of the socket client class or of view-internal state is needed. This favors one seam at the highest possible point (the real Engine protocol boundary) per project testing conventions.
- **Prior art**: none yet — this is the first test suite in the repo. The fake-Engine-server approach should become the pattern future features reuse rather than introducing new seams per feature.

## Out of Scope

- Any control/mutation of the Engine (starting/stopping the Loop, changing bpm/mode, creating/modifying Projects) — propeller-vision is permanently read-only (ADR-0001).
- Full track/note detail rendering (a piano-roll or track-editor style view) — only the derived Active Note signal is used, by Plasma only (ADR-0002, ADR-0004).
- Runtime View switching within a single session — View is chosen once at startup.
- BPM-derived or otherwise dynamic poll-interval adjustment — intervals are fixed (per-flag) for the process lifetime.
- A separate, faster poll interval specifically for Plasma — it reuses `--position-interval`, accepting that very short notes could in principle be missed between polls.
- An in-app log viewer or debug console — `--debug` only writes to a file.
- Any views beyond Dashboard and Plasma — no others have been specified yet.
- Authentication/encryption of the Engine connection — the protocol itself has none (per the engine's own docs), and this is unchanged by propeller-vision.

## Further Notes

- Domain vocabulary for this feature (Engine, Loop, Position, Project, Track, Mode, View, Dashboard, Plasma View, Active Note) is defined in `CONTEXT.md` at the repo root — use these terms rather than synonyms.
- Relevant ADRs: `docs/adr/0001-read-only-monitor.md`, `docs/adr/0002-no-track-detail-in-v1.md` (superseded in part), `docs/adr/0003-python-textual.md`, `docs/adr/0004-active-notes-in-scope.md`, `docs/adr/0005-shared-polling-layer.md`.
- The engine's protocol is one-shot-per-connection with no push/subscribe mechanism, which is why polling (rather than event-driven updates) is the architecture throughout.
