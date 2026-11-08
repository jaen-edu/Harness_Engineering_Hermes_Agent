# 1교시: OT 및 개발환경 설정
**시간**: 10:00–11:00 | **유형**: 고정 (환경 설정)

---

## 학습 목표

이 교시가 끝나면 수강생은:
1. 과정 전체 흐름과 최종 산출물을 이해합니다.
2. 모든 실습을 진행할 수 있는 동일한 개발 환경을 갖춥니다.

---

## 1. 과정 개요 안내

### AI-Native 개발이란?

> **AI-Native 개발(AI-Native Development)**  
> AI를 "보조 도구"가 아니라 개발 사이클의 핵심 구성원으로 통합하는 방식입니다.  
> 전통 방식이 "개발자 → 코드 → 리뷰" 순이라면, AI-Native는 "요구사항 → AI Agent → 검증" 흐름으로 재편합니다.

### 2일 14교시 전체 흐름

```
[1일차] 환경 → 개념 → Skills 설계(PRD/TASK/TDD) → 통합 실습
[2일차] 심화 Skills → 실전 프로젝트 → 배포 자동화 → 최종 발표
```

### 최종 산출물

- 재사용 가능한 **Skill Pack** (5개 Skills)
- Skills를 활용해 TDD로 개발한 **Python 계산기 앱**
- 자동화된 **개발 환경 설정 스크립트** (setup.ps1)etup.ps1

---

## 2. 개발 환경 일괄 설정

### 2-1. Python 3.12 + uv 설치

> **uv**는 pip보다 10~100배 빠른 Python 패키지 매니저입니다.  
> Rust로 작성되어 의존성 해결과 설치가 빠르며, 가상환경 관리까지 통합되어 있습니다.

```powershell
# uv 설치 (Windows PowerShell)
Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression

# uv로 Python 3.12 설치
uv python install 3.12

# 가상환경 생성 및 활성화
uv venv --python 3.12
.\.venv\Scripts\Activate.ps1

# 의존성 설치
uv pip install -r requirements.txt
```

> **자동화 스크립트** 사용:
> ```powershell
> .\setup.ps1
> ```

### 2-2. GitHub Copilot Pro Plan 확인

1. https://github.com/settings/copilot 접속
2. Copilot Pro 구독 상태 확인
3. VS Code에서 `Ctrl+Shift+P` → "GitHub Copilot: Sign In"

### 2-3. .env 기본 구성

```env
# 예시 (실제 값은 절대 커밋하지 않습니다)
APP_ENV=development
```

---

## 3. 환경 설정 확인 체크리스트

```
[ ] uv --version 출력 확인
[ ] python --version → 3.12.x 확인
[ ] pytest --version 출력 확인
[ ] VS Code에서 Python 인터프리터로 .venv 선택 확인
```

---

## 구성 이유

이후 모든 실습의 전제 조건인 개발 환경을 동일하게 맞춰야 수업 중 환경 차이로 인한 지연을 방지할 수 있습니다. `uv`는 `pip`보다 빠른 의존성 관리 도구로, AI-Native 개발 실습에서 빠른 패키지 설치·관리가 필요하기 때문에 채택합니다.
