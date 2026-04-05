from __future__ import annotations

from textual import containers, on
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmModal(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "Cancel")]
    CSS_PATH = "confirm_modal.tcss"

    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self._title = title
        self._body = body

    def compose(self):
        with containers.Vertical(id="confirm-dialog"):
            yield Static(self._title, id="confirm-title")
            yield Static(self._body, id="confirm-body")
            with containers.Horizontal(id="confirm-buttons"):
                yield Static("", id="confirm-buttons-spacer")
                yield Button("Cancel", id="confirm-cancel", compact=True)
                yield Button(
                    "Continue",
                    variant="primary",
                    id="confirm-continue",
                    compact=True,
                )

    @on(Button.Pressed, "#confirm-cancel")
    def on_cancel_pressed(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#confirm-continue")
    def on_continue_pressed(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)