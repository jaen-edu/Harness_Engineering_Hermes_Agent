"""업체 마스터(config/vendors.yaml) 읽기와 업체 자동 인식."""
import re
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "vendors.yaml"


def load_vendors(path=CONFIG_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    vendors = []
    for v in data.get("vendors", []):
        vendors.append({
            "code": str(v["code"]),
            "name": str(v.get("name", v["code"])),
            "aliases": [str(a) for a in v.get("aliases", [])],
            "file_keywords": [str(k) for k in v.get("file_keywords", [])],
            "reading_notes": str(v.get("reading_notes", "") or ""),
        })
    return vendors


def _norm(s: str) -> str:
    s = str(s or "")
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사", "", s)
    return re.sub(r"[\s()\[\]_\-.]", "", s)


def detect_by_filename(filename: str, vendors: list[dict]):
    name = _norm(Path(filename).stem)
    # 긴 키워드부터 비교해 '한성'이 '한성유압정공'보다 먼저 걸리지 않게 한다
    cands = [(len(k), v["code"]) for v in vendors for k in v["file_keywords"] if _norm(k) and _norm(k) in name]
    return max(cands)[1] if cands else None


def detect_by_name(supplier: str, vendors: list[dict]):
    s = _norm(supplier)
    if not s:
        return None
    for v in vendors:
        for a in v["aliases"] + [v["name"]]:
            a = _norm(a)
            if a and (a == s or a in s or s in a):
                return v["code"]
    return None


def vendor_by_code(code, vendors):
    return next((v for v in vendors if v["code"] == code), None)


def vendor_name(code, vendors, fallback=None) -> str:
    v = vendor_by_code(code, vendors)
    return v["name"] if v else (fallback or str(code))
