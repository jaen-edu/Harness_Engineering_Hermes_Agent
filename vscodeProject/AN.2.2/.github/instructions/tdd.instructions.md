---
applyTo: "**/test_*.py"
---
# 로컬 지침: TDD 테스트 작성 표준 (Local Instructions)
# 적용 범위: test_*.py 파일 편집 시 자동 적용됩니다.

## 테스트 구조: Given / When / Then

```python
def test_기능명_시나리오():
    # Given: 사전 조건 설정
    ...
    # When: 동작 실행
    result = ...
    # Then: 결과 검증
    assert result == expected
```

## 테스트 명명 규칙

- `test_<함수명>_<시나리오>_<기댓값>` 형식을 권장합니다.
- 예: `test_add_positive_numbers_returns_sum`

## 필수 케이스

각 함수에 대해 다음 케이스를 포함합니다:
1. **정상 케이스 (Happy Path)**: 일반적인 입력
2. **경계값 케이스 (Edge Case)**: 0, 빈 문자열, 최솟값/최댓값
3. **오류 케이스**: 잘못된 입력 시 예외 발생 여부

## pytest 사용 규칙

- `assert` 문을 직접 사용합니다 (`assertEqual` 대신).
- 예외 테스트: `pytest.raises(ValueError)` 컨텍스트 매니저를 사용합니다.
- 픽스처(fixture)는 `conftest.py`에 모읍니다.

## TDD Red 단계 원칙

- 테스트를 먼저 작성하고 **실행하여 실패(Red)를 확인**한 뒤 구현을 시작합니다.
- 테스트가 컴파일 오류 없이 실패해야 합니다 (`ImportError` 방지).

## 파일 분리 원칙

- 테스트 파일은 구현 파일과 같은 디렉터리 레벨에 위치합니다.
- 예: `calculator.py` ↔ `test_calculator.py`
