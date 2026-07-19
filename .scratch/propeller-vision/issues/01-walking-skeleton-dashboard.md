# 01 — Walking skeleton: Dashboard view, live

**What to build:** `propeller-vision` installs and runs, showing a live Dashboard against a real or fake propeller-engine. The user gets a moving Position playhead and a status panel (Mode, bpm, clock_state, sync_clock_state, current/pending Project header), driven by a shared polling layer that queries the Engine's `get_position` and `status`/`project` on independent timers. This ticket assumes the Engine is reachable for the whole session — no disconnect handling (that's ticket 02).

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] `pyproject.toml` (managed with `uv`) exposes a `propeller-vision` console-script entry point; `uv tool install .` (or equivalent) produces a runnable `propeller-vision` command; targets Python 3.11+
- [ ] Socket client implements the Engine's one-shot request/response protocol subset: connect, write one newline-terminated JSON command, read one JSON response line, disconnect — for `status`, `project`, and `get_position` (`get_position` uses `"type"` not `"command"`)
- [ ] Socket path resolves from `PROPELLER_SOCK` env var (default `/tmp/propeller.sock`), overridable by a `--socket` CLI flag (flag wins)
- [ ] `--view` flag exists and accepts `dashboard` (default); other values are rejected for now (plasma lands in ticket 04)
- [ ] `--position-interval` flag (default 100ms) controls the `get_position` poll rate; `--status-interval` flag (default 1s) controls the `status`/`project` poll rate; both are independent of each other
- [ ] Shared polling layer is View-agnostic — it fetches position and status/project state without any knowledge of which View is rendering it
- [ ] Dashboard renders a Position playhead scaled against `loop_duration`
- [ ] Dashboard renders Mode, bpm, `clock_state`; renders `sync_clock_state` only when Mode is `sync`
- [ ] Dashboard renders current/pending Project header info (e.g. whether a project is loaded/pending) — no Track/note-level detail
- [ ] A fake-Engine Unix-socket test server exists in the test suite, implementing `status`/`project`/`get_position` with configurable canned responses
- [ ] Tests drive the app via textual's `App.run_test()`/`Pilot` against the fake Engine and assert on rendered Dashboard content (playhead position, status panel fields) — no mocking of internal classes
