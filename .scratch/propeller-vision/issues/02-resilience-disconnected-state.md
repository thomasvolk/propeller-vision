# 02 — Resilience: disconnected state and auto-recovery

**What to build:** propeller-vision no longer crashes or hangs when the Engine is unreachable — at startup or mid-session. The active View shows a clear "disconnected" indicator, and the shared polling layer keeps retrying at its existing poll interval (no separate backoff schedule) until the Engine responds again, at which point rendering resumes automatically and the indicator clears.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] Starting propeller-vision when the socket doesn't exist (Engine never started) shows the disconnected indicator instead of crashing
- [x] Stopping the fake Engine mid-session causes the active View to show the disconnected indicator on the next failed poll
- [x] While disconnected, the shared polling layer keeps retrying at the configured `--position-interval`/`--status-interval` rates — no exponential backoff
- [x] Restarting the fake Engine causes propeller-vision to resume normal rendering automatically, with no restart of propeller-vision itself required
- [x] Test: using the fake-Engine harness from ticket 01, start the app connected, stop the fake Engine, assert the disconnected indicator appears, restart the fake Engine, assert normal rendering resumes — all via the `Pilot` harness, asserting on rendered output only
