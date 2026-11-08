"""프롬프트 생성, Claude 호출, JSON 파싱. 숫자는 pandas 계산값만 넘긴다."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import anthropic
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SYSTEM_PROMPT_PATH = ROOT / "prompts" / "system_prompt.md"
DEFAULT_MODEL = "claude-sonnet-5-5"

_STR = {"type": "string"}
_STR_LIST = {"type": "array", "items": _STR}
PROPOSAL_SCHEMA = {
    "type": "object",
    "properties": {
        "proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rank": {"type": "integer"},
                    "defect_type": _STR,
                    "phenomenon": _STR,
                    "suspected_causes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "category": {"type": "string", "enum": ["사람", "설비", "자재", "방법"]},
                                "cause": _STR,
                                "evidence": _STR,
                                "evidence_status": {"type": "string", "enum": ["근거 있음", "추정"]},
                                "confidence": {"type": "string", "enum": ["상", "중", "하"]},
                            },
                            "required": ["category", "cause", "evidence", "evidence_status", "confidence"],
                            "additionalProperties": False,
                        },
                    },
                    "verification": _STR_LIST,
                    "short_term": _STR_LIST,
                    "permanent": _STR_LIST,
                    "owner": _STR,
                    "claim_link": _STR,
                    "last_week_check": _STR,
                },
                "required": ["rank", "defect_type", "phenomenon", "suspected_causes", "verification",
                             "short_term", "permanent", "owner", "claim_link", "last_week_check"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["proposals"],
    "additionalProperties": False,
}


def api_settings() -> dict:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    valid = bool(key) and "여기에" not in key and key.startswith("sk-")
    return {
        "has_key": valid,
        "model": os.getenv("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL,
        "timeout": float(os.getenv("AI_TIMEOUT_SEC", "120") or 120),
    }


# ── 입력 만들기 ──────────────────────────────────────────────
def _df_text(df: pd.DataFrame) -> str:
    return df.to_csv(index=True if df.index.name or isinstance(df.index, pd.MultiIndex) else False,
                     sep="|", float_format="%.2f").strip()


def build_user_prompt(defects: pd.DataFrame, week: str, weeks: list[str], top3: list[str],
                      type_qty: pd.DataFrame, type_cnt: pd.DataFrame, changes: list[dict],
                      kpi: dict, memo: str, last_report: dict | None) -> str:
    cur = defects[defects["주차"] == week]
    parts = [f"# 분석 주차: {week} (비교 범위 {weeks[0]} ~ {weeks[-1]})"]
    k = (f"생산수량 {kpi['생산수량']:,}개, 불량수량 {kpi['불량수량']:,}개, 불량건수 {kpi['불량건수']}건, "
         f"불량률 {kpi['불량률']:.2f}%")
    if kpi.get("전주"):
        k += f" (전주 {kpi['전주']} {kpi['전주_불량률']:.2f}%, {kpi['불량률_증감pp']:+.2f}%p)"
    parts.append("## 전체 KPI\n" + k)
    parts.append("## TOP3 불량유형 (불량 수량 기준 순위)\n" + "\n".join(f"{i}. {t}" for i, t in enumerate(top3, 1)))

    parts.append("## 1. 유형별 주차 수량 추이 (개)\n" + _df_text(type_qty.loc[type_qty.index.isin(top3)]))
    parts.append("## 유형별 주차 건수 추이 (건)\n" + _df_text(type_cnt.loc[type_cnt.index.isin(top3)]))

    parts.append("## 2. TOP3 유형별 상세 (이번 주)")
    for t in top3:
        d = cur[cur["불량유형"] == t]
        if d.empty:
            parts.append(f"### {t}\n이번 주 발생 없음")
            continue
        detail = (d.groupby(["라인", "품번", "품명", "출하처", "발견 공정"])["불량수량"].sum()
                  .sort_values(ascending=False).head(10).reset_index())
        daily = d.groupby(d["발생일"].dt.strftime("%m/%d"))["불량수량"].sum().reset_index()
        daily.columns = ["일자", "불량수량"]
        proc = d.groupby("발견 공정")["불량수량"].sum().reset_index()
        parts.append(f"### {t} (이번 주 {int(d['불량수량'].sum())}개, {len(d)}건)\n"
                     f"라인·품번·출하처·발견 공정 상위:\n{_df_text(detail)}\n"
                     f"일자별 수량:\n{_df_text(daily)}\n발견 공정별 수량:\n{_df_text(proc)}")

    ch = "\n".join(f"- [{c['규칙']}] {c['내용']}" for c in changes) or "- 해당 없음"
    parts.append("## 3. 변화점 감지 결과\n" + ch)
    parts.append("## 4. 현장 메모 원문\n" + (memo.strip() or "(현장 메모 없음)"))
    if last_report:
        body = last_report.get("cause_section") or last_report.get("full_text", "")
        parts.append(f"## 5. 지난주 리포트 '원인 추정 · 다음 주 조치' 본문 ({last_report.get('title', '')})\n{body}")
    else:
        parts.append("## 5. 지난주 리포트\n(제공되지 않음)")
    parts.append("위 자료로 TOP3 각 유형에 대해 원인과 제거방안을 rank 순서대로 제안하라.")
    return "\n\n".join(parts)


# ── 호출 / 파싱 ──────────────────────────────────────────────
def _extract_json(text: str) -> dict:
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if m:
        t = m.group(1)
    start, end = t.find("{"), t.rfind("}")
    data = json.loads(t[start:end + 1] if start >= 0 else t)
    if isinstance(data, list):
        data = {"proposals": data}
    if "proposals" not in data or not isinstance(data["proposals"], list):
        raise ValueError("proposals 필드가 없습니다")
    return data


def _call(client: anthropic.Anthropic, model: str, system: str, user: str, structured: bool) -> str:
    kwargs = dict(model=model, max_tokens=16000, system=system,
                  messages=[{"role": "user", "content": user}])
    if structured:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": PROPOSAL_SCHEMA}}
        resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"],
                                           fallbacks="default", **kwargs)
    else:
        resp = client.messages.create(**kwargs)
    if resp.stop_reason == "refusal":
        raise RuntimeError("모델이 요청을 거절했습니다 (refusal).")
    text = "".join(b.text for b in resp.content if b.type == "text")
    if resp.stop_reason == "max_tokens":
        raise ValueError("응답이 최대 길이에서 잘렸습니다.")
    return text


def suggest(user_prompt: str) -> dict:
    """반환: {'ok': bool, 'data': dict|None, 'raw': str, 'error': str}"""
    s = api_settings()
    if not s["has_key"]:
        return {"ok": False, "data": None, "raw": "", "error": "API 키가 없습니다."}
    system = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    client = anthropic.Anthropic(timeout=s["timeout"], max_retries=1)
    structured = True
    raw, last_err = "", ""
    for _ in range(2):  # JSON 파싱 실패 시 1회 재시도
        try:
            raw = _call(client, s["model"], system, user_prompt, structured)
        except anthropic.BadRequestError as e:
            if structured:  # 모델이 구조화 출력/폴백을 지원하지 않으면 일반 호출로 재시도
                structured = False
                last_err = f"요청 형식 오류: {e.message}"
                continue
            return {"ok": False, "data": None, "raw": raw, "error": f"요청 형식 오류: {e.message}"}
        except anthropic.AuthenticationError:
            return {"ok": False, "data": None, "raw": "", "error": "API 키가 올바르지 않습니다 (.env 확인)."}
        except anthropic.PermissionDeniedError:
            return {"ok": False, "data": None, "raw": "", "error": "API 키에 이 모델 사용 권한이 없습니다."}
        except anthropic.NotFoundError:
            return {"ok": False, "data": None, "raw": "", "error": f"모델 '{s['model']}'을 찾을 수 없습니다 (.env의 ANTHROPIC_MODEL 확인)."}
        except anthropic.RateLimitError:
            return {"ok": False, "data": None, "raw": "", "error": "요청 한도 초과입니다. 잠시 후 다시 시도하세요."}
        except anthropic.APITimeoutError:
            return {"ok": False, "data": None, "raw": "", "error": f"응답 시간 초과 ({s['timeout']:.0f}초)."}
        except anthropic.APIStatusError as e:
            return {"ok": False, "data": None, "raw": "", "error": f"API 오류 ({e.status_code}): {e.message}"}
        except anthropic.APIConnectionError:
            return {"ok": False, "data": None, "raw": "", "error": "네트워크 연결 오류입니다."}
        except (RuntimeError, ValueError) as e:
            last_err = str(e)
            continue
        try:
            return {"ok": True, "data": _extract_json(raw), "raw": raw, "error": ""}
        except (ValueError, json.JSONDecodeError) as e:
            last_err = f"JSON 파싱 실패: {e}"
    return {"ok": False, "data": None, "raw": raw, "error": last_err}


def proposals_to_markdown(proposals: list[dict], week: str) -> str:
    lines = [f"# {week} TOP3 불량 원인·제거방안 제안", ""]
    for p in proposals:
        lines += [f"## {p.get('rank', '')}순위 {p.get('defect_type', '')}", "",
                  f"**현상**: {p.get('phenomenon', '')}", "", "**추정 원인**", ""]
        for c in p.get("suspected_causes", []):
            lines.append(f"- [{c.get('category', '')}] {c.get('cause', '')} "
                         f"({c.get('evidence_status', '')}, 신뢰도 {c.get('confidence', '')}) — 근거: {c.get('evidence', '')}")
        for title, key in [("확인 방법", "verification"), ("단기 조치 (1주 이내)", "short_term"), ("근본 대책", "permanent")]:
            lines += ["", f"**{title}**", ""] + [f"- {x}" for x in p.get(key, [])]
        lines += ["", f"**담당 부서**: {p.get('owner', '')}  ",
                  f"**관련 클레임**: {p.get('claim_link', '')}  ",
                  f"**지난주 조치 평가**: {p.get('last_week_check', '')}", ""]
    return "\n".join(lines)
