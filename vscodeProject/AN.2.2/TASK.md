# TASK.md: task-breakdown Skill

## 요약
- 총 TASK 수: 5개
- High 우선순위: 4개 / Medium: 1개 / Low: 0개

## TASK 목록

| ID  | 우선순위 | 제목 | 의존 | 예상시간 |
|-----|---------|------|------|---------|
| T01 | High    | PRD 입력 검증 및 실패 처리 | 없음 | 0.5h |
| T02 | High    | PRD 기능 항목 추출 규칙 구현 | T01 | 1h |
| T03 | High    | 원자적 TASK 분해 및 의존 정렬 | T02 | 1.5h |
| T04 | High    | TASK.md 필수 포맷 렌더링 | T03 | 1h |
| T05 | Medium  | 기존 TASK.md 덮어쓰기 보호 및 예외 케이스 검증 | T04 | 1h |

## 상세 TASK

### T01: PRD 입력 검증 및 실패 처리
- **설명**: 입력으로 사용할 `PRD.md`의 존재 여부를 확인하고, 파일이 없을 때 지정된 안내 문구를 반환하도록 합니다.
- **완료 조건**:
  - [ ] `PRD.md`가 없으면 "PRD.md가 없습니다. prd-writer Skill을 먼저 실행하세요." 메시지를 출력한다.
  - [ ] `PRD.md`가 존재하면 다음 단계로 정상 진행한다.
- **예상 테스트**: `test_missing_prd_returns_guidance_message`, `test_existing_prd_allows_processing`
- **예상 테스트 수**: 2개
- **의존**: 없음

### T02: PRD 기능 항목 추출 규칙 구현
- **설명**: PRD에서 기능 목록과 우선순위를 읽고, 범위 밖 항목은 제외하는 추출 규칙을 정의합니다.
- **완료 조건**:
  - [ ] PRD의 기능 목록에서 High / Medium / Low 우선순위를 식별한다.
  - [ ] "범위 밖"으로 명시된 기능은 TASK 후보에서 제외한다.
  - [ ] 빈 항목이나 모호한 문장은 분해 대상에서 제외하거나 경고 대상으로 분류한다.
- **예상 테스트**: `test_extracts_prioritized_features_from_prd`, `test_excludes_out_of_scope_items`, `test_ignores_empty_feature_lines`
- **예상 테스트 수**: 3개
- **의존**: T01

### T03: 원자적 TASK 분해 및 의존 정렬
- **설명**: 추출된 기능을 30분~2시간 단위의 독립적인 작업으로 재구성하고, 선행 작업이 먼저 오도록 TASK ID를 배치합니다.
- **완료 조건**:
  - [ ] 기능 하나를 함수 1~3개 또는 단일 동작 기준의 원자적 TASK로 분해한다.
  - [ ] 각 TASK의 완료 조건이 pytest로 검증 가능한 문장으로 작성된다.
  - [ ] 의존 관계가 있는 경우 선행 TASK가 더 낮은 번호를 갖는다.
  - [ ] 전체 TASK 수가 12개를 초과하면 우선순위 재조정을 권장한다.
- **예상 테스트**: `test_breaks_features_into_atomic_tasks`, `test_assigns_dependency_order_to_task_ids`, `test_warns_when_task_count_exceeds_twelve`
- **예상 테스트 수**: 3개
- **의존**: T02

### T04: TASK.md 필수 포맷 렌더링
- **설명**: 요약, 표, 상세 TASK 섹션을 포함한 Markdown 문서를 지정 형식으로 생성합니다.
- **완료 조건**:
  - [ ] 문서 상단에 프로젝트명과 TASK 수 요약이 포함된다.
  - [ ] TASK 목록 표에 ID, 우선순위, 제목, 의존, 예상시간이 포함된다.
  - [ ] 각 상세 TASK에 완료 조건, 예상 테스트, 의존 정보가 누락 없이 들어간다.
- **예상 테스트**: `test_renders_task_summary_section`, `test_renders_task_table_with_required_columns`, `test_renders_detail_sections_for_each_task`
- **예상 테스트 수**: 3개
- **의존**: T03

### T05: 기존 TASK.md 덮어쓰기 보호 및 예외 케이스 검증
- **설명**: 이미 `TASK.md`가 존재할 때 사용자 확인 없이 덮어쓰지 않도록 하고, 출력 안정성을 점검합니다.
- **완료 조건**:
  - [ ] 기존 `TASK.md`가 있으면 덮어쓰기 전에 사용자 확인을 요청한다.
  - [ ] 새 파일 생성 경로와 저장 동작이 실패 없이 처리된다.
  - [ ] 잘못된 PRD 구조에서도 문서 생성 실패 원인이 명확히 표시된다.
- **예상 테스트**: `test_existing_task_file_requires_confirmation`, `test_saves_task_file_to_target_path`, `test_invalid_prd_structure_returns_clear_error`
- **예상 테스트 수**: 3개
- **의존**: T04
