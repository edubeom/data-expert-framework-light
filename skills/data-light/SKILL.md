---
name: data-light
description: 비전공자·작은 시스템을 위한 쉬운 데이터 설계. "회원·주문·예약을 저장하고 싶어", "엑셀/CSV 를 DB 로", "테이블 설계해 줘", "Supabase/SQLite 스키마" 같은 요청에 쓴다. 몇 가지 쉬운 질문으로 테이블을 설계하고 검사·SQL·ERD·정의서·SQLite 검증·가져오기까지 한다. dev-process-light 에서 저장할 데이터가 생기면 이어서 쓴다.
---

# data-light — 쉬운 데이터 설계

사용자는 개발을 모를 수 있다. **질문은 쉽게·적게, 기술 결정은 Claude 가 하고 이유를 한 줄로 공유**한다.
정본은 `data/model.light.json` 하나. 다른 모든 파일은 여기서 만들어진다.

도구: `python scripts/datalight.py <명령>` (파이썬 표준 라이브러리만. 엑셀은 openpyxl 이 있으면)

| 명령 | 하는 일 |
|---|---|
| `check <model>` | 설계 검사 (키·참조·필수·선택값·이름·개인정보 위치) |
| `split <model> --write` | 개인정보 칸을 `pi_<테이블>` 로 옮김 |
| `build <model> [--db postgresql]` | `data/out/` 에 schema.sql · erd.md · spec.md (+spec.xlsx) |
| `try <model>` | SQLite 에서 실제로 만들고 샘플을 넣고, 규칙이 나쁜 값을 막는지 확인 |
| `import plan <csv/xlsx> --table 이름` → `import apply …` | 파일을 테이블로 (사용자 확인 후) |
| `import schema data/app.db` | 이미 있는 SQLite DB 에서 정본 초안 (이름표는 비어 있음) |
| `verify <model> [--mutate]` | **통과/실패 관문** — 설계 검사 + 성공 기준 + 규칙 + `out/` 최신 + DB 데이터 보호 (exit 0/1) |
| `hook install [--no-ci] [--append]` · `hook status` | 커밋할 때마다 `verify` 자동 실행 + GitHub CI 파일 + `.gitignore` · 설치된 버전 확인 |
| `upgrade <model>` | 전문판(data-expert-framework) model.json 으로 졸업 |

**원칙 — "확인해 줘" 대신 확인할 수단을 남긴다.** 무엇이 되면 완성인지(성공 기준)를 먼저 정해 정본에 쿼리로 적고,
`verify` 가 통과해야 끝이다. 지시를 기억하는 대신 도구가 막는다.

형식은 [references/format.md](references/format.md), dev-process-light 와 함께 쓸 때는 [references/with-dev-process-light.md](references/with-dev-process-light.md).

## 흐름: 이해 → 설계 → 확인 → 만들기 → 넣기

### 1. 이해 — 질문 3~5개만
한 번에 하나씩, 고를 수 있게 묻는다(AskUserQuestion 이 있으면 사용). 이미 답이 있는 것(dev-process-light 에서 정한 것 포함)은 묻지 않는다.

1. **무엇을 기록하나요?** — 예시를 보여 주고 고르거나 말하게 한다 (회원 · 주문 · 예약 · 상품 · 일정 · 글 …)
   이어서 **"이 기록으로 무엇을 알 수 있어야 하나요?"** — 예: "손님별 이번 달 주문 금액", "남은 자리 수". 1~3개.
   이것이 성공 기준이다. **"이번에 안 만들 것"** 도 하나 물어 둔다 (예: 결제, 배송 추적).
2. **누가 쓰나요?** — 나 혼자 / 몇 명이 같이 / 아무나 가입해서
3. **사람 정보가 들어가나요?** — 이름·전화·이메일·주소 … (있으면 따로 보관한다고 알려 준다)
4. (필요할 때만) **이미 쓰는 엑셀·CSV 가 있나요?** — 있으면 그 파일에서 시작 (5단계 `import`)
5. (필요할 때만) 헷갈리는 관계 하나 — "주문 하나에 반찬이 여러 개 들어가나요?" 처럼 예/아니오로

