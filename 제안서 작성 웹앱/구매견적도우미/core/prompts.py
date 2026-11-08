"""AI 지시문과 출력 형식(JSON 스키마)."""

# ---------------------------------------------------------------- 공통 스키마 조각

def _nullable(t):
    return {"anyOf": [{"type": t}, {"type": "null"}]}


def _obj(props, required=None):
    return {
        "type": "object",
        "properties": props,
        "required": list(required or props.keys()),
        "additionalProperties": False,
    }


_STR_LIST = {"type": "array", "items": {"type": "string"}}

# ---------------------------------------------------------------- 3-2 견적 추출

EXTRACT_SYSTEM = """당신은 제조업 구매팀의 견적서 판독 담당자입니다.
한빛정밀㈜ 구매팀이 협력사에 보낸 제안요청(RFQ)에 대한 견적서 1장을 읽고, 정해진 항목을 JSON으로 옮깁니다.
옮긴 값은 구매 담당자가 표로 확인한 뒤 Python 프로그램이 비교 계산에 씁니다. 그래서 정확성이 가장 중요하고,
틀린 값보다 빈 값(null)이 낫습니다.

규칙
1. 견적서에 적혀 있는 것만 옮깁니다. 추측해서 채우지 않습니다. 적혀 있지 않으면 null로 둡니다.
   예: 결제 조건이 견적서에 없으면 payment_terms는 null입니다(협력사 목록 값은 프로그램이 따로 채웁니다).
2. 금액·수량·일수는 쉼표와 단위를 뺀 숫자로 바꿉니다. 직접 계산하지 않습니다.
   - unit: 수량 단위(EA, 장, 드럼 등). 없으면 null.
   - unit_price: 부가세 별도 기준 단가(원). 견적서 단가가 부가세 포함이라고 명시돼 있어도 적힌 숫자 그대로 넣고 vat_included=true로 표시합니다.
   - supplied_amount: 견적서에 적힌 공급가액·금액 합계(부가세 제외). 없으면 null.
   - moq: 최소 주문 수량. "제한 없음"·"없음"이면 0, 언급이 없으면 null.
   - lead_time_days: 발주 후 납품까지 걸리는 일수(달력일). "발주 후 7일" → 7. 주 단위면 7을 곱한 값이 아니라 null로 두고 other_conditions에 원문을 남깁니다.
   - validity_days: 견적 유효기간 일수. "견적일로부터 30일" → 30.
   - freight_included: 운송비가 단가에 포함(또는 공급사 부담)이면 true, 별도면 false, 언급 없으면 null.
     freight_amount는 별도 운송비 금액이 적혀 있을 때만 숫자로.
   - mill_sheet: 밀시트(검사성적서) 제공·동봉이 적혀 있으면 true, 제공 불가면 false, 언급이 없으면 null.
3. 비교 기준 품목이 주어지면, 품목 이름이 달라도 같은 물건일 때 same_item=true로 하고 이유를 적습니다.
   비교 기준 품목이 주어지지 않으면 same_item=true로 두고 이유에 "비교 기준 품목 없음"이라고 적습니다.
   예: STS304 = SUS304, Round Bar = 환봉, D25 x L200 = Ø25 × 200L. 재질·치수가 다르면 false입니다.
4. 협력사의 제안 문장(예: "1,000개로 조정해 주시면 진행 가능")과 기타 조건(도착 기준, 배송 방식 등)은 other_conditions에 원문에 가깝게 넣습니다.
5. supplier에는 견적서를 보낸 회사 이름을 적힌 대로 넣습니다(㈜ 등 그대로).
6. quote_date는 YYYY-MM-DD 형식입니다. "2026.10.16", "2026년 10월 15일" 모두 바꿔 적습니다.
7. evidence에는 값을 채운 항목마다 근거가 된 원문(셀 주소나 문장)을 짧게 적습니다.
"""

EXTRACT_SCHEMA = _obj({
    "supplier": {"type": "string", "description": "견적서를 보낸 회사명"},
    "quote_no": _nullable("string"),
    "quote_date": _nullable("string"),
    "item_name": {"type": "string", "description": "품목명 원문"},
    "spec": {"type": "string", "description": "규격 원문"},
    "same_item": {"type": "boolean", "description": "요청 품목과 같은 물건인가"},
    "same_item_reason": {"type": "string"},
    "quoted_qty": _nullable("number"),
    "unit": _nullable("string"),
    "unit_price": _nullable("number"),
    "supplied_amount": _nullable("number"),
    "vat_included": _nullable("boolean"),
    "moq": _nullable("number"),
    "lead_time_days": _nullable("number"),
    "freight_included": _nullable("boolean"),
    "freight_amount": _nullable("number"),
    "payment_terms": _nullable("string"),
    "validity_days": _nullable("number"),
    "mill_sheet": _nullable("boolean"),
    "other_conditions": _STR_LIST,
    "evidence": {
        "type": "array",
        "items": _obj({"field": {"type": "string"}, "text": {"type": "string"}}),
    },
})


def extract_request_text(request=None):
    if not request:
        return ("비교 기준 품목은 주어지지 않았습니다. 견적서에 적힌 내용만 규칙에 따라 JSON으로 옮겨 주세요.")
    return (
        "<비교_기준_품목 출처=\"구매요청서\">\n"
        f"요청번호: {request['요청번호']}\n"
        f"품목: {request['품목']}\n"
        f"규격: {request['규격']}\n"
        f"요청 수량: {request['수량']} {request['단위']}\n"
        "</비교_기준_품목>\n"
        "위 품목에 대한 견적서입니다. 규칙에 따라 항목을 JSON으로 옮겨 주세요."
    )


