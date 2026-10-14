# 변경 기록

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