저장 위치는 묻지 않고 2번 답으로 정해서 알린다 (설계·검사는 어느 경우든 이 정본과 `verify` 로):
- 혼자 보는 정적 사이트(서버 없음) → **브라우저 저장소** ("서버가 없어도 되니까. 브라우저 기록을 지우면 사라지므로 내보내기 백업을 둔다") — 정본은 `"db": "sqlite"` 그대로 두고 검사용으로 쓴다
- 내 컴퓨터에서만 쓰는 도구 → **SQLite + 작은 서버** ("설치가 필요 없고 파일 하나라서")
- 여러 사람이 로그인해서 쓰는 웹 → **Supabase(PostgreSQL)** ("로그인·권한·백업을 같이 주니까") → `"db": "postgresql"`

### 2. 설계 — 정본 쓰기
`data/model.light.json` 을 쓴다. Claude 가 정하는 것:
- 영어 이름(소문자·밑줄): 테이블은 단수 명사 (`customer`, `order_item`), 키는 `<테이블>_id`. 예약어(`order`, `user`, `group`…)는 피한다 (`orders`, `member`).
- 자료형: id · ref · text · long_text · int · number · money · bool · date · datetime 중에서.
- 모든 칸에 **한글 이름표(label)** — 사용자는 이것만 보면 된다.
- 개인정보 칸에는 `"personal": "name"` 처럼 종류를 표시하고 `split --write` 로 분리한다.
- 확인용 샘플 몇 행(`sample`). 샘플 값은 **만든 값**으로 (실제 사람의 이름·전화번호 금지).
- 두 칸을 묶어야 중복이 되는 경우는 표에 `"unique": [["member_id", "dues_month"]]` (한 회원이 같은 달 회비를 두 번 내지 않음).
- **성공 기준(`goals`)** — 1번 답을 한 문장(`say`) + 확인 쿼리(`sql`) + 샘플로 나와야 할 결과(`expect`)로. **설계보다 먼저** 쓴다.
- **만들지 않을 것(`not_doing`)** — 범위 밖. 그 이름의 테이블이 생기면 `check` 가 막는다.

### 3. 확인 — 사용자에게 보여 주기
`build` → `verify` 를 돌리고(통과할 때까지 Claude 가 고치며 반복), **사용자에게는 ERD 그림(erd.md 의 Mermaid)·성공 기준 결과·표 하나**로 보여 준다:
"손님 한 명이 주문을 여러 번 할 수 있고, 주문 하나에 반찬이 여러 개 담깁니다. 맞나요?"
기술 용어(PK·FK·정규화)는 쓰지 않거나, 쓰면 바로 풀어 쓴다 (예: "다른 표를 가리키는 칸").
FAIL 은 Claude 가 고치고 다시 돌린다. 사용자에게 고치라고 하지 않는다.
처음 한 번은 `verify --mutate` 로 "일부러 규칙을 하나 빼도 잡는지"까지 보여 준다 (검사 장치가 진짜 동작하는지).

