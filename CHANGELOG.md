# 변경 기록

## 0.6.0 — 2026-10-17 · 웹 ERD 뷰어 (`view`)
- `datalight.py view [data/model.light.json]` — 정본을 브라우저 ERD 로 (보기 전용). 표를 끌어 옮기면 위치만 `model.light.json.layout.json` 에,
  테마 5가지·보기 단계(표만·키·칸·자료형)·선택한 표만/이웃까지·SVG/PNG, 정본을 고치면 1초 안에 다시 그림. 이 컴퓨터(127.0.0.1)에서만 열림
- 뷰어는 전문판 data-expert-framework 의 `runtime/viewer/dataviewer` 를 커밋 그대로 담은 사본 (`skills/data-light/viewer`, 저작권자 결정으로 MIT 공개,
  `viewer.lock.json` 에 커밋·지문). 표준 라이브러리만 — 새 필수 패키지 없음. 관리자는 `tools/update_viewer.py` 로만 바꾼다 (`--check` 를 시험이 본다)
- 사용자에게 보여 줄 그림: 표가 많으면 erd.md 대신 `view`
- 뷰어 사본은 `.gitattributes` 에서 줄바꿈을 바꾸지 않게(-text) -- Windows 에서도 지문이 맞게. `view` 는 설치 폴더에 `__pycache__` 를 남기지 않는다

## 0.5.0 — 2026-10-17 · 전문판 0.6.0 (FW-01) 부분집합 — 만드는 것(product)
- 정본 `product`: `kinds`(design 설계까지 · load 파일 넣기 · manage 데이터 관리 · analyze 분석, 여러 개) · `main`(여럿이면 주 목적) ·
  `said`(**사용자 말 그대로** -- 짐작한 것은 적지 않는다, 전문판 FW-06 의 부분집합). 전문판 `data.product_type`·`data.product_primary` 의 부분집합
- `check`: 없으면 참고("유형 미정"), 모양이 틀리면 고칠 것 · `verify`: 없으면 **유형 미정으로 실패**, analyze 인데 성공 기준이 없으면 실패,
  manage 는 화면을 보지 않는다는 참고
- 정의서(spec.md) 맨 위에 "만드는 것"과 사용자 말 · `upgrade --facts data/facts.json` 이 전문판 질문 대장으로 옮김(사용자 답, 원문 = said),
  전문판 `facts.py product` 가 같은 판정을 내는지 시험(DEF_SCRIPTS)
- SKILL.md 질문 0번 "무엇을 만들어 드릴까요?", dev-process-light 카드의 `데이터:` 줄 → `product`
- 고침: 가져오기 기록의 백업·원본 경로가 macOS(/var → /private/var)·Windows(짧은 이름 RUNNER~1)에서 폴더를 잃고 파일 이름만 남던 문제
  (경로 양쪽을 실제 경로로 맞춘 뒤 비교) -- 0.4.0 부터 CI 의 macOS·Windows 가 실패하던 원인. CI 는 실패한 시험을 주석(annotation)으로 남긴다
- 독립 검토 반영: `main_said`(여럿일 때 주 목적에 대한 사용자 말) -- 있을 때만 전문판 주 목적으로 옮기고 없으면 전문판에서 묻는다,
  `product` 값 모양 검사(글자·목록), 프로젝트 안 링크 폴더는 이름 그대로(실제 경로 비교는 밖으로 나올 때만), `upgrade --facts` 는 대장이 있으면 아무것도 만들지 않는다
- **호환**: 0.4.x 정본은 `product` 를 더해야 `verify` 가 통과한다 -- dev-process-light 의 짝 고정(`data-light.lock.json`)을 올릴 때 함께 안내

## 0.4.1 — 2026-10-15 · dev-process-light 0.10 3차 요청 (V1~V6)
- **V1 급함: macOS 에서 커밋 훅이 모든 커밋을 막던 문제** — 0.4.0 훅의 `$( … case … )` 를 macOS `/bin/sh`(bash 3.2)가 못 읽음.
  case 패턴 앞에 `(` (POSIX), `hook install` 이 설치 뒤 `sh -n` 으로 확인해 못 읽으면 우리 블록을 빼고 알림(커밋을 막는 훅을 남기지 않음), CI 에 macOS 추가
  Windows 에서 `bash` 가 WSL 이어도 `sh -n` 확인이 잘못 실패하지 않게(파일 이름 + cwd, 진짜 문법 오류만 실패로)
- V2 `split` 이 짝 표의 `access` 를 `pi_` 로 옮김 (read 는 옮기지 않고, owner 가 있으면 own)
- V3 `access` 두 개 목록 — 넓은 쪽 읽기 + 좁은 쪽 쓰기 (`["read", "own"]` 게시판, `["read", "members"]` 공지): SELECT 와 INSERT·UPDATE·DELETE 규칙을 따로 만듦
- V4 샘플도 필수 칸도 없는 표의 `try`/`verify` 오류 → `INSERT … DEFAULT VALUES`
- V5 짝 표에 access 가 있는데 `pi_` 에 없으면 `check` 가 참고로 알림
- V6 `signup: closed` 안내에 익명 로그인 끄기 · Authentication → Users → Add user · 가입 화면 두지 않기

## 0.4.0 — 2026-10-15 · dev-process-light 0.9 2차 요청 반영 (U1~U8)
보안
- 정본에 `signup`(open/closed)·표의 `access`(members/own/read)·자료형 `owner` — build 가 **실제 RLS 규칙**을 만든다.
  `access: members` 는 `signup: closed` 일 때만(가입이 켜져 있으면 아무나 가입해 읽음 → `check` 가 막음), `pi_` 는 `read` 금지, `pi_` 의 `own` 은 짝 테이블의 owner 를 따름
- 규칙 틀 주석: 정해진 사람끼리에 "새 가입을 끈 경우에만", `pi_` 에도 그 틀, "생성물을 고치지 말고 SQL 편집기에서 · data/supabase-policies.sql 에 기록"
- `import apply` 는 SQLite 전용 — 정본이 PostgreSQL 이면 멈춤(`--force-sqlite`), `import schema` 가 개인정보로 보이는 칸을 `확인:` 으로 (`pi_` 표 칸은 개인정보로 표시)

흐름
- 정본 `outside` — 일부러 정본 밖에 둔 표는 데이터 보호 검사에서 뺌
- 훅·CI: 한글 경로(`core.quotepath=false`), `out/` 만 바뀐 저장도 검사, `.claude/skills/`·`.agents/skills/` 의 설치된 예제는 제외
- 훅 블록을 괄호로 감싸고 끝 표시(`# data-light end`)를 둠 — 공유 훅에서 우리 블록 뒤의 내용이 계속 돌고, 다시 설치해도 남음
- git worktree 지원(`git rev-parse --git-path hooks`), 훅 위치 표시 "`.githooks/pre-commit` (git 설정 core.hooksPath)"
- `import apply` 가 "이미 N행"·원본 없음·PostgreSQL 정본이면 백업·정본 변경 전에 멈춤, 기록의 백업 경로는 프로젝트 기준
- `with-dev-process-light.md`: 다시 설치 뒤 build·verify 는 늘, 파일 지도에 `.data-light/`·CI 파일, signup·access·outside 안내

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
