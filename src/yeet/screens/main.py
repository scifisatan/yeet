import asyncio
from pathlib import Path

from textual import on, work, highlight
from textual.app import ComposeResult
from textual import getters
from textual.binding import Binding
from textual.content import Content
from textual.screen import Screen
from textual.reactive import var
from textual.timer import Timer
from textual.widgets import Footer, DirectoryTree, Tree, Static
from textual import containers
from textual.widget import Widget

from yeet.app import YeetApp
from yeet.git_changes_controller import GitChangesController
from yeet.messages import ProjectDirectoryUpdated
from yeet.widgets.diff_view import DiffView
from yeet.widgets.git_change_lists import (
    ChangeSelected,
    DiscardAllRequested,
    FileActionRequested,
    GitChangesList,
    GitStagedList,
    StageAllRequested,
    ToggleStageRequested,
    UnstageAllRequested,
)
from yeet.widgets.git_commit_widget import (
    CommitMessageChanged,
    CommitRequested,
    GitCommitWidget,
    UndoRequested,
)
from yeet.widgets.project_directory_tree import ProjectDirectoryTree
from yeet.widgets.side_bar import SideBar


class MainScreen(Screen, can_focus=False):
    AUTO_FOCUS = "#project_directory_tree"

    CSS_PATH = "main.tcss"

    BINDINGS = [
        Binding("ctrl+b,f20", "show_sidebar", "Sidebar"),
        Binding(
            "ctrl+alt+left,ctrl+shift+left,f7",
            "sidebar_narrower",
            "Sidebar narrower",
        ),
        Binding(
            "ctrl+alt+right,ctrl+shift+right,f8",
            "sidebar_wider",
            "Sidebar wider",
        ),
        Binding(
            "ctrl+alt+0,ctrl+shift+0,f9",
            "sidebar_reset",
            "Sidebar default",
        ),
        Binding("ctrl+r", "refresh_git", "Refresh", tooltip="Refresh git changes"),
        Binding("ctrl+enter", "commit_git", "Commit", tooltip="Commit staged changes"),
    ]

    BINDING_GROUP_TITLE = "Screen"
    side_bar = getters.query_one(SideBar)
    project_directory_tree = getters.query_one("#project_directory_tree")
    inline_diff_container = getters.query_one("#inline-diff", containers.Vertical)
    inline_view_body = getters.query_one("#inline-view-body", containers.VerticalScroll)

    project_path: var[Path] = var(Path("./").expanduser().absolute())

    app = getters.app(YeetApp)

    def __init__(
        self,
        project_path: Path,
    ) -> None:
        super().__init__()
        self.set_reactive(MainScreen.project_path, project_path)
        self._changes_controller = GitChangesController(self, project_path)
        self._project_refresh_timer: Timer | None = None
        self._inline_view_widget: Widget | None = None

    def watch_title(self, title: str) -> None:
        self.app.update_terminal_title()

    def compose(self) -> ComposeResult:
        with containers.Center():
            yield SideBar(
                SideBar.Panel(
                    "Changes",
                    containers.Vertical(
                        GitCommitWidget(id="commit-controls"),
                        GitStagedList(id="staged-list"),
                        GitChangesList(id="changes-list"),
                        id="git-changes-panel",
                    ),
                ),
                SideBar.Panel(
                    "Project",
                    ProjectDirectoryTree(
                        self.project_path,
                        id="project_directory_tree",
                    ),
                    flex=True,
                ),
            )
            with containers.Vertical(id="main-panel"):
                with containers.Vertical(id="inline-diff"):
                    yield Static("Preview", id="inline-diff-title")
                    yield containers.VerticalScroll(id="inline-view-body")
        yield Footer()

    def update_node_styles(self, animate: bool = True) -> None:
        self.query_one(Footer).update_node_styles(animate=animate)
        self.query_one(SideBar).update_node_styles(animate=animate)

    @on(ProjectDirectoryUpdated)
    async def on_project_directory_update(self) -> None:
        self._schedule_project_refresh()

    def _schedule_project_refresh(self) -> None:
        if self._project_refresh_timer is None:
            self._project_refresh_timer = self.set_timer(
                0.15, self._run_scheduled_project_refresh
            )
        else:
            self._project_refresh_timer.reset()

    def _run_scheduled_project_refresh(self) -> None:
        self._project_refresh_timer = None
        self.refresh_project_views()

    @work
    async def refresh_project_views(self) -> None:
        await self.query_one(ProjectDirectoryTree).reload()
        await self._changes_controller.refresh_changes()

    async def _show_git_diff(
        self, path1: str, path2: str, before: str, after: str
    ) -> None:
        diff_view = DiffView(path1, path2, before, after)
        await diff_view.prepare()
        additions, removals = diff_view.counts

        diff_view_setting = self.app.settings.get("diff.view", str)
        diff_view.split = diff_view_setting == "split"
        diff_view.auto_split = diff_view_setting == "auto"

        await self._show_inline_widget_with_title(
            Content.from_markup(
                "[b]Diff:[/b] [dim]$path[/dim] [dim]([/][$text-success]+$additions[/][dim]/[/][$text-error]-$removals[/][dim])[/]",
                path=path2,
                additions=additions,
                removals=removals,
            ),
            diff_view,
            show_title=True,
            diff_mode=True,
        )

    def _schedule_auto_refresh(self) -> None:
        self.run_worker(
            self._changes_controller.refresh_changes(),
            exclusive=True,
            group="git-changes-refresh",
        )
    @work
    async def action_refresh_git(self) -> None:
        await self._changes_controller.refresh_changes(notify=True)

    @work
    async def action_commit_git(self) -> None:
        await self._changes_controller.commit_changes()

    @on(CommitMessageChanged)
    def on_commit_message_changed(self, _: CommitMessageChanged) -> None:
        self._changes_controller.update_commit_button()

    @on(ToggleStageRequested)
    async def on_toggle_stage_requested(self, event: ToggleStageRequested) -> None:
        await self._changes_controller.toggle_stage(event.section, event.option_id)

    @on(FileActionRequested)
    def on_file_action_requested(self, event: FileActionRequested) -> None:
        self.run_worker(
            self._changes_controller.handle_file_action(
                event.section, event.option_id, event.action
            ),
            exclusive=True,
            group="git-changes-file-action",
        )

    @on(CommitRequested)
    def on_commit_requested(self, _: CommitRequested) -> None:
        self.run_worker(
            self._changes_controller.commit_changes(),
            exclusive=True,
            group="git-changes-commit",
        )

    @on(UndoRequested)
    def on_revert_requested(self, _: UndoRequested) -> None:
        self.run_worker(
            self._changes_controller.undo_last_commit(),
            exclusive=True,
            group="git-changes-commit",
        )

    @on(StageAllRequested)
    def on_local_stage_all_pressed(self) -> None:
        self.run_worker(
            self._changes_controller.bulk_stage_all(),
            exclusive=True,
            group="git-changes-bulk",
        )

    @on(UnstageAllRequested)
    def on_staged_unstage_all_pressed(self) -> None:
        self.run_worker(
            self._changes_controller.bulk_unstage_all(),
            exclusive=True,
            group="git-changes-bulk",
        )

    @on(DiscardAllRequested)
    def on_local_discard_all_pressed(self) -> None:
        self.run_worker(
            self._changes_controller.bulk_discard_all(),
            exclusive=True,
            group="git-changes-bulk",
        )

    @on(ChangeSelected)
    async def on_change_selected(self, event: ChangeSelected) -> None:
        await self._changes_controller.open_selected_change(
            event.section, event.option_id
        )

    async def _show_inline_widget_with_title(
        self,
        title: Content | str,
        widget: Widget,
        *,
        show_title: bool,
        diff_mode: bool,
    ) -> None:
        if self._inline_view_widget is not None:
            await self._inline_view_widget.remove()
            self._inline_view_widget = None

        title_widget = self.query_one("#inline-diff-title", Static)
        title_widget.update(title)
        title_widget.set_class(not show_title, "-hidden")
        container = self.inline_diff_container
        container.add_class("-show")
        self.inline_view_body.set_class(diff_mode, "-diff-mode")
        await self.inline_view_body.mount(widget)
        self._inline_view_widget = widget
        self.inline_view_body.scroll_home(animate=False)
        self.inline_view_body.focus()

    @on(DirectoryTree.FileSelected, "ProjectDirectoryTree")
    def on_project_directory_tree_selected(self, event: Tree.NodeSelected):
        if (data := event.node.data) is not None:
            self.show_project_file(data.path)

    @work
    async def show_project_file(self, path: Path) -> None:
        path = path.resolve()
        if not path.exists() or not path.is_file():
            return

        try:
            data = await asyncio.to_thread(path.read_bytes)
        except Exception as error:
            self.notify(str(error), title="Open file", severity="error")
            return

        if b"\x00" in data:
            body = "Binary file preview is not supported."
            preview_widget = Static(body, classes="inline-content")
        else:
            text = data.decode("utf-8", errors="replace")
            if not text:
                text = "(empty file)"
            language = highlight.guess_language(text, path.name)
            content = highlight.highlight(text, language=language, path=str(path))
            preview_widget = Static(content, classes="inline-content")

        rel_path = path.relative_to(self.project_path)
        title = Content.from_markup("[b]File:[/b] [dim]$path[/dim]", path=str(rel_path))
        await self._show_inline_widget_with_title(
            title, preview_widget, show_title=True, diff_mode=False
        )

    def on_mount(self) -> None:
        for tree in self.query("#project_directory_tree").results(DirectoryTree):
            tree.data_bind(path=MainScreen.project_path)
        for tree in self.query(DirectoryTree):
            tree.guide_depth = 3
        self.run_worker(
            self._changes_controller.refresh_changes(),
            exclusive=True,
            group="git-changes-refresh",
        )
        self.set_interval(1.0, self._schedule_auto_refresh)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "show_sidebar" and self.side_bar.has_focus_within:
            return False
        return True

    def action_show_sidebar(self) -> None:
        self.side_bar.focus_default()

    def action_sidebar_narrower(self) -> None:
        self.side_bar.narrower()

    def action_sidebar_wider(self) -> None:
        self.side_bar.wider()

    def action_sidebar_reset(self) -> None:
        self.side_bar.reset_width()

    @on(SideBar.Dismiss)
    def on_side_bar_dismiss(self, message: SideBar.Dismiss):
        message.stop()
        self.project_directory_tree.focus()
