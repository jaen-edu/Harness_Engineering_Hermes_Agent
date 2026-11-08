from __future__ import annotations


def add_task(task_or_tasks: list[str] | str, task: str | None = None) -> list[str]:
    if task is None:
        tasks: list[str] = []
        candidate = task_or_tasks
    else:
        if not isinstance(task_or_tasks, list):
            raise TypeError("tasks must be a list")
        tasks = task_or_tasks
        candidate = task

    if not isinstance(candidate, str):
        raise TypeError("task must be a string")

    title = candidate.strip()
    if not title:
        raise ValueError("task must not be empty")

    return [*tasks, title]


def add(items: list[str], item: str) -> list[str]:
    return add_task(items, item)
