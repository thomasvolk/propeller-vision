from __future__ import annotations

import argparse
import os
from typing import Sequence

from propeller_vision.app import PropellerVisionApp
from propeller_vision.poller import Poller
from propeller_vision.protocol import EngineClient

DEFAULT_SOCKET_PATH = "/tmp/propeller.sock"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="propeller-vision")
    parser.add_argument(
        "--socket",
        default=None,
        help=f"Path to the engine's Unix socket (default: $PROPELLER_SOCK or {DEFAULT_SOCKET_PATH})",
    )
    parser.add_argument(
        "--view",
        choices=["dashboard"],
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
    args = parser.parse_args(argv)
    if args.socket is None:
        args.socket = os.environ.get("PROPELLER_SOCK", DEFAULT_SOCKET_PATH)
    return args


def main() -> None:
    args = parse_args()
    poller = Poller(
        client_factory=lambda: EngineClient(args.socket),
        position_interval=args.position_interval,
        status_interval=args.status_interval,
    )
    app = PropellerVisionApp(poller)
    app.run()
