# AGENTS.md — data-expert-framework-light

이 저장소는 비전공자·작은 시스템용 데이터 설계 스킬(`skills/data-light`)과 도구(`datalight.py`)입니다.

## 에이전트가 사용자를 도울 때
- `skills/data-light/SKILL.md` 의 흐름을 따른다: 질문은 쉽게 3~5개, 기술 결정은 에이전트가 하고 이유를 한 줄로 공유.
- DB 를 만들거나 바꾸거나 지우기, 파일을 DB 에 넣기는 **사용자 확인 후에만**. 확인한 답은 `--approval` 로 그대로 기록.
- 개인정보 칸은 `pi_` 테이블로 분리한다. 비밀번호는 저장하지 않는다.

## 이 저장소를 고칠 때
- 의존성은 파이썬 표준 라이브러리만 (openpyxl 은 선택). 새 패키지를 필수로 만들지 않는다.
- 정본 형식(`references/format.md`)을 바꾸면 `upgrade` 와 시험도 같이 고친다. 형식은 전문판 `model.json` 의 부분집합을 유지한다.
- 고친 뒤: `python -X dev -W error::ResourceWarning tests/test_datalight.py` (pytest 도 가능).
- 버전을 올릴 때는 `VERSION`·`datalight.py` 의 `__version__`·`.claude-plugin/*.json` 을 함께 (시험이 맞는지 본다). dev-process-light 가 이 버전을 짝으로 고정해 쓴다.
- 사용자에게 보이는 말은 쉬운 한국어로.

## 교훈 (실수 기록)
- 2026-10-14 Windows 에서 시험 실패: SQLite 연결·파일을 닫지 않으면 Windows 는 임시 폴더를 지우지 못한다(WinError 32).
  DB 연결은 `try/finally: con.close()`, 파일은 `with open(...)`. 시험은 `python -X dev -W error::ResourceWarning` 으로 돌려 닫지 않은 것을 실패로 잡는다 (CI 도 동일).
- 2026-10-14 CI 실패 두 가지: ① `Path.write_text(newline=)` 은 Python 3.10+ → 3.9 에서 오류. 파일 쓰기는 `_write()` 로.
  ② Windows 파이프 출력은 cp1252 라 한글이 ???? → 출력은 항상 UTF-8 로 재설정. 시험의 `run()` 은 `PYTHONIOENCODING=cp1252` 로 Windows 를 흉내 낸다.
  고친 뒤에는 최저 지원 버전(3.9)에서도 시험한다: `uv python install 3.9` → `$(uv python find 3.9) tests/test_datalight.py`.
