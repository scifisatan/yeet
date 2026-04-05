from __future__ import annotations

import asyncio
from asyncio.subprocess import PIPE
from pathlib import Path

from yeet.widgets.git_change_models import GitChange


class GitRepository:
    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path

    async def run(
        self, args: list[str], allow_error: bool = False
    ) -> tuple[int, str, str]:
        process = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(self.project_path),
            *args,
            stdout=PIPE,
            stderr=PIPE,
        )
        stdout, stderr = await process.communicate()
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
        if not allow_error and process.returncode != 0:
            raise RuntimeError(stderr_text.strip() or "git command failed")
        return process.returncode or 0, stdout_text, stderr_text

    async def read_working_file(self, path: str) -> str:
        full_path = self.project_path / path
        if not full_path.exists() or not full_path.is_file():
            return ""
        data = await asyncio.to_thread(full_path.read_bytes)
        if b"\x00" in data:
            return "(binary file)"
        return data.decode("utf-8", errors="replace")

    async def read_head_file(self, path: str) -> str:
        code, stdout, _stderr = await self.run(["show", f"HEAD:{path}"], allow_error=True)
        if code != 0:
            return ""
        return stdout

    async def read_index_file(self, path: str) -> str:
        code, stdout, _stderr = await self.run(["show", f":{path}"], allow_error=True)
        if code != 0:
            return ""
        return stdout

    async def stage_path(self, path: str) -> None:
        await self.run(["add", "-A", "--", path])

    async def unstage_path(self, path: str) -> None:
        try:
            await self.run(["restore", "--staged", "--", path])
        except Exception:
            code, _stdout, _stderr = await self.run(
                ["rm", "--cached", "--", path], allow_error=True
            )
            if code != 0:
                raise

    async def stage_all(self) -> None:
        await self.run(["add", "-A"])

    async def unstage_all(self) -> None:
        code, _stdout, _stderr = await self.run(
            ["restore", "--staged", ":/"], allow_error=True
        )
        if code != 0:
            await self.run(["reset", "HEAD", "--", "."])

    async def discard_all_local(self) -> None:
        await self.run(["restore", "--worktree", ":/"])
        await self.run(["clean", "-fd"])

    async def discard_local_path(self, change: GitChange) -> None:
        path = change.path
        if change.status == "untracked":
            await self.run(["clean", "-fd", "--", path])
            return

        await self.run(["restore", "--worktree", "--", path])
        if change.status == "deleted":
            await self.run(["checkout", "--", path], allow_error=True)

    async def load_diff_payload(
        self, change: GitChange, *, staged: bool
    ) -> tuple[str, str, str, str]:
        before_path = change.old_path or change.path
        after_path = change.path

        if change.status == "untracked":
            before = ""
            after = await self.read_working_file(after_path)
            return before_path, after_path, before, after

        before = (
            await self.read_head_file(before_path)
            if staged
            else await self.read_index_file(before_path)
        )
        if change.status == "deleted":
            after = ""
        else:
            after = (
                await self.read_index_file(after_path)
                if staged
                else await self.read_working_file(after_path)
            )

        return before_path, after_path, before, after

    async def read_head_commit_subject(self) -> str:
        code, stdout, _stderr = await self.run(
            ["log", "-1", "--pretty=%s"], allow_error=True
        )
        if code != 0:
            return ""
        return stdout.strip()
