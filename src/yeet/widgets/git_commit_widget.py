from __future__ import annotations

from textual import containers, on
from textual.message import Message
from textual.widgets import Button, Input


class CommitMessageChanged(Message):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__()


class CommitRequested(Message):
    pass


class UndoRequested(Message):
    pass


class GitCommitWidget(containers.Vertical):
    def compose(self):
        with containers.Horizontal(id="commit-message-row"):
            yield Input(placeholder="Commit message", id="commit-message")
        with containers.Horizontal(id="commit-actions-row"):
            yield Button(
                "Commit",
                variant="primary",
                id="commit-button",
                disabled=True,
                compact=True,
            )
            yield Button(
                "↶",
                variant="default",
                id="revert-button",
                compact=True,
            )

    def commit_message(self) -> str:
        if not self.is_mounted:
            return ""
        return self.query_one("#commit-message", Input).value

    def set_commit_message(self, message: str) -> None:
        if not self.is_mounted:
            return
        self.query_one("#commit-message", Input).value = message

    def update_state(self, *, has_staged_changes: bool, in_progress: bool) -> None:
        if not self.is_mounted:
            return

        message = self.commit_message().strip()
        button = self.query_one("#commit-button", Button)
        revert_button = self.query_one("#revert-button", Button)

        if has_staged_changes:
            button.label = "Commit" if not in_progress else "Running..."
            can_run = bool(message) and not in_progress
        else:
            button.label = "Push" if not in_progress else "Running..."
            can_run = not in_progress

        button.disabled = not can_run
        revert_button.disabled = in_progress

    @on(Input.Changed, "#commit-message")
    def on_commit_message_changed(self, event: Input.Changed) -> None:
        self.post_message(CommitMessageChanged(event.value))

    @on(Input.Submitted, "#commit-message")
    def on_commit_message_submitted(self, _: Input.Submitted) -> None:
        self.post_message(CommitRequested())

    @on(Button.Pressed, "#commit-button")
    def on_commit_button_pressed(self, _: Button.Pressed) -> None:
        self.post_message(CommitRequested())

    @on(Button.Pressed, "#revert-button")
    def on_revert_button_pressed(self, _: Button.Pressed) -> None:
        self.post_message(UndoRequested())
