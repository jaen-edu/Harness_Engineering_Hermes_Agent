---
name: prd-writer
description: 프로젝트 정보를 바탕으로 구조화된 PRD.md를 작성합니다.
---
# Skill: prd-writer

## 트리거 조건

다음 중 하나가 포함된 요청이 들어올 때 이 Skill을 사용합니다:
- "PRD 작성해줘" / "PRD 만들어줘"
- "요구사항 문서 작성"
- "prd-writer Skill 사용해서"
- 새 기능/앱 개발을 시작하는 요청 (요구사항이 불명확한 경우)

# PRD: SimpleTask CLI

## 1. 개요
SimpleTask는 터미널 기반으로 할 일을 관리하는 Python CLI 애플리케이션입니다.

## 2. 목표
- 빠른 Todo 입력 및 관리
- 파일 기반 저장 (JSON)
- 개발자 친화적 UX

## 3. 대상 사용자
- 개발자
- CLI 환경 사용자

## 4. 핵심 기능
### 4.1 할 일 추가
- 명령어: add "할 일 내용"
- ID 자동 생성

### 4.2 할 일 조회
- 전체 목록 출력
- 상태(완료/미완료) 표시

### 4.3 완료 처리
- 명령어: done {id}

### 4.4 삭제
- 명령어: delete {id}

## 5. 기술 스택
- Python 3.12
- JSON 파일 저장

## 6. 데이터 구조
```json
{
  "id": 1,
  "task": "강의 준비",
  "done": false
}
7. 확장 계획
태그 기능
우선순위
날짜 기반 필터
