"""Claude API 호출 — .env에서 키·모델을 읽고, 정해진 JSON 모양으로 답을 받는다."""
import json
import os

import anthropic
from dotenv import dotenv_values

from core.common import APP_DIR

ENV_PATH = APP_DIR / ".env"
DEFAULT_MODEL = "claude-sonnet-5-5"
PLACEHOLDER = "여기에_API_키_붙여넣기"
MAX_RETRIES = 2  # 설계서 5.10: 2회 재시도 (SDK가 429·5xx·연결 오류를 자동 재시도)
TIMEOUT_SECONDS = 180

# 서버 측 거절 대비(fallbacks: "default")를 받는 모델
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}


class AIError(RuntimeError):
    """사용자에게 그대로 보여 줄 수 있는 AI 오류."""


def _settings():
    # .env 파일 값을 우선 쓰고, 없을 때만 PC 환경변수를 본다 (화면에서 저장한 값이 바로 반영되도록 매번 읽음)
    env = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    key = (env.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "").strip()
    model = (env.get("CLAUDE_MODEL") or os.getenv("CLAUDE_MODEL") or "").strip() or DEFAULT_MODEL
    if key == PLACEHOLDER:
        key = ""
    return key, model


def save_settings(key=None, model=None):
    """API 키·모델명을 .env 파일에 저장한다 (다른 줄은 그대로 둔다)."""
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else [
        "# API 키 (다른 사람에게 이 파일을 주지 마세요)"]
    values = {}
    if key is not None:
        values["ANTHROPIC_API_KEY"] = key.strip()
    if model is not None:
        values["CLAUDE_MODEL"] = model.strip() or DEFAULT_MODEL
    for name, val in values.items():
        for i, line in enumerate(lines):
            if line.split("=", 1)[0].strip() == name:
                lines[i] = f"{name}={val}"
                break
        else:
            lines.append(f"{name}={val}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_connection():
    """짧은 호출로 키·모델을 확인한다. 실패하면 AIError."""
    cm = get_client()
    if cm is None:
        raise AIError("API 키가 없습니다.")
    client, model = cm
    try:
        client.with_options(max_retries=0, timeout=30).messages.create(
            model=model, max_tokens=16, messages=[{"role": "user", "content": "ping"}])
    except anthropic.AuthenticationError as e:
        raise AIError("API 키가 올바르지 않습니다.") from e
    except anthropic.NotFoundError as e:
        raise AIError(f"모델 '{model}'을(를) 찾을 수 없습니다.") from e
    except anthropic.APIStatusError as e:
        raise AIError(f"연결 실패 (오류 {e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise AIError("연결 실패. 인터넷 연결을 확인해 주세요.") from e
    return model


def status():
    """(키 있음 여부, 모델명)."""
    key, model = _settings()
    return bool(key), model


def get_client():
    """키가 있으면 (client, model), 없으면 None."""
    key, model = _settings()
    if not key:
        return None
    client = anthropic.Anthropic(api_key=key, max_retries=MAX_RETRIES, timeout=TIMEOUT_SECONDS)
    return client, model


def _create(client, model, system, content, schema, effort, max_tokens):
    params = dict(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
        # 설계서는 tool_choice 강제를 적었으나 Sonnet 5.5/Opus 5.5는 강제 도구 호출을 거부(400)하므로
        # 같은 목적(항상 같은 모양의 JSON)을 구조화 출력으로 보장한다.
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )
    if model in FALLBACK_MODELS:
        return client.beta.messages.create(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params
        )
    return client.messages.create(**params)


def call_tool(system, content, schema, effort="medium", max_tokens=16000, client_model=None):
    """지시문 + 입력 블록 → 스키마 모양의 dict.

    client_model: 테스트용 (client, model). 없으면 .env 설정으로 만든다.
    """
    cm = client_model or get_client()
    if cm is None:
        raise AIError("API 키가 없습니다. .env 파일에 ANTHROPIC_API_KEY를 넣어 주세요.")
    client, model = cm

    last_problem = None
    for _ in range(2):  # JSON이 깨져 오면 한 번 더 요청
        try:
            resp = _create(client, model, system, content, schema, effort, max_tokens)
        except anthropic.AuthenticationError as e:
            raise AIError("API 키가 올바르지 않습니다. .env의 ANTHROPIC_API_KEY를 확인해 주세요.") from e
        except anthropic.PermissionDeniedError as e:
            raise AIError("이 API 키로는 해당 모델을 쓸 수 없습니다.") from e
        except anthropic.NotFoundError as e:
            raise AIError(f"모델 '{model}'을(를) 찾을 수 없습니다. .env의 CLAUDE_MODEL을 확인해 주세요.") from e
        except anthropic.RateLimitError as e:
            raise AIError("AI 사용 한도를 넘었습니다. 잠시 후 다시 시도해 주세요.") from e
        except anthropic.BadRequestError as e:
            raise AIError(f"AI 요청 오류: {e.message}") from e
        except anthropic.APIStatusError as e:
            raise AIError(f"AI 연결 실패 (서버 오류 {e.status_code}). 잠시 후 다시 시도해 주세요.") from e
        except anthropic.APIConnectionError as e:
            raise AIError("AI 연결 실패. 인터넷 연결을 확인해 주세요.") from e

        if resp.stop_reason == "refusal":
            raise AIError("AI가 이 요청을 처리하지 않았습니다(안전 정책). 내용을 확인해 주세요.")
        if resp.stop_reason == "max_tokens":
            last_problem = "AI 답변이 너무 길어 잘렸습니다."
            max_tokens = min(max_tokens * 2, 32000)
            continue
        texts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        if not texts:
            last_problem = "AI가 답변을 돌려주지 않았습니다."
            continue
        try:
            return json.loads(texts[-1])
        except json.JSONDecodeError:
            last_problem = "AI 답변 형식이 올바르지 않습니다."
    raise AIError(last_problem or "AI 호출 실패")
