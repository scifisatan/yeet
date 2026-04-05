from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual import containers
from textual import widgets
from textual.message import Message
from textual.reactive import reactive, var
from textual.widget import Widget


class SideBar(containers.Vertical):
    MIN_WIDTH = 24
    MAX_WIDTH = 72
    DEFAULT_WIDTH = 36

    active_panel_id = var("")
    sidebar_width = reactive(DEFAULT_WIDTH)

    class Dismiss(Message):
        pass

    @dataclass(frozen=True)
    class Panel:
        title: str
        widget: Widget
        flex: bool = False
        id: str | None = None

    def __init__(
        self,
        *panels: Panel,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.panels: list[SideBar.Panel] = [*panels]
        self._panel_ids = [self._build_panel_id(index, panel) for index, panel in enumerate(self.panels)]
        if self._panel_ids:
            self.active_panel_id = self._panel_ids[0]

    def _build_panel_id(self, index: int, panel: Panel) -> str:
        return panel.id or f"sidebar-panel-{index}"

    def focus_default(self) -> None:
        if button := self.query(".sidebar-tab").first():
            button.focus()

    def on_mount(self) -> None:
        self.trap_focus()
        self.watch_sidebar_width(self.sidebar_width)
        self._sync_tab_styles()

    def compose(self) -> ComposeResult:
        with containers.Horizontal(id="sidebar-tabs"):
            for panel, panel_id in zip(self.panels, self._panel_ids, strict=False):
                yield widgets.Button(
                    panel.title,
                    id=f"sidebar-tab-{panel_id}",
                    classes="sidebar-tab",
                    compact=True,
                )

        with widgets.ContentSwitcher(id="sidebar-switcher", initial=self.active_panel_id):
            for panel, panel_id in zip(self.panels, self._panel_ids, strict=False):
                with containers.Vertical(
                    id=panel_id,
                    classes="-flex" if panel.flex else "-fixed",
                ):
                    yield panel.widget

    @on(widgets.Button.Pressed, ".sidebar-tab")
    def on_sidebar_tab_pressed(self, event: widgets.Button.Pressed) -> None:
        if button_id := event.button.id:
            self.active_panel_id = button_id.removeprefix("sidebar-tab-")
            event.stop()

    def watch_active_panel_id(self, panel_id: str) -> None:
        if not self.is_mounted:
            return
        if switcher := self.query("#sidebar-switcher").first():
            switcher.current = panel_id
        self._sync_tab_styles()

    def _sync_tab_styles(self) -> None:
        for button in self.query(".sidebar-tab"):
            button.remove_class("-selected")
            if button.id == f"sidebar-tab-{self.active_panel_id}":
                button.add_class("-selected")

    def action_dismiss(self) -> None:
        self.post_message(self.Dismiss())

    def narrower(self) -> None:
        self.sidebar_width = max(self.MIN_WIDTH, self.sidebar_width - 2)

    def wider(self) -> None:
        self.sidebar_width = min(self.MAX_WIDTH, self.sidebar_width + 2)

    def reset_width(self) -> None:
        self.sidebar_width = self.DEFAULT_WIDTH

    def watch_sidebar_width(self, width: int) -> None:
        self.styles.width = width


if __name__ == "__main__":
    from textual.app import App, ComposeResult

    class SApp(App):
        def compose(self) -> ComposeResult:
            yield SideBar(
                SideBar.Panel("Hello", widgets.Label("Hello, World!")),
                SideBar.Panel(
                    "Files",
                    widgets.DirectoryTree(
                        "~/",
                    ),
                    flex=True,
                ),
                SideBar.Panel(
                    "Hello",
                    widgets.Static("Where there is a Will! " * 10),
                )
            )

    SApp().run()
