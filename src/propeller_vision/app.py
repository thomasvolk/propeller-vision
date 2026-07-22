"""The propeller-vision textual App: wires the shared Poller to the active View."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches

from propeller_vision.dashboard import Dashboard
from propeller_vision.plasma import PlasmaView, ProjectPoller
from propeller_vision.poller import Poller


class PropellerVisionApp(App[None]):
    BINDINGS = [
        Binding("ctrl+q", "noop", show=False, system=True, priority=True),
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
    ]

    def action_noop(self) -> None:
        pass

    def __init__(
        self,
        poller: Poller,
        view: str = "dashboard",
        project_poller: ProjectPoller | None = None,
    ) -> None:
        if view == "plasma" and project_poller is None:
            raise ValueError("view='plasma' requires a project_poller")
        super().__init__()
        self.poller = poller
        self.view = view
        self.project_poller = project_poller

    def compose(self) -> ComposeResult:
        if self.view == "plasma":
            yield PlasmaView()
        else:
            yield Dashboard()

    def on_mount(self) -> None:
        self.poller.start()
        if self.project_poller is not None:
            self.project_poller.start()
        self.set_interval(self.poller.position_interval, self._refresh)

    def _refresh(self) -> None:
        try:
            if self.view == "plasma":
                assert self.project_poller is not None
                self.query_one(PlasmaView).update_from(self.poller, self.project_poller)
            else:
                self.query_one(Dashboard).update_from(self.poller)
        except NoMatches:
            # The refresh timer can fire once more while the app is tearing
            # down and the widget tree (or its children) is already gone.
            pass

    async def on_unmount(self) -> None:
        await self.poller.stop()
        if self.project_poller is not None:
            await self.project_poller.stop()