### 4. 만들기
- SQLite: `data/out/schema.sql` 로 `data/app.db` 를 만든다 (`sqlite3 data/app.db < data/out/schema.sql` 또는 파이썬). **이미 있는 DB 를 바꾸거나 지우기 전에는 반드시 확인**받는다.
- 이미 DB 가 있으면 먼저 `import schema data/app.db` 로 초안을 만들고, `확인:` 줄(규칙에 안 맞는 이름·키 없는 표)은 사용자와 정한다. 이름을 바꾸면 DB 도 바꿔야 하므로 혼자 고치지 않는다.
- Supabase: `build --db postgresql` 결과를 SQL 편집기(또는 Supabase 도구)에 넣는다. 실제 프로젝트에 적용하기 전에 확인받는다.
  이 SQL 은 **모든 표에 RLS(행 접근 규칙)를 켠다** — 규칙이 없으면 사이트의 공개용 키로는 아무것도 읽고 쓸 수 없다(안전한 기본값).
  2번 답(누가 쓰나)에 맞는 틀을 골라 표마다 규칙을 켠다: 정해진 사람끼리 = 로그인한 사람만, 가입형 = 자기 행(`auth.uid()`), `pi_` = 본인·관리자만(모두 읽기 금지).
  사이트 코드에는 **공개용 키(anon · publishable)만** 넣는다. `service_role` · `sb_secret_` 키는 절대 넣지 않는다. 적용 뒤 Supabase 의 Security Advisor 를 확인한다.

### 5. 넣기 (가져오기)
1. 프로젝트 맨 위 폴더에서 `import plan 파일 --table 이름 --label 한글이름` → `data/import_plan.json`. 칸마다 영어 이름이 비어 있다. Claude 가 채운다.
   계획에는 경로가 프로젝트 기준으로만 적히고 개인정보 칸의 값은 가려진다. 그래도 실제 값 일부가 들어 있으니 **올리지 않는다**(`hook install` 이 `.gitignore` 에 넣는다). 원본이 프로젝트 밖이면 apply 때 `--file` 로 알려 준다.
2. 계획을 표로 보여 주고(어느 칸이 개인정보로 따로 가는지 포함) "이대로 넣을까요?" 확인.
3. 사용자가 답하면 plan 의 `approved` 를 true 로 하고 `import apply … --approval "<사용자 답 그대로>"`. 기록은 `data/import_log.jsonl`.
같은 테이블에 행이 이미 있으면 멈춘다 — 더하는 게 맞는지 묻고 `--append`.

### 지키는 장치 (git 을 쓰면)
`hook install` 을 한 번 해 둔다(사용자에게 한 번 묻고) → 정본이 바뀐 커밋은 `verify` 를 통과해야 저장되고, GitHub 에 올리면 같은 검사가 다시 돈다.
멈추면 FAIL 줄을 고친 뒤 다시 저장한다. **검사를 건너뛰지 않는다**(`--no-verify` 금지).
CI 파일을 원치 않으면 `--no-ci`(기억해 둔다), 이미 다른 pre-commit 이 있으면 `--append`. `git config core.hooksPath` 가 있으면 그 폴더에 설치한다.
다시 설치할지는 `hook status` 로 판단한다 (버전이 같으면 그대로).
설계에서 잘못을 발견하면 고치기만 하지 말고 **그 잘못을 잡는 성공 기준이나 샘플 행을 하나 더해 박제**한다.

### 6. 졸업 (필요할 때만)
데이터가 커지거나, 암호화·권한 등급·공통 용어 사전이 필요해지면 `upgrade` 로 전문판 model.json 을 만든다. 설계를 다시 하지 않아도 된다.

## 지킬 것 — 되돌릴 수 있나?
- 되돌릴 수 있는 일(이름표·설명·샘플·`out/` 다시 만들기)은 Claude 가 알아서 한다.
- **되돌릴 수 없는 일은 사용자 확인 후에만**: DB 를 만들기·바꾸기·지우기, 파일 적재. 장치가 받쳐 준다 —
  `import apply` 는 확인 답 없이는 멈추고 쓰기 전에 `data/backup/` 에 복사본을 만든다,
  `verify` 는 데이터가 든 테이블·칸이 정본에서 빠지면 실패한다.
- 개인정보는 본 테이블에 두지 않는다 (`check` 가 막는다). 비밀번호는 저장하지 말고 로그인 서비스(Supabase Auth 등)에 맡긴다.
- **`verify` 가 통과하기 전에는 "다 됐다"고 말하지 않는다.** 정본만 고친다. `data/out/` 은 다시 만들면 된다.
