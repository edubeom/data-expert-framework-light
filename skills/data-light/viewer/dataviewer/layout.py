"""엔터티 위치 -- 원본 옆 `<원본 파일 이름>.layout.json` (원본은 고치지 않는다).

    {"layout_version": 1, "source": "model.json", "positions": {"public.student": {"x": 40, "y": 60}}}
"""
from __future__ import annotations

import json
import math
import os
import tempfile
import time
from pathlib import Path

LAYOUT_VERSION = 1
MAX_TABLES = 5000
LIMIT = 1_000_000          # 좌표 범위 (화면 밖으로 날아간 값 막기)


class LayoutError(ValueError):
    pass


def layout_path(source) -> Path:
    p = Path(source)
    return p.with_name(p.name + ".layout.json")


def load(source) -> dict:
    """저장된 위치 {key: {x, y}} -- 없거나 깨졌으면 빈 dict (화면은 자동 배치로 그린다)."""
    f = layout_path(source)
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    pos = data.get("positions") if isinstance(data, dict) else None
    if not isinstance(pos, dict):
        return {}
    out = {}
    for k, v in pos.items():
        try:
            out[str(k)] = clean_point(v)
        except LayoutError:
            continue
    return out


def clean_point(v) -> dict:
    if not isinstance(v, dict):
        raise LayoutError("위치는 {x, y} 여야 한다")
    try:
        x, y = float(v["x"]), float(v["y"])
    except (KeyError, TypeError, ValueError):
        raise LayoutError("위치는 {x, y} 숫자여야 한다") from None
    if not (math.isfinite(x) and math.isfinite(y)) or abs(x) > LIMIT or abs(y) > LIMIT:
        raise LayoutError("위치 값이 범위를 벗어났다")
    return {"x": round(x, 1), "y": round(y, 1)}


def save(source, positions: dict, known_keys) -> dict:
    """원본에 있는 엔터티의 위치만 받아, 이미 저장된 위치(지금 원본에 잠시 없는 엔터티 것까지)에 합쳐 원자적으로 바꿔 쓴다."""
    if not isinstance(positions, dict) or len(positions) > MAX_TABLES:
        raise LayoutError("positions 는 {엔터티: {x, y}} 여야 한다")
    known = set(known_keys)
    clean = {}
    for k, v in positions.items():
        if k in known:
            clean[k] = clean_point(v)
    f = layout_path(source)
    merged = dict(load(source))
    merged.update(clean)
    body = json.dumps({"layout_version": LAYOUT_VERSION, "source": Path(source).name,
                       "positions": dict(sorted(merged.items()))}, ensure_ascii=False, indent=1) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".layout-", suffix=".tmp", dir=str(f.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        for i in range(6):                              # Windows: 다른 프로그램(백신·동기화)이 잠깐 열고 있으면 잠시 뒤 다시
            try:
                os.replace(tmp, f)
                break
            except PermissionError:
                if i == 5:
                    raise
                time.sleep(0.05 * (i + 1))
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise LayoutError(f"위치 파일을 쓸 수 없다: {exc}") from None
    return clean
