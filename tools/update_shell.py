#!/usr/bin/env python3
"""개발 관리 사이트 화면 틀 사본 관리 (관리자용 -- 사용자는 필요 없음).

skills/data-light/site/shell 은 data-expert-framework 의 runtime/outputs-shell 을 **정해 둔 커밋 그대로** 담은 사본이다.
고치지 않는다 -- 원본에서 고치고 이 도구로 다시 받는다. 무엇을 담았는지는 skills/data-light/site/shell.lock.json
(파일마다 sha256 + 전문판과 같은 방식의 틀 지문). 이 사본은 저작권자의 결정(2026-10-20, D5)으로 이 저장소의 MIT 라이선스로 공개된다
(skills/data-light/site/NOTICE.md).

    python tools/update_shell.py --check                                   # 사본이 잠금과 같은지 (인터넷 필요 없음)
    python tools/update_shell.py --from ../data-expert-framework --ref <커밋>

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
DEST = ROOT / "skills" / "data-light" / "site"
SHELL = DEST / "shell"
LOCK = DEST / "shell.lock.json"
SRC = "runtime/outputs-shell"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fingerprint(d: Path) -> str:
    """전문판 outputs.shell_fingerprint 와 같은 셈 -- 상대 경로와 내용(줄 끝 맞춤)."""
    h = hashlib.sha256()
    for f in sorted(p for p in d.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store"):
        h.update(f.relative_to(d).as_posix().encode("utf-8") + b"\0")
        h.update(f.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()[:16]


def check() -> list[str]:
    try:
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"잠금 파일을 읽을 수 없다: {exc}"]
    errs = []
    for name, h in lock.get("files", {}).items():
        p = SHELL / name
        if not p.is_file():
            errs.append(f"없음: {name}")
        elif _sha(p.read_bytes().replace(b"\r\n", b"\n")) != h:
            errs.append(f"잠금과 다름: {name} (사본을 고치지 않는다 -- 원본에서 고치고 다시 받는다)")
    extra = sorted(p.relative_to(SHELL).as_posix() for p in SHELL.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    errs += [f"잠금에 없는 파일: {x}" for x in extra if x not in lock.get("files", {})]
    if not errs and lock.get("fingerprint") != fingerprint(SHELL):
        errs.append("틀 지문이 잠금과 다르다")
    return errs


def update(src_repo: Path, ref: str) -> None:
    def git(*a) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(src_repo), *a], capture_output=True)
    commit = git("rev-parse", ref).stdout.decode().strip()
    r = git("ls-tree", "-r", "--name-only", ref, "--", SRC)
    if r.returncode != 0 or not r.stdout.strip():
        sys.exit(f"{ref} 에 {SRC} 가 없다: {r.stderr.decode('utf-8', 'replace').strip()}")
    names = [x[len(SRC) + 1:] for x in r.stdout.decode("utf-8").splitlines() if x.startswith(SRC + "/")]
    if SHELL.exists():
        for p in sorted(SHELL.rglob("*"), reverse=True):        # 지난 사본을 비운다 (잠금에 없는 파일이 남지 않게)
            p.unlink() if p.is_file() else p.rmdir()
    files = {}
    for name in names:
        data = git("show", f"{ref}:{SRC}/{name}").stdout.replace(b"\r\n", b"\n")
        out = SHELL / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        files[name] = _sha(data)
    ver = (SHELL / "VERSION").read_text(encoding="utf-8").strip()
    LOCK.write_text(json.dumps({"about": "data-expert-framework 의 runtime/outputs-shell 사본 (바이트 그대로, 줄 끝 LF). 고치지 않는다 -- "
                                         "원본에서 고치고 tools/update_shell.py 로만 바꾼다.",
                                "source": "sungbeom78/data-expert-framework (runtime/outputs-shell)", "commit": commit,
                                "version": ver, "fingerprint": fingerprint(SHELL), "files": files},
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] 화면 틀 {ver} ({commit[:7]}) 을 {SHELL.relative_to(ROOT)} 에 담음 ({len(files)}개 파일)")


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
        print("\n".join(f"FAIL {e}" for e in errs) if errs else "PASS -- 화면 틀 사본이 잠금과 같음")
        return 1 if errs else 0
    update(Path(a.src), a.ref)
    return 0


if __name__ == "__main__":
    sys.exit(main())
