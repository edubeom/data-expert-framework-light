# 변경 기록

## 0.3.0 — 2026-10-14 · dev-process-light 0.8 짝 맞춤 요청 반영
보안·실제 데이터
- `import plan` 기본 저장 위치 `data/import_plan.json`, 원본 경로는 프로젝트 기준(밖이면 파일 이름만 → apply `--file`), 개인정보 칸의 샘플 값은 가림, "올리지 않는다" 안내. 가져오기 기록도 프로젝트 기준 경로
- `hook install` 의 `.gitignore`: `data/*.csv` · `data/*.xlsx` · `data/out/spec.xlsx` · `data/import_plan*.json` · `import_plan*.json` 추가
- `build --db postgresql`: **모든 표**에 RLS + 누가 쓰나별 규칙 틀(정해진 사람끼리 · 가입형 자기 행 · 누구나 읽기, `pi_` 는 본인·관리자). SKILL 에 공개용 키만 · service_role/sb_secret_ 금지 · Security Advisor
- 훅 안내문에서 `--no-verify` 권유 삭제 ("FAIL 을 고친 뒤 다시 저장")

흐름·형식
- 표의 `"unique": [[칸, 칸]]` — 묶음 중복 금지 (DDL · `try` · `--mutate` · `upgrade` → 전문판 `uniques`)
- `import schema <app.db>` — 이미 있는 SQLite 에서 정본 초안 (CHECK 규칙·이름으로 bool·선택값·금액·날짜 복원, 규칙에 안 맞는 이름·키 없는 표 목록)
- `--version`, 훅에 버전 한 줄, `hook status`
- `hook install --no-ci`(기억함) · `--append`(다른 pre-commit 끝에) · `core.hooksPath` 존중 · 다시 설치하면 우리 부분만 교체
- `with-dev-process-light.md` 를 dev-process-light 0.8 과 맞춤 (NOW.md 다섯 줄, 실제 저장 위치 표, 기록 위치, 검사 장치 한 번 묻기), SKILL 의 저장 위치 규칙도 같게
- 작은 것: `split` 설명 "회원의 개인정보", README 에 "dev-process-light 로 설치했으면 플러그인은 따로 깔지 않아도 됨"

## 0.2.1 — 2026-10-14 · Windows · Python 3.9 수정
0.2.0 은 Windows 와 Python 3.9 에서 일부 기능이 실패합니다. 0.2.1 을 쓰세요.
- Windows 수정: SQLite 연결·CSV 파일을 항상 닫음 (임시 폴더 삭제 실패 WinError 32)
- Windows 수정: 출력을 항상 UTF-8 로 (cp1252 파이프에서 한글이 ???? 로 깨짐), 커밋 훅이 Windows 의 가짜 python3 를 건너뜀
- Python 3.9 수정: `Path.write_text(newline=)`(3.10+) 대신 공용 쓰기 함수
- CI: fail-fast 끔, actions/checkout@v5 · setup-python@v6
- CI 와 시험에서 닫지 않은 DB·파일(ResourceWarning)을 실패로 처리

## 0.2.0 — 2026-10-14 · 검증 하네스
- 정본에 성공 기준 `goals`(say · sql · expect)와 범위 밖 `not_doing` — `try` 가 샘플로 성공 기준 쿼리를 실제로 돌림, `check` 가 범위 밖 테이블·데이터를 바꾸는 쿼리를 막음
- `verify` — 통과/실패 관문 하나 (설계 검사 + 성공 기준 + 규칙 + `out/` 최신 + DB 데이터 보호), `--mutate` 장치 검증
- `hook install` — pre-commit 훅 + GitHub Actions 파일 + `.gitignore`
- `import apply` 가 쓰기 전에 `data/backup/` 에 DB 백업
- 필수 참조 칸 비우기도 규칙 시험에 추가, 정의서 맨 위에 성공 기준
- 저장소 CI (Ubuntu·Windows × Python 3.9·3.12)

## 0.1.0 — 2026-10-14
- 첫 공개. 쉬운 정본 형식 `data-light/1`
- `datalight.py`: check · split · build(SQLite/PostgreSQL DDL, Mermaid ERD, 정의서 md/xlsx) · try(SQLite 즉석 검증) · import(plan/apply, 승인 기록) · upgrade(전문판 model.json)
- 스킬 `data-light` (질문 3~5개 흐름), dev-process-light 연결 문서, 반찬가게 예제
- 시험: 단위 시험 + (전문판 스크립트가 있으면) upgrade 결과 호환 시험
