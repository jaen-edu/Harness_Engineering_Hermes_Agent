import pytest

from todo import add


def test_add_todo_returns_updated_list() -> None:
    # Given: 기존 할 일 목록이 있다.
    items = ["기존 할 일"]

    # When: 새로운 할 일을 추가한다.
    result = add(items, "새 할 일")

    # Then: 새 항목이 포함된 목록이 반환되어야 한다.
    assert result == ["기존 할 일", "새 할 일"]


def test_add_empty_string_raises_value_error() -> None:
    # Given: 비어 있는 목록이 있다.
    items: list[str] = []

    # When / Then: 빈 문자열은 허용되지 않아야 한다.
    with pytest.raises(ValueError):
        add(items, "")


def test_add_none_raises_type_error() -> None:
    # Given: 비어 있는 목록이 있다.
    items: list[str] = []

    # When / Then: None 입력은 타입 오류여야 한다.
    with pytest.raises(TypeError):
        add(items, None)  # type: ignore[arg-type]
