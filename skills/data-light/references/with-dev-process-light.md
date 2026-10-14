# dev-process-light 와 함께 쓰기

[dev-process-light](https://github.com/sungbeom78/dev-process-light) 0.8 이상은 이 스킬(data-light)을 `kit/skills/data-light` 에 **짝 버전으로 함께 담아** 설치한다
(`data-light.lock.json` 이 커밋·버전을 고정). 프로젝트 안에서는 이 스킬 파일을 고치지 않는다 — 고칠 것은 이 저장소에 요청한다.

## 언제 넘어오나
dev-process-light 규칙 12 **데이터부터**: 표가 이어지거나, 여럿이 로그인하거나, 엑셀·CSV 가 있거나, 개인정보가 있으면
화면보다 먼저 data-light 정본을 만들고 사용자에게 확인받는다. 카드의 `데이터:` 줄(없음 · 브라우저에만 · 새 표 · 표 바꿈 · 읽기만)이 신호다.

## 질문은 한 번만
`dev-notes/NOW.md` 의 "이 프로젝트는" 다섯 줄을 먼저 읽는다 — **누가 쓰나 · 로그인 · 올리는 곳 · 저장하는 데이터 · 개인정보**.
이미 답이 있는 것은 묻지 않는다. 새로 물은 답은 그 줄과 `dev-notes/DECISIONS.md` **양쪽에** 적는다.
카드·할 일에 적힌 완료 기준과 "만들지 않을 것"은 정본의 `goals`·`not_doing` 으로 옮겨 적는다 (같은 말을 다시 묻지 않는다).

## 실제 저장 위치
| "이 프로젝트는" 의 답 | 데이터를 두는 곳 | 정본 `db` |
|---|---|---|
| 혼자 보는 정적 사이트 (서버 없음) | 브라우저 저장소 — 내보내기 백업을 함께 만든다 | `sqlite` (설계·검사용) |
| 내 컴퓨터에서만 쓰는 도구 | SQLite (`data/app.db`) + 작은 서버 | `sqlite` |
| 여러 사람이 로그인해서 쓰는 웹 | Supabase(PostgreSQL) — 모든 표 RLS, 공개용 키만 | `postgresql` |

## 파일 위치와 기록
```
<프로젝트>/
├─ data/
│  ├─ model.light.json   정본 (이것만 고친다)
│  ├─ out/               build 결과 (schema.sql · erd.md · spec.md)
│  ├─ app.db             SQLite 를 쓸 때 (올리지 않음)
│  ├─ backup/            가져오기 전 자동 백업 (올리지 않음)
│  ├─ import_plan.json   가져오기 계획 (실제 값 일부 -- 올리지 않음)
│  └─ import_log.jsonl   가져오기 기록 (경로는 프로젝트 기준)
└─ dev-notes/
   ├─ NOW.md             "이 프로젝트는" 다섯 줄
   ├─ FEATURES.md        "데이터 (표)" 절 -- 표 → 그 표를 쓰는 기능
   └─ log/데이터/        데이터 작업 기록 (저장 종류 `데이터:`)
```
- 코드(화면·API)는 정본의 테이블·칸 이름을 그대로 쓴다. `NAMES.md` 는 정본의 한글 이름표를 따른다.
- 검사 장치는 **한 번 묻고** `datalight.py hook install` — 정본이 바뀐 저장(커밋)은 `verify` 를 통과해야 한다. 건너뛰지 않는다.
- `hook install` 이 `.gitignore` 에 넣는 줄: `data/app.db` · `data/backup/` · `data/*.csv` · `data/*.xlsx` · `data/out/spec.xlsx` · `data/import_plan*.json` · `import_plan*.json` · `.env`
- 다시 설치한 뒤에는 `hook status` 로 버전을 보고, 다를 때만 `hook install` → `build` → `verify`.

## 돌아가기
설계·확인·만들기가 끝나면 dev-process-light 흐름(화면 만들기 등)으로 돌아간다. 이후 저장할 것이 바뀌면 정본을 고치고 `build → verify` 를 다시 돌린다 (훅을 설치했으면 저장할 때 자동).
`verify` 의 "정본에서 빠졌습니다(데이터 N행)"는 되돌릴 수 없는 변경이다 — AI 가 혼자 고치지 않고 사용자에게 묻는다.