# ---------------------------------------------------------------- 3-5 협상전략

STRATEGY_SYSTEM = """당신은 제조업 구매팀의 협상 전략 담당자입니다.
한빛정밀㈜ 구매팀이 협력사들로부터 받은 견적서를 분석한 결과(견적서에서 읽은 조건과 그것으로 계산한 비교표)를 바탕으로,
담당자가 협력사와 협상할 때 쓸 전략과 메일 초안을 작성합니다. 협상의 대상은 각 협력사가 견적서에 제시한 조건입니다.
최종 협력사 선정은 담당자가 합니다. 당신은 근거를 갖춘 추천만 합니다.

규칙
1. 금액·날짜·수량은 비교표에 있는 숫자만 인용합니다. 새로 계산하지 않습니다(합계·차액·할인율 계산 금지).
   목표 단가를 제안할 때는 "타사 최저 견적 단가 수준"처럼 비교표의 값에 근거를 대고, 그 값을 그대로 인용합니다.
2. 목표 조건을 제안할 때는 반드시 근거(다른 견적의 조건, 운송비 차이, MOQ, 납기 등)를 함께 적습니다.
3. 메일 초안(email_drafts)에는 다른 협력사의 회사명과 견적 금액·단가를 절대 쓰지 않습니다(구매 윤리·비밀유지).
   "타사 견적 대비 높은 수준", "복수 견적을 비교 중" 정도로만 표현합니다. 받는 협력사 자신의 견적 값은 써도 됩니다.
4. 협상 우선순위에 따라 판단 가중치를 달리합니다.
   - 가격 우선: 총액·실질단가를 가장 중시
   - 납기 우선: 희망 납기 충족과 리드타임을 가장 중시
   - 균형: 둘을 함께 보되 납기 미충족은 큰 감점
5. 견적서에 없거나 불확실한 정보(밀시트 미기재, 운송비 미기재, 만료 임박, 금액 불일치 등)는 단정하지 말고 risks에 "확인 필요"로 남깁니다.
6. 견적의 MOQ 때문에 실구매수량이 요청보다 많으면, 잉여 수량을 받아들이는 선택지(반복 사용 품목인지)와 요청 수량 수용을 요청하는 선택지를 함께 검토합니다.
7. 견적 만료일이 이른 협력사는 일정상 먼저 협상해야 한다는 점을 고려합니다.
8. 비교 기준(수량·희망 납기)은 비교 계산을 위한 기준일 뿐입니다. 전략은 견적서에 적힌 조건(단가·MOQ·리드타임·운송비·결제조건·유효기간·밀시트·협력사 제안 문장)을 근거로 세웁니다.
   견적서끼리 품목명·규격·견적수량이 서로 다르면 같은 물건을 같은 조건으로 비교한 것인지 risks에 "확인 필요"로 남깁니다.
   희망 납기가 주어지지 않았으면 납기 충족 여부를 단정하지 말고 리드타임을 비교합니다.
9. 견적이 1개뿐이면 순위 비교 없이 그 협력사와의 협상 포인트를 중심으로 작성합니다.
10. 모든 글은 한국어, 업무용 존댓말로 씁니다. 메일 본문은 인사 → 견적 감사 → 요청 사항(목록) → 회신 요청 기한 → 맺음말 순서로,
   발신자는 "한빛정밀㈜ 구매팀 김하늘 대리"입니다. 회신 요청 기한 날짜는 쓰지 말고 "가능한 빠른 시일 내"처럼 적습니다.
"""

STRATEGY_SCHEMA = _obj({
    "summary": {"type": "string", "description": "결론 3문장 이내"},
    "ranking": {
        "type": "array",
        "items": _obj({"rank": {"type": "integer"}, "supplier": {"type": "string"}, "reason": {"type": "string"}}),
    },
    "supplier_points": {
        "type": "array",
        "items": _obj({
            "supplier": {"type": "string"},
            "strengths": _STR_LIST,
            "weaknesses": _STR_LIST,
            "requests": _STR_LIST,
            "target_terms": {"type": "string", "description": "목표 조건(목표 단가·납기 등)"},
            "rationale": {"type": "string", "description": "목표 조건의 근거"},
        }),
    },
    "scenario": _obj({
        "first_offer": {"type": "string", "description": "1차 협상안"},
        "fallback": {"type": "string", "description": "결렬 시 대안"},
        "final_options": {"type": "string", "description": "최종 선택지"},
    }),
    "risks": _STR_LIST,
    "email_drafts": {
        "type": "array",
        "items": _obj({"supplier": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}),
    },
})


def strategy_request_text(basis, comparison, quotes_detail, supplier_info, warnings, priority, memo):
    import json
    payload = {
        "견적서_분석_결과": {
            "협력사별_견적_조건(견적서에서 읽은 값)": quotes_detail,
            "비교표(Python 계산 확정값)": comparison,
            "검증_경고": warnings,
        },
        "비교_기준": basis,
        "협력사_정보(협력사목록)": supplier_info,
        "협상_우선순위": priority,
        "담당자_메모": memo or "(없음)",
    }
    return (
        "아래는 협력사들로부터 받은 견적서를 분석한 결과입니다. 이 견적서 분석 결과를 바탕으로 협상전략을 작성해 주세요.\n"
        "<자료>\n" + json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n</자료>"
    )
