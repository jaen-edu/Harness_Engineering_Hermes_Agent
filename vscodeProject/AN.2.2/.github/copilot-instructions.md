# GitHub Copilot 전역 지침 (Global Instructions)
# 파일 위치: .github/copilot-instructions.md
# 적용 범위: 이 워크스페이스의 모든 Copilot 대화에 자동 포함됩니다.

## 과정 컨텍스트

이 저장소는 **AI-Native 소프트웨어 개발: Agent Skills 기반 AI 코딩 워크플로우** 실습 워크스페이스입니다.

- 주 언어: Python 3.12
- 패키지 매니저: uv
- 테스트 프레임워크: pytest
- 코드 품질 도구: ruff

## 코딩 원칙

1. **Python 우선**: 모든 구현 코드는 Python 3.12 문법을 사용합니다.
2. **TDD 사이클 준수**: 테스트 없이 구현 코드를 먼저 작성하지 않습니다.
3. **단순성 우선**: 테스트를 통과하는 가장 단순한 구현을 선택합니다. 과도한 추상화를 피합니다.
4. **명시적 의존성**: 외부 패키지를 추가할 때는 반드시 `requirements.txt`에 버전과 함께 기록합니다.

## Skills 디렉터리

이 프로젝트는 `.github/skills/` 디렉터리에 재사용 가능한 Agent Skills를 관리합니다.
각 Skill의 `SKILL.md`는 Copilot이 특정 작업을 수행하는 방식을 정의합니다.

## 파일 및 폴더 명명 규칙

- Python 파일: `snake_case.py`
- 테스트 파일: `test_<대상모듈>.py`
- Skill 디렉터리: `kebab-case/SKILL.md`
- 문서: `한글 제목 사용 가능, 영문 파일명`

## 응답 언어

학습자에게 설명할 때, 그리고 생성되는 문서는 모두 **한국어**를 사용합니다. 코드와 파일 경로는 영문 그대로 유지합니다.
