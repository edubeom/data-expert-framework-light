# 쉬운 정본 형식 — `data-light/1`

파일: `data/model.light.json` (UTF-8 JSON)

```json
{
  "format": "data-light/1",
  "project": "반찬가게 주문",
  "db": "sqlite",
  "tables": [ { 테이블 }, ... ]
}
```

| 키 | 뜻 |
|---|---|
| `db` | `sqlite`(기본) 또는 `postgresql` (Supabase 포함) |

## 테이블
| 키 | 필수 | 뜻 |
|---|---|---|
| `name` | ✔ | 영어 소문자·숫자·밑줄, 글자로 시작, 예약어 금지. 단수 명사 (`customer`) |
| `label` | 권장 | 한글 이름표 (`손님`) |
| `about` | | 한 줄 설명 |
| `columns` | ✔ | 칸 목록 |
| `sample` | | 확인용 샘플 행 `[{칸: 값}]` — `try` 가 넣어 본다 |
| `timestamps` | | 기본 true → `created_at`·`updated_at` 자동 추가. 끄려면 false |

## 칸
| 키 | 뜻 |
|---|---|
| `name` | 영어 이름 (테이블과 같은 규칙) |
| `label` | 한글 이름표 |
| `type` | 아래 자료형 중 하나 |
| `required` | true 면 비울 수 없음 |
| `unique` | true 면 같은 값 두 번 금지 |
| `choices` | 고를 수 있는 값 목록 (text·int 만) |
| `default` | 기본값 |
| `ref` | (type ref) 가리키는 테이블 |
| `on_delete` | (type ref) 가리키는 행을 지울 때: `keep`(못 지우게, 기본) · `delete`(같이 지움) · `clear`(비움) |
| `key` | (type ref) 이 칸이 키 — 1:1 짝 테이블(`pi_`), 연결 테이블(여러 칸 key) |
| `personal` | 개인정보 종류: `name` `phone` `email` `address` `birth` `id_number` `account` `health` `photo` `location` `other` (또는 true) |
| `about` | 설명 |

## 자료형
| type | 뜻 | SQLite | PostgreSQL |
|---|---|---|---|
| `id` | 자동 번호 (테이블마다 하나, 이름은 `<테이블>_id`) | INTEGER PRIMARY KEY AUTOINCREMENT | bigint identity |
| `ref` | 다른 테이블을 가리킴 (이름 끝 `_id`) | INTEGER + REFERENCES | bigint + REFERENCES |
| `text` | 짧은 글 | TEXT | text |
| `long_text` | 긴 글 | TEXT | text |
| `int` | 정수 | INTEGER | integer |
| `number` | 소수 포함 숫자 | REAL | numeric |
| `money` | 금액 (음수 금지) | NUMERIC | numeric(15,2) |
| `bool` | 예/아니오 | INTEGER 0/1 | boolean |
| `date` | 날짜 `2026-10-14` | TEXT | date |
| `datetime` | 날짜+시각 | TEXT | timestamptz |

## 규칙 (`check`)
- 테이블마다 행을 구별할 키: `id` 칸 하나, 또는 key 표시한 ref 칸(들).
- ref 는 있는 테이블을, 칸 하나로 된 키를 가진 테이블을 가리킨다.
- `required` 인 ref 끼리 돌고 도는 순환 금지.
- 개인정보(`personal`) 칸은 `pi_` 테이블에만 → `split --write` 가 `pi_<테이블>`(본 테이블과 1:1, 같이 지워짐)로 옮긴다.
- 이름은 영어 소문자·숫자·밑줄, SQL 예약어 금지.

## 전문판과의 관계
이 형식은 data-expert-framework `model.json` 의 부분집합이다. `upgrade` 가 변환한다:
type → domains, label → terms(한글명), 이름 토큰 → words(한글명은 전문판 공통 사전 대조 때 정리),
ref → fk(on_delete RESTRICT/CASCADE/SET NULL) + relationships, personal → `pi`/`pi_type`, `pi_` 테이블 → `is_pi`.
