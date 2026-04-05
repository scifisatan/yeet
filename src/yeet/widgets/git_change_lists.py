from __future__ import annotations

from pathlib import Path

from textual import containers, on
from textual.binding import Binding
from textual.content import Content
from textual.message import Message
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from yeet.visuals.columns import Columns, Row
from yeet.widgets.collapsible_with_actions import CollapsibleWithActions
from yeet.widgets.git_change_models import GitChange


class ToggleStageRequested(Message):
    def __init__(self, section: str, option_id: str) -> None:
        self.section = section
        self.option_id = option_id
        super().__init__()


class FileActionRequested(Message):
    def __init__(self, section: str, option_id: str, action: str) -> None:
        self.section = section
        self.option_id = option_id
        self.action = action
        super().__init__()


class ChangeSelected(Message):
    def __init__(self, section: str, option_id: str) -> None:
        self.section = section
        self.option_id = option_id
        super().__init__()


class StageAllRequested(Message):
    pass


class UnstageAllRequested(Message):
    pass


class DiscardAllRequested(Message):
    pass


class GitChangeList(OptionList):
    BINDINGS = [
        Binding("space", "toggle_stage", "Stage/Unstage"),
        Binding("plus,equal", "stage_file", "Stage file"),
        Binding("minus", "minus_action", "Unstage/Discard file"),
    ]

    def __init__(self, section: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.section = section

    def _highlighted_option_id(self) -> str | None:
        option = self.highlighted_option
        if option is None or option.id is None or option.id.endswith("-summary"):
            return None
        return option.id

    def action_toggle_stage(self) -> None:
        option_id = self._highlighted_option_id()
        if option_id is None:
            return
        parent = self.query_ancestor(GitChangeSectionBase)
        parent.post_message(ToggleStageRequested(self.section, option_id))

    def action_stage_file(self) -> None:
        option_id = self._highlighted_option_id()
        if option_id is None:
            return
        parent = self.query_ancestor(GitChangeSectionBase)
        parent.post_message(FileActionRequested(self.section, option_id, "plus"))

    def action_minus_action(self) -> None:
        option_id = self._highlighted_option_id()
        if option_id is None:
            return
        parent = self.query_ancestor(GitChangeSectionBase)
        parent.post_message(FileActionRequested(self.section, option_id, "minus"))

    async def _on_click(self, event) -> None:
        clicked_option: int | None = event.style.meta.get("option")
        if clicked_option is None:
            return

        try:
            option = self.options[clicked_option]
        except IndexError:
            return

        if option.disabled:
            return

        option_id = option.id or ""
        self.highlighted = clicked_option
        if not option_id or option_id.endswith("-summary"):
            self.action_select()
            return

        action_width = 7 if self.section == "local" else 4
        action_start = max(0, self.scrollable_content_region.width - action_width)
        if event.x >= action_start:
            parent = self.query_ancestor(GitChangeSectionBase)
            if self.section == "local":
                plus_boundary = action_start + 3
                action = "plus" if event.x < plus_boundary else "minus"
            else:
                action = "minus"
            parent.post_message(FileActionRequested(self.section, option_id, action))
            event.stop()
            return

        self.action_select()


class GitChangeSectionBase(containers.Vertical):
    SECTION = ""
    TITLE = "Changes"
    EMPTY_TEXT = "No changes"
    SECTION_ID = "changes-section"
    OPTIONS_ID = "changes-options"
    EMPTY_ID = "changes-empty"

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._entries: list[GitChange] = []
        self._changes: dict[str, GitChange] = {}

    def compose(self):
        with CollapsibleWithActions(
            title=self.TITLE,
            collapsed=False,
            collapsed_symbol="▸",
            expanded_symbol="▾",
            header_actions=self._header_actions(),
            id=self.SECTION_ID,
            classes="changes-section",
        ):
            yield GitChangeList(section=self.SECTION, id=self.OPTIONS_ID)
            yield Static(self.EMPTY_TEXT, id=self.EMPTY_ID, classes="section-empty")

    def _header_actions(self) -> tuple[Button, ...]:
        return ()

    @staticmethod
    def _status_icon(status: str) -> str:
        icon_map = {
            "modified": "M",
            "added": "A",
            "deleted": "D",
            "renamed": "R",
            "untracked": "?",
            "changed": "*",
        }
        return icon_map.get(status, "*")

    @staticmethod
    def _language_icon(path: str) -> str:
        suffix = Path(path).suffix.lower()
        icon_map: dict[str, str] = {
            ".py": "🐍",
            ".tcss": "🎨",
            ".md": "📝",
            ".json": "🧩",
            ".toml": "⚙",
            ".yaml": "📄",
            ".yml": "📄",
        }
        return icon_map.get(suffix, "•")

    def _render_change_label(
        self,
        change: GitChange,
        *,
        section: str,
    ) -> Row:
        icon = self._status_icon(change.status)
        if change.old_path is not None:
            path_text = f"{change.old_path} -> {change.path}"
        else:
            path_text = change.path

        lang_icon = self._language_icon(change.path)
        columns = Columns("auto", "flex", "auto")
        actions = (
            Content.from_markup("[$text-success][+][/] [$text-error][-][/]")
            if section == "local"
            else Content.from_markup("[$text-error][-][/]")
        )
        return columns.add_row(
            Content.styled(f"  {icon} {lang_icon}", "$text-secondary"),
            Content(path_text),
            actions,
        )

    def set_rows(self, rows: list[GitChange]) -> None:
        self._entries = rows
        option_list = self.query_one(f"#{self.OPTIONS_ID}", OptionList)
        empty_widget = self.query_one(f"#{self.EMPTY_ID}", Static)

        option_list.clear_options()
        self._changes.clear()

        if not rows:
            empty_widget.update(self.EMPTY_TEXT)
            option_list.display = False
            empty_widget.display = True
            self._sync_title()
            return

        option_list.display = True
        empty_widget.display = False

        for index, change in enumerate(rows, start=1):
            option_id = f"{self.SECTION}-change-{index}"
            self._changes[option_id] = change
            option_list.add_option(
                Option(
                    self._render_change_label(change, section=self.SECTION),
                    id=option_id,
                )
            )

        self._sync_title()

    def _sync_title(self) -> None:
        section = self.query_one(f"#{self.SECTION_ID}", CollapsibleWithActions)
        section.title = f"{self.TITLE} ({len(self._entries)})"

    def get_change(self, option_id: str) -> GitChange | None:
        return self._changes.get(option_id)

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != self.OPTIONS_ID:
            return
        option_id = event.option_id or ""
        if not option_id or option_id.endswith("-summary"):
            return
        self.post_message(ChangeSelected(self.SECTION, option_id))


class GitStagedList(GitChangeSectionBase):
    SECTION = "staged"
    TITLE = "Staged Changes"
    EMPTY_TEXT = "No staged changes"
    SECTION_ID = "staged-section"
    OPTIONS_ID = "staged-options"
    EMPTY_ID = "staged-empty"

    def _header_actions(self) -> tuple[Button, ...]:
        return (
            Button("-", id="staged-unstage-all", classes="section-action", compact=True),
        )

    @on(Button.Pressed, "#staged-unstage-all")
    def on_staged_unstage_all_pressed(self) -> None:
        self.post_message(UnstageAllRequested())


class GitChangesList(GitChangeSectionBase):
    SECTION = "local"
    TITLE = "Local Changes"
    EMPTY_TEXT = "No local changes"
    SECTION_ID = "local-section"
    OPTIONS_ID = "local-options"
    EMPTY_ID = "local-empty"

    def _header_actions(self) -> tuple[Button, ...]:
        return (
            Button("+", id="local-stage-all", classes="section-action", compact=True),
            Button("-", id="local-discard-all", classes="section-action", compact=True),
        )

    @on(Button.Pressed, "#local-stage-all")
    def on_local_stage_all_pressed(self) -> None:
        self.post_message(StageAllRequested())

    @on(Button.Pressed, "#local-discard-all")
    def on_local_discard_all_pressed(self) -> None:
        self.post_message(DiscardAllRequested())
