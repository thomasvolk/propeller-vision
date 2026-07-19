"""The propeller-vision textual App: wires the shared Poller to the active View."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.css.query import NoMatches

from propeller_vision.dashboard import Dashboard
from propeller_vision.poller import Poller


class PropellerVisionApp(App[None]):
    def __init__(self, poller: Poller) -> None:
        super().__init__()
        self.poller = poller

    def compose(self) -> ComposeResult:
        yield Dashboard()

    def on_mount(self) -> None:
        self.poller.start()
        self.set_interval(self.poller.position_interval, self._refresh)

    def _refresh(self) -> None:
        try:
            self.query_one(Dashboard).update_from(self.poller)
        except NoMatches:
            # The refresh timer can fire once more while the app is tearing
            # down and the widget tree (or its children) is already gone.
            pass

    async def on_unmount(self) -> None:
        await self.poller.stop()
