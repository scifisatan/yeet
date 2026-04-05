from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from yeet.git_repository import GitRepository
from yeet.widgets.confirm_modal import ConfirmModal
from yeet.widgets.git_change_lists import GitChangesList, GitStagedList
from yeet.widgets.git_change_models import GitChange, parse_porcelain_status
from yeet.widgets.git_commit_widget import GitCommitWidget

if TYPE_CHECKING:
    from yeet.screens.main import MainScreen


class GitChangesController:
    def __init__(self, screen: MainScreen, project_path: Path) -> None:
        self._screen = screen
        self._git = GitRepository(project_path)
        self._staged_entries: list[GitChange] = []
        self._local_entries: list[GitChange] = []
        self._refresh_in_progress = False
        self._refresh_queued = False
        self._last_snapshot: tuple[str, ...] = ()
        self._commit_in_progress = False

    def _commit_widget(self) -> GitCommitWidget:
        return self._screen.query_one("#commit-controls", GitCommitWidget)

    def _staged_list(self) -> GitStagedList:
        return self._screen.query_one("#staged-list", GitStagedList)

    def _changes_list(self) -> GitChangesList:
        return self._screen.query_one("#changes-list", GitChangesList)

    def _render_options(self) -> None:
        self._staged_list().set_rows(self._staged_entries)
        self._changes_list().set_rows(self._local_entries)

    def _change_from_section(self, section: str, option_id: str) -> GitChange | None:
        if section == "staged":
            return self._staged_list().get_change(option_id)
        return self._changes_list().get_change(option_id)

    async def _confirm(self, title: str, body: str) -> bool:
        confirmed = await self._screen.app.push_screen_wait(ConfirmModal(title, body))
        return bool(confirmed)

    def update_commit_button(self) -> None:
        if not self._screen.is_mounted:
            return
        self._commit_widget().update_state(
            has_staged_changes=bool(self._staged_entries),
            in_progress=self._commit_in_progress,
        )

    async def commit_changes(self) -> None:
        if self._commit_in_progress:
            return

        commit_widget = self._commit_widget()
        message = commit_widget.commit_message().strip()

        if not self._staged_entries:
            git_args = ["push", "origin", "HEAD"]
            title = "Git push"
            requires_message = False
        else:
            git_args = ["commit", "-m", message]
            title = "Git commit"
            requires_message = True

        if requires_message and not message:
            self._screen.notify(
                "Enter a commit message first", title=title, severity="warning"
            )
            return

        self._commit_in_progress = True
        self.update_commit_button()
        try:
            _code, stdout, stderr = await self._git.run(git_args)
        except Exception as error:
            self._screen.notify(str(error), title=title, severity="error")
        else:
            if requires_message:
                commit_widget.set_commit_message("")
            output_text = stdout.strip() or stderr.strip()
            summary_line = output_text.splitlines()[0] if output_text else "Done"
            self._screen.notify(summary_line, title=title)
        finally:
            self._commit_in_progress = False
            await self.refresh_changes()
            self.update_commit_button()

    async def undo_last_commit(self) -> None:
        if self._commit_in_progress:
            return

        confirmed = await self._confirm(
            "Undo last commit?",
            "This will run: git reset --soft HEAD~1.\nYour changes stay in the index.",
        )
        if not confirmed:
            return

        reverted_message = await self._git.read_head_commit_subject()

        self._commit_in_progress = True
        self.update_commit_button()
        try:
            _code, stdout, stderr = await self._git.run(["reset", "--soft", "HEAD~1"])
        except Exception as error:
            self._screen.notify(str(error), title="Git undo", severity="error")
        else:
            if reverted_message:
                self._commit_widget().set_commit_message(reverted_message)
            output_text = stdout.strip() or stderr.strip()
            summary_line = output_text.splitlines()[0] if output_text else "Done"
            self._screen.notify(summary_line, title="Git undo")
        finally:
            self._commit_in_progress = False
            await self.refresh_changes()
            self.update_commit_button()

    async def refresh_changes(self, notify: bool = False) -> None:
        if self._refresh_in_progress:
            self._refresh_queued = True
            return

        self._refresh_in_progress = True
        try:
            while True:
                self._refresh_queued = False

                try:
                    _code, stdout, _stderr = await self._git.run(
                        ["status", "--porcelain=v1", "--untracked-files=all"]
                    )
                except Exception as error:
                    snapshot = ("Unable to read git status",)
                    if snapshot != self._last_snapshot:
                        self._staged_entries = []
                        self._local_entries = []
                        self._last_snapshot = snapshot
                        self._render_options()
                    if notify:
                        self._screen.notify(
                            str(error), title="Git changes", severity="error"
                        )
                else:
                    staged, local = parse_porcelain_status(stdout)
                    if not staged and not local:
                        snapshot = ("No local changes",)
                        if snapshot != self._last_snapshot:
                            self._staged_entries = []
                            self._local_entries = []
                            self._last_snapshot = snapshot
                            self._render_options()
                        if notify:
                            self._screen.notify("No local changes", title="Git changes")
                    else:
                        staged_labels = tuple(
                            (
                                change.path,
                                change.old_path or "",
                                change.status,
                            )
                            for change in staged
                        )
                        local_labels = tuple(
                            (
                                change.path,
                                change.old_path or "",
                                change.status,
                            )
                            for change in local
                        )
                        labels = ("staged",) + staged_labels + ("local",) + local_labels
                        if labels != self._last_snapshot:
                            self._staged_entries = staged
                            self._local_entries = local
                            self._render_options()
                            self._last_snapshot = labels

                if not self._refresh_queued:
                    break
        finally:
            self._refresh_in_progress = False
            self.update_commit_button()

    async def handle_file_action(self, section: str, option_id: str, action: str) -> None:
        if section == "staged":
            change = self._change_from_section(section, option_id)
            if change is None:
                return
            if action == "minus":
                try:
                    await self._git.unstage_path(change.path)
                except Exception as error:
                    self._screen.notify(str(error), title="Git unstage", severity="error")
                    return
                self._screen.notify(f"Unstaged: {change.path}", title="Git unstage")
                await self.refresh_changes()
            return

        change = self._change_from_section(section, option_id)
        if change is None:
            return

        if action == "plus":
            try:
                await self._git.stage_path(change.path)
            except Exception as error:
                self._screen.notify(str(error), title="Git stage", severity="error")
                return
            self._screen.notify(f"Staged: {change.path}", title="Git stage")
            await self.refresh_changes()
            return

        if action == "minus":
            confirmed = await self._confirm(
                "Discard local change?",
                f"This will discard local edits for {change.path}.",
            )
            if not confirmed:
                return
            try:
                await self._git.discard_local_path(change)
            except Exception as error:
                self._screen.notify(str(error), title="Git discard", severity="error")
                return
            self._screen.notify(f"Discarded: {change.path}", title="Git discard")
            await self.refresh_changes()

    async def bulk_stage_all(self) -> None:
        try:
            await self._git.stage_all()
        except Exception as error:
            self._screen.notify(str(error), title="Git stage", severity="error")
            return
        self._screen.notify("Staged all changes", title="Git stage")
        await self.refresh_changes()

    async def bulk_unstage_all(self) -> None:
        try:
            await self._git.unstage_all()
        except Exception as error:
            self._screen.notify(str(error), title="Git unstage", severity="error")
            return
        self._screen.notify("Unstaged all changes", title="Git unstage")
        await self.refresh_changes()

    async def bulk_discard_all(self) -> None:
        confirmed = await self._confirm(
            "Discard all local changes?",
            "This will restore tracked files and delete untracked files (git clean -fd).",
        )
        if not confirmed:
            return

        try:
            await self._git.discard_all_local()
        except Exception as error:
            self._screen.notify(str(error), title="Git discard", severity="error")
            return
        self._screen.notify("Discarded all local changes", title="Git discard")
        await self.refresh_changes()

    async def open_selected_change(self, section: str, option_id: str) -> None:
        change = self._change_from_section(section, option_id)
        if change is None:
            return

        staged = section == "staged"
        try:
            path1, path2, before, after = await self._git.load_diff_payload(
                change, staged=staged
            )
        except Exception as error:
            self._screen.notify(str(error), title="Git diff", severity="error")
            return
        await self._screen._show_git_diff(path1, path2, before, after)

    async def toggle_stage(self, section: str, option_id: str) -> None:
        change = self._change_from_section(section, option_id)
        if change is None:
            return

        path = change.path
        if section == "staged":
            action_label = "Unstaged"
            action = self._git.unstage_path
        else:
            action_label = "Staged"
            action = self._git.stage_path

        try:
            await action(path)
        except Exception as error:
            self._screen.notify(str(error), title="Git stage", severity="error")
            return

        self._screen.notify(f"{action_label}: {path}", title="Git stage")
        await self.refresh_changes()
