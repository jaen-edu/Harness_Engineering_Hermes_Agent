"""입력 폴더에서 엑셀 파일을 찾아 읽고, 이번 집계에 쓸 파일을 고른다.

폴더에 지난 분기 파일이 쌓여 있어도 되도록
- 출하실적: 출하일 기준 가장 최근 분기의 파일만 쓴다.
- 분기목표: 폴더의 모든 파일을 합쳐 읽고, 분기 열로 이번 분기 행만 쓴다(calc.compute).
- 지난분기 집계표: 제목이 직전 분기인 파일을 고른다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

import calc

BASE = Path(__file__).resolve().parent / "입력파일"
SHIP_DIR = BASE / "1_출하실적"
TARGET_DIR = BASE / "2_분기목표"
LAST_DIR = BASE / "3_지난분기집계표"


def ensure_folders() -> None:
    for d in (SHIP_DIR, TARGET_DIR, LAST_DIR):
        d.mkdir(parents=True, exist_ok=True)


def excel_files(folder: Path) -> list[Path]:
    """엑셀 파일 목록(엑셀이 열어 둔 임시 파일 '~$...'은 뺀다)."""
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.glob("*.xlsx") if p.is_file() and not p.name.startswith(("~$", ".")))


def open_folder(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    os.startfile(folder)  # Windows 탐색기로 열기


@dataclass
class Picked:
    used: list = field(default_factory=list)       # 읽은 파일 객체
    skipped: list[str] = field(default_factory=list)  # 건너뛴 파일 안내
    errors: list[str] = field(default_factory=list)   # 집계를 멈춰야 하는 문제


def _read(reader, path: Path):
    try:
        return reader(path.name, path.read_bytes()), None
    except PermissionError:
        return None, f"'{path.name}' 파일을 읽을 수 없습니다. 엑셀에서 열려 있다면 닫고 다시 읽어 주세요."
    except calc.StopError as exc:
        return None, str(exc)


def pick_shipments() -> Picked:
    out = Picked()
    files = []
    for p in excel_files(SHIP_DIR):
        f, err = _read(calc.read_shipments, p)
        if err:
            out.errors.append(err)
        elif f.main_month is None:
            out.skipped.append(f"{p.name}: 출하 행이 없어 건너뜀")
        else:
            files.append(f)
    if not files:
        return out
    quarter_of = lambda f: (f.main_month[0], (f.main_month[1] - 1) // 3 + 1)
    latest = max(quarter_of(f) for f in files)
    for f in sorted(files, key=lambda f: f.main_month):
        if quarter_of(f) == latest:
            out.used.append(f)
        else:
            y, q = quarter_of(f)
            out.skipped.append(f"{f.name}: {calc.quarter_label(y, q)} 파일이라 이번 집계에서 제외")
    return out


def pick_targets() -> Picked:
    """폴더의 분기목표 파일을 모두 읽어 하나로 합친다."""
    out = Picked()
    parts = []
    for p in excel_files(TARGET_DIR):
        f, err = _read(calc.read_targets, p)
        if err:
            out.errors.append(err)
        else:
            parts.append(f)
    if parts:
        rows = pd.concat([f.rows.assign(행=f.rows["행"].map(lambda r, n=f.name: f"{n} {r}")) for f in parts],
                         ignore_index=True)
        quarters = list(dict.fromkeys(q for f in parts for q in f.quarters))
        out.used.append(calc.TargetFile(", ".join(f.name for f in parts), rows, quarters))
    return out


def pick_last_quarter(prev_label: str | None) -> Picked:
    """직전 분기(prev_label) 집계표를 고른다. 없으면 가장 최근에 수정한 파일."""
    out = Picked()
    found = []
    for p in excel_files(LAST_DIR):
        f, err = _read(calc.read_last_quarter, p)
        if err:
            out.errors.append(err)
        else:
            found.append((p.stat().st_mtime, f))
    if not found:
        return out
    match = [f for _, f in found if prev_label and f.label == prev_label]
    chosen = match[0] if match else max(found, key=lambda t: t[0])[1]
    if prev_label and chosen.label != prev_label:
        chosen.warnings.append(
            f"지난분기 집계표 폴더에 {prev_label} 파일이 없어 '{chosen.name}'({chosen.label or '분기 미확인'})과 비교했습니다.")
    out.used.append(chosen)
    out.skipped += [f"{f.name}: {f.label or '분기 미확인'} 파일이라 사용 안 함" for _, f in found if f is not chosen]
    return out


def prev_quarter_label(ships: list[calc.ShipmentFile]) -> str | None:
    if not ships:
        return None
    y, m = max(f.main_month for f in ships)
    q = (m - 1) // 3 + 1
    return calc.quarter_label(y, q - 1) if q > 1 else calc.quarter_label(y - 1, 4)
