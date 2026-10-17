#!/usr/bin/env python3
"""웹 ERD 뷰어 사본 관리 (관리자용 -- 사용자는 필요 없음).

skills/data-light/viewer/dataviewer 는 data-expert-framework 의 runtime/viewer/dataviewer 를 **정해 둔 커밋 그대로** 담은 사본이다.
고치지 않는다 -- 원본에서 고치고 이 도구로 다시 받는다. 무엇을 담았는지는 skills/data-light/viewer/viewer.lock.json.
이 사본은 저작권자의 결정(2026-10-17)으로 이 저장소의 MIT 라이선스로 공개된다 (skills/data-light/viewer/NOTICE.md).

    python tools/update_viewer.py --check                                   # 사본이 잠금과 같은지 (인터넷 필요 없음)
    python tools/update_viewer.py --from ../data-expert-framework --ref <커밋>

파이썬 표준 라이브러리와 git 만 쓴다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "skills" / "data-light" / "viewer"
LOCK = DEST / "viewer.lock.json"
SRC = "runtime/viewer/dataviewer"
FILES = ("__init__.py", "__main__.py", "layout.py", "server.py", "sources.py", "static/viewer.html")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def check() -> list[str]:
    try:
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"잠금 파일을 읽을 수 없다: {exc}"]
    errs = []
    for name, h in lock.get("files", {}).items():
        p = DEST / "dataviewer" / name
        if not p.is_file():
            errs.append(f"없음: {name}")
        elif _sha(p.read_bytes()) != h:
            errs.append(f"잠금과 다름: {name} (사본을 고치지 않는다 -- 원본에서 고치고 다시 받는다)")
    extra = sorted(str(p.relative_to(DEST / "dataviewer")).replace("\\", "/") for p in (DEST / "dataviewer").rglob("*")
                   if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    errs += [f"잠금에 없는 파일: {x}" for x in extra if x not in lock.get("files", {})]
    return errs


def update(src_repo: Path, ref: str) -> None:
    def show(path: str) -> bytes:
        r = subprocess.run(["git", "-C", str(src_repo), "show", f"{ref}:{path}"], capture_output=True)
        if r.returncode != 0:
            sys.exit(f"git show {ref}:{path} 실패: {r.stderr.decode('utf-8', 'replace').strip()}")
        return r.stdout
    commit = subprocess.run(["git", "-C", str(src_repo), "rev-parse", ref], capture_output=True, text=True).stdout.strip()
    files = {}
    for name in FILES:
        data = show(f"{SRC}/{name}")
        out = DEST / "dataviewer" / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        files[name] = _sha(data)
    import re
    ver = re.search(rb'__version__ = "([^"]+)"', show(f"{SRC}/__init__.py"))
    LOCK.write_text(json.dumps({"about": "data-expert-framework 의 runtime/viewer/dataviewer 사본 (바이트 그대로). 고치지 않는다 -- "
                                         "원본에서 고치고 tools/update_viewer.py 로만 바꾼다.",
                                "source": "sungbeom78/data-expert-framework (runtime/viewer)", "commit": commit,
                                "version": ver.group(1).decode() if ver else "?", "files": files},
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] 뷰어 {commit[:7]} 을 {DEST.relative_to(ROOT)} 에 담음 ({len(files)}개 파일)")


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--from", dest="src", default=str(ROOT.parent / "data-expert-framework"))
    ap.add_argument("--ref", default="main")
    a = ap.parse_args(argv)
    if a.check:
        errs = check()
        print("\n".join(f"FAIL {e}" for e in errs) if errs else "PASS -- 뷰어 사본이 잠금과 같음")
        return 1 if errs else 0
    update(Path(a.src), a.ref)
    return 0


if __name__ == "__main__":
    sys.exit(main())
