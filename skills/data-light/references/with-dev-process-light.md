# dev-process-light 와 함께 쓰기

[dev-process-light](https://github.com/sungbeom78/dev-process-light) 로 만드는 작은 홈페이지·앱에 **저장할 데이터가 생기면** 이 스킬로 넘어온다.

## 언제 넘어오나
- 회원·게시글·예약·주문·기록처럼 "쌓이는 것"이 생겼을 때
- 사용자가 엑셀·CSV 를 보여 주며 "이걸 사이트에 넣고 싶어" 할 때

## 묻지 않을 것
dev-process-light 에서 이미 정한 것은 다시 묻지 않는다:
누가 쓰나(혼자/여럿) · 로그인 여부 · 호스팅(정적/서버/Supabase 등). 그 답으로 DB 를 정한다.

| dev-process-light 에서 정한 것 | DB |
|---|---|
| 혼자 보는 사이트, 정적 호스팅(GitHub Pages 등) | 데이터가 작고 고정 → JSON 파일, 쌓이는 데이터 → SQLite (로컬 도구) |
| 여러 사람이 로그인해서 쓰는 웹 | Supabase(PostgreSQL) — `"db": "postgresql"` |
| 이미 Supabase 를 쓰는 중 | Supabase |

## 파일 위치 약속
```
<프로젝트>/
└─ data/
   ├─ model.light.json   정본 (이것만 고친다)
   ├─ out/               build 결과 (schema.sql · erd.md · spec.md)
   ├─ app.db             SQLite 를 쓸 때 (git 에 올리지 않음)
   └─ import_log.jsonl   가져오기 기록
```
- 코드(화면·API)는 정본의 테이블·칸 이름을 그대로 쓴다.
- dev-process-light 에서 정한 **완료 기준·만들지 않을 것**이 있으면 데이터 쪽 `goals`·`not_doing` 으로 옮겨 적는다 (같은 말을 다시 묻지 않는다).
- git 을 쓰는 프로젝트면 `datalight.py hook install` — 정본이 바뀐 커밋은 `verify` 를 통과해야 한다.
- dev-process-light 의 기획 문서에 "데이터" 절이 있으면 ERD(`data/out/erd.md`) 링크를 단다.
- `.gitignore` 에 `data/app.db`, `data/*.csv`, `data/*.xlsx`, `.env` 를 넣는다.

## 돌아가기
설계·확인·만들기가 끝나면 dev-process-light 흐름(화면 만들기 등)으로 돌아간다. 이후 저장할 것이 바뀌면 정본을 고치고 `build → verify` 를 다시 돌린다 (훅을 설치했으면 커밋할 때 자동).
