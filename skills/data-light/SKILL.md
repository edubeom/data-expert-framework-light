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
| `upgrade <model>` | 전문판(data-expert-framework) model.json 으로 졸업 |

형식은 [references/format.md](references/format.md), dev-process-light 와 함께 쓸 때는 [references/with-dev-process-light.md](references/with-dev-process-light.md).

## 흐름: 이해 → 설계 → 확인 → 만들기 → 넣기

### 1. 이해 — 질문 3~5개만
한 번에 하나씩, 고를 수 있게 묻는다(AskUserQuestion 이 있으면 사용). 이미 답이 있는 것(dev-process-light 에서 정한 것 포함)은 묻지 않는다.

1. **무엇을 기록하나요?** — 예시를 보여 주고 고르거나 말하게 한다 (회원 · 주문 · 예약 · 상품 · 일정 · 글 …)
2. **누가 쓰나요?** — 나 혼자 / 몇 명이 같이 / 아무나 가입해서
3. **사람 정보가 들어가나요?** — 이름·전화·이메일·주소 … (있으면 따로 보관한다고 알려 준다)
4. (필요할 때만) **이미 쓰는 엑셀·CSV 가 있나요?** — 있으면 그 파일에서 시작 (5단계 `import`)
5. (필요할 때만) 헷갈리는 관계 하나 — "주문 하나에 반찬이 여러 개 들어가나요?" 처럼 예/아니오로

DB 선택은 묻지 않고 정해서 알린다:
- 혼자 쓰거나 정적 사이트 → **SQLite** ("설치가 필요 없고 파일 하나라서")
- 여러 사람이 로그인해서 쓰는 웹 → **Supabase(PostgreSQL)** ("로그인·권한·백업을 같이 주니까") → `"db": "postgresql"`

### 2. 설계 — 정본 쓰기
`data/model.light.json` 을 쓴다. Claude 가 정하는 것:
- 영어 이름(소문자·밑줄): 테이블은 단수 명사 (`customer`, `order_item`), 키는 `<테이블>_id`. 예약어(`order`, `user`, `group`…)는 피한다 (`orders`, `member`).
- 자료형: id · ref · text · long_text · int · number · money · bool · date · datetime 중에서.
- 모든 칸에 **한글 이름표(label)** — 사용자는 이것만 보면 된다.
- 개인정보 칸에는 `"personal": "name"` 처럼 종류를 표시하고 `split --write` 로 분리한다.
- 확인용 샘플 몇 행(`sample`).

### 3. 확인 — 사용자에게 보여 주기
`check` → `build` → `try` 를 돌리고, **사용자에게는 ERD 그림(erd.md 의 Mermaid)과 표 하나**로 보여 준다:
"손님 한 명이 주문을 여러 번 할 수 있고, 주문 하나에 반찬이 여러 개 담깁니다. 맞나요?"
기술 용어(PK·FK·정규화)는 쓰지 않거나, 쓰면 바로 풀어 쓴다 (예: "다른 표를 가리키는 칸").
`check` 의 "고칠것" 은 Claude 가 고치고 다시 돌린다. 사용자에게 고치라고 하지 않는다.

### 4. 만들기
- SQLite: `data/out/schema.sql` 로 `data/app.db` 를 만든다 (`sqlite3 data/app.db < data/out/schema.sql` 또는 파이썬). **이미 있는 DB 를 바꾸거나 지우기 전에는 반드시 확인**받는다.
- Supabase: `build --db postgresql` 결과를 SQL 편집기(또는 Supabase 도구)에 넣는다. 실제 프로젝트에 적용하기 전에 확인받는다. 개인정보 테이블(`pi_`)에는 RLS(행 접근 규칙)를 켜라고 안내한다.

### 5. 넣기 (가져오기)
1. `import plan 파일 --table 이름 --label 한글이름` → 칸마다 영어 이름이 비어 있다. Claude 가 채운다.
2. 계획을 표로 보여 주고(어느 칸이 개인정보로 따로 가는지 포함) "이대로 넣을까요?" 확인.
3. 사용자가 답하면 plan 의 `approved` 를 true 로 하고 `import apply … --approval "<사용자 답 그대로>"`. 기록은 `data/import_log.jsonl`.
같은 테이블에 행이 이미 있으면 멈춘다 — 더하는 게 맞는지 묻고 `--append`.

### 6. 졸업 (필요할 때만)
데이터가 커지거나, 암호화·권한 등급·공통 용어 사전이 필요해지면 `upgrade` 로 전문판 model.json 을 만든다. 설계를 다시 하지 않아도 된다.

## 지킬 것
- 사용자에게 묻기 전에 DB 를 만들거나 바꾸거나 지우지 않는다. 파일 적재도 확인 후.
- 개인정보는 본 테이블에 두지 않는다 (`check` 가 막는다). 비밀번호는 저장하지 말고 로그인 서비스(Supabase Auth 등)에 맡긴다.
- `data/app.db`, 가져온 원본 파일, `.env` 는 공개 저장소에 올리지 않게 `.gitignore` 에 넣는다.
- 정본만 고친다. `data/out/` 은 다시 만들면 된다.
