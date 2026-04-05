from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GitChange:
    path: str
    old_path: str | None
    status: str


def status_from_code(code: str) -> str:
    if code == "?":
        return "untracked"
    if code == "M":
        return "modified"
    if code == "A":
        return "added"
    if code == "D":
        return "deleted"
    if code in {"R", "C"}:
        return "renamed"
    return "changed"


def parse_porcelain_status(
    status_output: str,
) -> tuple[list[GitChange], list[GitChange]]:
    staged: list[GitChange] = []
    local: list[GitChange] = []
    for line in status_output.splitlines():
        if len(line) < 3:
            continue
        xy = line[:2]
        path_field = line[3:]

        old_path: str | None = None
        path = path_field
        if " -> " in path_field:
            old_path, path = path_field.split(" -> ", 1)

        if xy == "??":
            local.append(GitChange(path=path, old_path=old_path, status="untracked"))
            continue

        index_code, worktree_code = xy[0], xy[1]
        if index_code != " ":
            staged.append(
                GitChange(
                    path=path,
                    old_path=old_path,
                    status=status_from_code(index_code),
                )
            )
        if worktree_code != " ":
            local.append(
                GitChange(
                    path=path,
                    old_path=old_path,
                    status=status_from_code(worktree_code),
                )
            )

    return staged, local
