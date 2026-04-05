from __future__ import annotations

from textual import containers
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Collapsible


class CollapsibleWithActions(Collapsible):
    def __init__(
        self,
        *children: Widget,
        header_actions: tuple[Widget, ...] = (),
        title: str = "Toggle",
        collapsed: bool = True,
        collapsed_symbol: str = "▸",
        expanded_symbol: str = "▾",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(
            *children,
            title=title,
            collapsed=collapsed,
            collapsed_symbol=collapsed_symbol,
            expanded_symbol=expanded_symbol,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self._header_actions = list(header_actions)

    def compose(self) -> ComposeResult:
        with containers.Horizontal(classes="changes-header"):
            yield self._title
            yield from self._header_actions
        with self.Contents():
            yield from self._contents_list
