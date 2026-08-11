from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Sequence

from propeller_vision.app import PropellerVisionApp
from propeller_vision.plasma import ProjectPoller
from propeller_vision.poller import Poller
from propeller_vision.protocol import EngineClient

DEFAULT_SOCKET_PATH = "/tmp/propeller.sock"
DEFAULT_LOG_PATH = Path.home() / ".propeller-vision.log"

# Parent of all propeller_vision module loggers -- configuring handlers here
# (rather than on the root logger) keeps --debug from affecting output from
# other libraries, and propagate=False keeps us off the root logger entirely
# so nothing can leak to stderr and corrupt the TUI's terminal control.
LOGGER_NAME = "propeller_vision"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="propeller-vision")
    parser.add_argument(
        "--socket",
        default=None,
        help=f"Path to the engine's Unix socket (default: $PROPELLER_SOCK or {DEFAULT_SOCKET_PATH})",
    )
    parser.add_argument(
        "--view",
        choices=["dashboard", "plasma", "space"],
        default="dashboard",
        help="Which View to render (default: dashboard)",
    )
    parser.add_argument(
        "--position-interval",
        type=float,
        default=0.1,
        help="Position poll interval in seconds (default: 0.1)",
    )
    parser.add_argument(
        "--status-interval",
        type=float,
        default=1.0,
        help="Status/project poll interval in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--flow-speed",
        type=float,
        default=0.5,
        help="Plasma view background flow speed, as a multiplier of the BPM-derived rate (default: 0.5)",
    )
    parser.add_argument(
        "--scroll-speed",
        type=float,
        default=1.0,
        help="Space view scroll speed, as a multiplier of the BPM-derived rate (default: 1.0)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=f"Enable file logging for troubleshooting (writes to {DEFAULT_LOG_PATH})",
    )
    args = parser.parse_args(argv)
    if args.socket is None:
        args.socket = os.environ.get("PROPELLER_SOCK", DEFAULT_SOCKET_PATH)
    return args


def configure_logging(debug: bool, log_path: Path = DEFAULT_LOG_PATH) -> None:
    """Off by default; --debug turns on file logging only, never a console handler.

    The TUI owns the terminal, so nothing here may write to stderr/stdout --
    a NullHandler (rather than leaving the logger unconfigured) guarantees
    that even if root logging is configured elsewhere, we neither write a
    file nor fall back to logging's stderr "handler of last resort".
    """
    logger = logging.getLogger(LOGGER_NAME)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    logger.propagate = False

    if not debug:
        logger.addHandler(logging.NullHandler())
        return

    handler = logging.FileHandler(log_path)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def main() -> None:
    args = parse_args()
    configure_logging(args.debug)
    logger = logging.getLogger(__name__)
    logger.info("propeller-vision starting (socket=%s, view=%s)", args.socket, args.view)
    poller = Poller(
        client_factory=lambda: EngineClient(args.socket),
        position_interval=args.position_interval,
        status_interval=args.status_interval,
    )
    project_poller = None
    if args.view in ("plasma", "space"):
        project_poller = ProjectPoller(
            client_factory=lambda: EngineClient(args.socket),
            interval=args.status_interval,
        )
    app = PropellerVisionApp(
        poller,
        view=args.view,
        project_poller=project_poller,
        flow_speed=args.flow_speed,
        scroll_speed=args.scroll_speed,
    )
    app.run()
