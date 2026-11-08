"""파일 읽기, 열 정리, 주차 계산, 입력 검증."""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from docx import Document

import config


@dataclass
class LoadResult:
    data: pd.DataFrame
    errors: list[str] = field(default_factory=list)      # 파일 단위 오류 (읽기 실패, 필수 열 없음)
    warnings: list[str] = field(default_factory=list)    # 참고 경고 (파일명 주차 불일치 등)


def _name(src) -> str:
    return Path(getattr(src, "name", str(src))).name


def _read_table(src) -> pd.DataFrame:
    name = _name(src).lower()
    if name.endswith(".csv"):
        raw = src.getvalue() if hasattr(src, "getvalue") else Path(src).read_bytes()
        for enc in ("utf-8-sig", "cp949"):
            try:
                return pd.read_csv(io.BytesIO(raw), encoding=enc)
            except UnicodeDecodeError:
                continue
        raise ValueError("CSV 인코딩을 읽을 수 없습니다 (UTF-8 또는 CP949만 지원)")
    return pd.read_excel(src, sheet_name=0)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """열 이름 앞뒤 공백 제거 + 별칭을 표준 이름으로 변환."""
    canon = {re.sub(r"\s+", "", c): c for c in config.DEFECT_REQUIRED + config.PRODUCTION_REQUIRED}
    aliases = {re.sub(r"\s+", "", k): v for k, v in config.COLUMN_ALIASES.items()}
    rename = {}
    for col in df.columns:
        key = re.sub(r"\s+", "", str(col))
        if key in canon:
            rename[col] = canon[key]
        elif key in aliases:
            rename[col] = aliases[key]
        else:
            rename[col] = str(col).strip()
    return df.rename(columns=rename)


def normalize_line(value) -> str:
    """'1 라인', '1라인 ', 'Line1' 등의 표기를 '1라인'으로 통일."""
    s = re.sub(r"\s+", "", str(value))
    m = re.fullmatch(r"(?i)(?:line)?(\d+)(?:라인|line)?", s)
    return f"{m.group(1)}라인" if m else s


def iso_week_label(d) -> str:
    return f"W{pd.Timestamp(d).isocalendar().week:02d}"


def week_sort_key(w: str) -> int:
    m = re.search(r"\d+", str(w))
    return int(m.group()) if m else 0


# ── 생산수량 ─────────────────────────────────────────────────
def load_production(src) -> LoadResult:
    try:
        df = normalize_columns(_read_table(src))
    except Exception as e:  # noqa: BLE001
        return LoadResult(pd.DataFrame(), [f"{_name(src)}: 파일을 읽을 수 없습니다 ({e})"])
    missing = [c for c in config.PRODUCTION_REQUIRED if c not in df.columns]
    if missing:
        return LoadResult(pd.DataFrame(), [f"{_name(src)}: 필수 열 없음 → {', '.join(missing)}"])
    df = df[config.PRODUCTION_REQUIRED].copy()
    df["주차"] = df["주차"].astype(str).str.strip().str.upper()
    df["라인"] = df["라인"].map(normalize_line)
    df["생산수량"] = pd.to_numeric(df["생산수량"], errors="coerce")
    df["근무일수"] = pd.to_numeric(df["근무일수"], errors="coerce")
    warnings = []
    bad = df["생산수량"].isna() | (df["생산수량"] <= 0)
    if bad.any():
        warnings.append(f"생산수량이 숫자가 아니거나 0 이하인 행 {int(bad.sum())}개를 제외했습니다.")
        df = df[~bad]
    return LoadResult(df.reset_index(drop=True), [], warnings)


