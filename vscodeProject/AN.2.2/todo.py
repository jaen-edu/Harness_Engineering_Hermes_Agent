def add(items: list[str], task: str) -> list[str]:
    if task is None or not isinstance(task, str):
        raise TypeError("task must be a string")
    if not task.strip():
        raise ValueError("task must not be empty")
    return [*items, task.strip()]
