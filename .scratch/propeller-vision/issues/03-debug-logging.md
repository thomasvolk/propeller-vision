# 03 — Diagnostics: `--debug` file logging

**What to build:** A `--debug` flag that enables file logging for troubleshooting, without polluting the TUI (which owns the terminal) and without logging anything by default.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] Without `--debug`, nothing is written to a log file
- [x] With `--debug`, propeller-vision logs (via Python's `logging` module) to a file
- [x] An unhandled exception during a `--debug` session still crashes the process; textual restores the terminal on exit, and the traceback is printed to stderr after teardown
- [x] No in-app log viewer — file only
- [x] Test: run with `--debug`, trigger a loggable event (e.g. a disconnect from ticket 02, or a forced log call), assert the log file contains it; run without `--debug` and assert no log file is created/written
