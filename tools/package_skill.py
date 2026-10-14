#!/usr/bin/env python3
"""make release zips into dist/:
  data-light-skill-<ver>.zip    skill folder only (upload to Claude as a skill)
  data-expert-light-plugin-<ver>.zip   whole plugin (README, LICENSE, .claude-plugin, skills)"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"__pycache__", ".pytest_cache", "dist", ".git"}


def files(base: Path):
    for p in sorted(base.rglob("*")):
        if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP) and p.suffix not in (".pyc", ".db") \
                and p.name != "spec.xlsx":
            yield p


def main():
    ver = (ROOT / "VERSION").read_text().strip()
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    skill = ROOT / "skills" / "data-light"
    a = dist / f"data-light-skill-{ver}.zip"
    with zipfile.ZipFile(a, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files(skill):
            z.write(p, Path("data-light") / p.relative_to(skill))
        z.write(ROOT / "LICENSE", "data-light/LICENSE")
    b = dist / f"data-expert-light-plugin-{ver}.zip"
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for top in ("README.md", "LICENSE", "VERSION", "CHANGELOG.md", "AGENTS.md", "CLAUDE.md"):
            z.write(ROOT / top, top)
        for p in list(files(ROOT / ".claude-plugin")) + list(files(ROOT / "skills")):
            z.write(p, p.relative_to(ROOT))
    for f in (a, b):
        print(f"{f.relative_to(ROOT)}  {f.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
