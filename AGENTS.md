# AGENTS.md — data-expert-framework-light

이 저장소는 비전공자·작은 시스템용 데이터 설계 스킬(`skills/data-light`)과 도구(`datalight.py`)입니다.

## 에이전트가 사용자를 도울 때
- `skills/data-light/SKILL.md` 의 흐름을 따른다: 질문은 쉽게 3~5개, 기술 결정은 에이전트가 하고 이유를 한 줄로 공유.
- DB 를 만들거나 바꾸거나 지우기, 파일을 DB 에 넣기는 **사용자 확인 후에만**. 확인한 답은 `--approval` 로 그대로 기록.
- 개인정보 칸은 `pi_` 테이블로 분리한다. 비밀번호는 저장하지 않는다.

## 이 저장소를 고칠 때
- 의존성은 파이썬 표준 라이브러리만 (openpyxl 은 선택). 새 패키지를 필수로 만들지 않는다.
- 정본 형식(`references/format.md`)을 바꾸면 `upgrade` 와 시험도 같이 고친다. 형식은 전문판 `model.json` 의 부분집합을 유지한다.
- 고친 뒤: `python -m pytest tests -q` (pytest 가 없으면 `python tests/test_datalight.py`).
- 사용자에게 보이는 말은 쉬운 한국어로.
