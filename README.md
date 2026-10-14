# data-expert-framework-light

**개발을 몰라도 쓸 수 있는 데이터 설계 도우미** — Claude 와 몇 마디 나누면 "무엇을 어떻게 저장할지"가 정리되고,
바로 쓸 수 있는 데이터베이스 설계도·SQL·정의서가 만들어집니다.

> "우리 반찬가게 주문을 기록하고 싶어" → 손님·반찬·주문·주문항목 4개 표, 그림(ERD), SQL, 엑셀 정의서, 그리고 "규칙이 진짜 동작하는지" 시험까지.

- 작은 홈페이지·동아리·가게·개인 기록처럼 **가벼운 시스템**용
- 질문은 쉽게 3~5개. 어떤 DB·자료형을 쓸지는 Claude 가 정하고 **왜 그런지 한 줄로** 알려 줍니다
- 이름·전화번호 같은 **개인정보는 자동으로 따로** 보관합니다
- 갖고 있는 **엑셀·CSV** 에서 시작할 수 있습니다 (넣기 전에 꼭 물어봅니다)
- [dev-process-light](https://github.com/sungbeom78/dev-process-light) 와 함께 쓰면 홈페이지 만들기 → 데이터 저장까지 한 흐름

## 설치

**Claude Code / Cowork 플러그인**
```
/plugin marketplace add sungbeom78/data-expert-framework-light
/plugin install data-expert-light
```
**스킬만** — [Releases](https://github.com/sungbeom78/data-expert-framework-light/releases) 의 `data-light-skill-<버전>.zip` 을 Claude 설정의 스킬에 올립니다.

필요한 것: Python 3.9 이상 (추가 설치 없음. 엑셀을 쓰려면 `pip install openpyxl`)

## 이렇게 씁니다
Claude 에게 그냥 말하세요.
```
동아리 회원이랑 회비 낸 기록을 저장하고 싶어
```
1. Claude 가 몇 가지를 물어봅니다 — 무엇을 기록하나요? 누가 쓰나요? 사람 정보가 들어가나요?
2. 설계도(그림)와 표를 보여 주며 "이렇게 맞나요?" 하고 확인합니다
3. 맞으면 SQL·정의서를 만들고, 실제로 넣어 보며 규칙을 시험합니다
4. 원하면 갖고 있는 엑셀을 넣어 줍니다

만들어지는 파일 (프로젝트의 `data/` 폴더):

| 파일 | 내용 |
|---|---|
| `model.light.json` | 설계 원본 — 이것만 고치면 나머지는 다시 만들어집니다 |
| `out/erd.md` | 표 사이 관계 그림 (GitHub·VS Code 에서 바로 보임) |
| `out/schema.sql` | DB 를 만드는 SQL (SQLite 또는 PostgreSQL·Supabase) |
| `out/spec.md`, `out/spec.xlsx` | 테이블 정의서 |
| `app.db` | SQLite 를 쓸 때의 데이터 파일 |

## 직접 돌려 보기 (선택)
```bash
cd skills/data-light
python scripts/datalight.py check examples/shop/data/model.light.json
python scripts/datalight.py try   examples/shop/data/model.light.json
python scripts/datalight.py build examples/shop/data/model.light.json --out /tmp/shop
```
명령 전체: `python scripts/datalight.py -h` · 형식: [format.md](skills/data-light/references/format.md)

## 더 큰 시스템이 되면 — 전문판
데이터가 많아지거나 암호화·권한 등급·공통 용어 사전·데이터 레이크가 필요해지면
`datalight.py upgrade` 로 전문판(data-expert-framework) 형식으로 옮길 수 있습니다. 설계를 처음부터 다시 하지 않아도 됩니다.

| | light (이 저장소) | 전문판 |
|---|---|---|
| 대상 | 비전공자, 작은 시스템 | 전문 팀, 업무 시스템 |
| 설계 | 쉬운 형식 + 한글 이름표 | 단어·용어·도메인 사전, 공통 용어 규칙 |
| 개인정보 | `pi_` 테이블로 분리 | 별도 스키마 + 앱 암호화 + 등급별 권한 |
| 검증 | SQLite 즉석 시험 | 실제 PostgreSQL 검증, pgModeler |
| 데이터 | CSV·엑셀 가져오기 | 공공데이터·레이크·조회 API·카탈로그 |

## 라이선스
MIT — [LICENSE](LICENSE)