# ── 불량기록 ─────────────────────────────────────────────────
def load_defects(sources, production: pd.DataFrame | None = None) -> LoadResult:
    """여러 불량기록 파일을 합치고 검증한다. 문제 행은 '문제' 열에 사유를 적어 남긴다."""
    frames, errors, warnings = [], [], []
    for src in sources:
        name = _name(src)
        try:
            df = normalize_columns(_read_table(src))
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: 파일을 읽을 수 없습니다 ({e})")
            continue
        missing = [c for c in config.DEFECT_REQUIRED if c not in df.columns]
        if missing:
            errors.append(f"{name}: 필수 열 없음 → {', '.join(missing)}  (현재 열: {', '.join(map(str, df.columns))})")
            continue
        df = df[config.DEFECT_REQUIRED].copy()
        df.insert(0, "원본파일", name)
        df.insert(1, "원본행", range(2, len(df) + 2))  # 엑셀 행 번호 (헤더 1행)
        frames.append(df)

    if not frames:
        return LoadResult(pd.DataFrame(), errors, warnings)

    df = pd.concat(frames, ignore_index=True)
    problems = [[] for _ in range(len(df))]

    def flag(mask, msg):
        for i in df.index[mask]:
            problems[i].append(msg)

    # 문자열 정리
    for c in ["품번", "품명", "출하처", "불량유형", "발견 공정", "조치", "기록자"]:
        df[c] = df[c].astype(str).str.strip()
    df["라인"] = df["라인"].map(normalize_line)

    # 발생일 → 주차
    df["발생일"] = pd.to_datetime(df["발생일"], errors="coerce")
    flag(df["발생일"].isna(), "발생일 형식 오류")
    df["주차"] = df["발생일"].map(lambda d: iso_week_label(d) if pd.notna(d) else "")

    # 불량수량
    qty = pd.to_numeric(df["불량수량"], errors="coerce")
    flag(qty.isna(), "불량수량이 숫자가 아님")
    flag(qty.notna() & (qty <= 0), "불량수량이 0 이하")
    df["불량수량"] = qty

    # 생산수량과 매칭
    if production is not None and not production.empty:
        lines = set(production["라인"])
        weeks = set(production["주차"])
        flag(~df["라인"].isin(lines), "생산수량에 없는 라인")
        flag((df["주차"] != "") & ~df["주차"].isin(weeks), "생산수량에 없는 주차")

    # 조치 표준화 (원문 보존)
    df["조치분류"] = df["조치"].where(df["조치"].isin(config.STANDARD_ACTIONS), "기타")

    df["문제"] = ["; ".join(p) for p in problems]

    # 파일명 주차 vs 발생일 주차 검증
    for name, g in df.groupby("원본파일"):
        m = re.search(r"W(\d{1,2})", name, re.I)
        if not m:
            continue
        fw = f"W{int(m.group(1)):02d}"
        others = sorted(set(g["주차"]) - {fw, ""}, key=week_sort_key)
        if others:
            n = int((~g["주차"].isin([fw, ""])).sum())
            warnings.append(f"{name}: 파일명은 {fw}인데 발생일 기준 {', '.join(others)} 행이 {n}개 있습니다 (발생일 기준으로 집계).")

    return LoadResult(df, errors, warnings)


def non_standard_actions(df: pd.DataFrame) -> pd.DataFrame:
    s = df.loc[df["조치분류"] == "기타", "조치"]
    return s.value_counts().rename_axis("조치 원문").reset_index(name="건수")


# ── 지난주 리포트 / 현장 메모 ────────────────────────────────
def load_last_report(src) -> dict:
    """docx 전체 본문과 '원인 추정 · 다음 주 조치' 절 본문을 돌려준다."""
    doc = Document(src)
    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    full = "\n".join(paras)
    cause, capture = [], False
    for t in paras:
        if re.match(r"^\d+\.\s", t):
            capture = ("원인" in t) or ("조치" in t)
            continue
        if capture:
            cause.append(t)
    tables = []
    for tb in doc.tables:
        tables.append("\n".join(" | ".join(c.text for c in r.cells) for r in tb.rows))
    title = paras[0] if paras else ""
    return {"title": title, "full_text": full, "cause_section": "\n".join(cause), "tables": tables}


def read_text(src) -> str:
    raw = src.getvalue() if hasattr(src, "getvalue") else Path(src).read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")
