# 💰 budget-app

파일 기반(JSONL)으로 동작하는 **콘솔 가계부** 프로그램입니다.
단순히 내역을 저장하는 수준을 넘어, 수정/삭제/검색/월별 요약/카테고리 관리/
예산 초과 경고/CSV import·export까지 지원하는 "작은 서비스"를 목표로 만들었습니다.

외부 라이브러리 없이 **Python 표준 라이브러리만** 사용합니다.

---

## 목차

- [주요 기능](#주요-기능)
- [요구 사항](#요구-사항)
- [설치 및 실행](#설치-및-실행)
- [빠른 시작](#빠른-시작)
- [명령어 목록](#명령어-목록)
- [데이터 저장 방식](#데이터-저장-방식)
- [CSV import/export 스키마](#csv-importexport-스키마)
- [프로젝트 구조](#프로젝트-구조)
- [설계 포인트](#설계-포인트)
- [종료 코드 & 에러 처리](#종료-코드--에러-처리)

---

## 주요 기능

| 기능 | 명령어 | 설명 |
|---|---|---|
| 거래 추가 | `add` | 대화형으로 날짜/타입/카테고리/금액/메모/태그 입력 |
| 거래 목록 | `list` | 최신순 조회, `--limit` 지원, 제너레이터 기반 스트리밍 처리 |
| 거래 검색 | `search` | 기간/카테고리/타입/키워드/태그 조건 검색 |
| 월별 요약 | `summary` | 총수입/총지출/잔액 + 카테고리별 지출 TOP N |
| 예산 관리 | `budget set` | 월 예산 설정 → summary에서 사용률(%) 및 초과 경고 |
| 카테고리 관리 | `category` | 추가/조회/삭제 (사용 중인 카테고리는 대체 지정 필요) |
| 거래 수정 | `update` | id 기반, 옵션으로 원하는 필드만 수정 |
| 거래 삭제 | `delete` | id 기반 삭제, 원자적 파일 교체로 안전하게 처리 |
| 가져오기/내보내기 | `import` / `export` | CSV로 일괄 등록 / 조건별 CSV 내보내기 |

---

## 요구 사항

- Python 3.9 이상
- 추가 설치 패키지 없음 (표준 라이브러리만 사용)

---

## 설치 및 실행

```bash
git clone https://github.com/<your-id>/budget-app.git
cd budget-app
python -m budget_app --help
```

---

## 빠른 시작

```bash
# 1. 카테고리 확인 (최초 실행 시 food/transport/rent/salary/etc 자동 생성)
python -m budget_app category list

# 2. 거래 추가 (대화형)
python -m budget_app add

# 3. 최근 내역 확인
python -m budget_app list --limit 10

# 4. 이번 달 요약
python -m budget_app summary --month 2026-09 --top 3

# 5. 예산 설정 후 다시 요약 (초과 여부 확인)
python -m budget_app budget set --month 2026-09 --amount 500000
python -m budget_app summary --month 2026-09
```

기본 데이터 저장 폴더는 `./data`이며, `--data-dir` 옵션으로 변경할 수 있습니다.

```bash
python -m budget_app --data-dir ./mydata list
```

`--verbose` 옵션을 주면 실행 로그와 처리 시간이 함께 출력됩니다.

모든 명령은 `-h` / `--help` 로 사용법을 확인할 수 있습니다.

```bash
python -m budget_app search --help
```

---

## 명령어 목록

### 거래

```bash
python -m budget_app add
python -m budget_app list --limit 20
python -m budget_app search --from 2026-09-01 --to 2026-09-30 --category food
python -m budget_app search --q 점심 --tag friend
python -m budget_app update --id T0002 --amount 20000 --memo "수정된 메모"
python -m budget_app delete --id T0003
```

> `update`는 **옵션 기반**으로 고정되어 있습니다(대화형 방식은 미지원).
> 지정한 옵션의 필드만 바뀌고, 나머지는 기존 값이 유지됩니다.

### 요약 / 예산

```bash
python -m budget_app summary --month 2026-09 --top 3
python -m budget_app budget set --month 2026-09 --amount 500000
```

### 카테고리

```bash
python -m budget_app category list
python -m budget_app category add hobby
python -m budget_app category remove food --replacement etc
```

> 사용 중인 카테고리를 삭제하려면 `--replacement`로 대체 카테고리를 지정해야 합니다.
> 지정하지 않으면 삭제가 거부됩니다.

### 가져오기 / 내보내기

```bash
python -m budget_app import --from ./sample.csv
python -m budget_app export --out ./sep.csv --month 2026-09
python -m budget_app export --out ./range.csv --from 2026-09-01 --to 2026-09-15
```

> `export`는 `--month` 또는 `--from`/`--to` 중 최소 하나의 조건이 반드시 필요합니다.

---

## 데이터 저장 방식

- 포맷: **JSONL** (한 줄 = JSON 객체 하나)
- 기본 폴더: `./data` (없으면 최초 실행 시 자동 생성)
- 3개 파일로 분리 저장:

| 파일 | 내용 |
|---|---|
| `data/transactions.jsonl` | 거래 내역 |
| `data/categories.jsonl` | 카테고리 목록 (최초 실행 시 기본값 자동 생성) |
| `data/budgets.jsonl` | 월별 예산 |

`transactions.jsonl` 한 줄 예시:

```json
{"id": "T0001", "type": "income", "date": "2026-09-01", "amount": 3000000, "category": "salary", "memo": "9월 월급", "tags": []}
```

수정/삭제 시에는 임시 파일에 전체 내용을 먼저 쓰고 `os.replace()`로
**원자적으로 교체**하여, 중간에 프로세스가 죽어도 원본 파일이 깨지지 않도록 했습니다.

---

## CSV import/export 스키마

인코딩 UTF-8, 첫 줄은 헤더 필수.

| column | required | 설명 |
|---|---|---|
| `date` | Y | `YYYY-MM-DD` |
| `type` | Y | `income` / `expense` |
| `category` | Y | 등록된 카테고리 (없으면 오류) |
| `amount` | Y | 양수 정수 |
| `memo` | N | 문자열 |
| `tags` | N | 쉼표(`,`)로 구분된 문자열 |

예시:

```csv
date,type,category,amount,memo,tags
2026-09-20,expense,transport,3000,택시,
2026-09-21,income,salary,500000,보너스,bonus
```

---

## 프로젝트 구조

```
budget_app/
├── __init__.py
├── __main__.py     # python -m budget_app 진입점
├── models.py       # Transaction / Category / Budget dataclass
├── exceptions.py   # 사용자 정의 예외 (원인 + 해결 힌트)
├── decorators.py   # log_execution / measure_time / handle_errors
├── storage.py      # 파일 I/O 담당 (Repository, 제너레이터 스트리밍, 원자적 교체)
├── services.py     # 검증 규칙 + 비즈니스 로직 (BudgetService)
└── cli.py          # argparse 기반 CLI, 대화형 입력, 출력 포맷팅
```

레이어별 책임:

| 계층 | 파일 | 책임 |
|---|---|---|
| 모델 | `models.py` | 데이터의 "모양"만 정의 |
| 저장소 | `storage.py` | 파일을 어떻게 읽고 쓸지만 담당 |
| 서비스 | `services.py` | 검증/계산/조합 등 실제 비즈니스 규칙 |
| CLI | `cli.py` | 입력 파싱 → 서비스 호출 → 결과 출력 |

---

## 설계 포인트

### 제너레이터 기반 스트리밍

```python
def iter_all(self) -> Iterator[Transaction]:
    with self.path.open("r", encoding="utf-8") as f:
        for line in f:
            yield Transaction.from_dict(json.loads(line))
```

`list()`로 감싸서 강제로 다 읽지 않는 이상 파일 전체를 한 번에 메모리에 올리지 않습니다.
`search`/`list`/`summary`는 이 제너레이터를 한 줄씩 소비하면서 조건에 맞지 않는 데이터는
즉시 버리기 때문에, 파일이 커져도 메모리 사용량이 급격히 늘지 않습니다.

### 데코레이터로 공통 관심사 분리

```python
@log_execution
@measure_time
@handle_errors
def dispatch(args: argparse.Namespace) -> int:
    ...
```

로그 남기기 / 실행 시간 측정 / 예외 처리(스택트레이스 대신 "원인 + 해결 힌트" 출력)를
비즈니스 로직과 완전히 분리했습니다. `dispatch` 본문에는 `try/except`나 로그 코드가
전혀 없습니다.

### 타입 힌트로 계약 명시

```python
def add_transaction(
    self, date: str, type_: str, category: str, amount: int,
    memo: Optional[str] = None, tags: Optional[List[str]] = None,
) -> Transaction:
```

함수가 무엇을 받고 무엇을 돌려주는지 시그니처만 보고 알 수 있고,
에디터/타입 체커가 실수를 미리 잡아줍니다.

### 원자적 파일 교체

`update`/`delete`처럼 파일 전체를 다시 써야 하는 작업은 임시 파일에 먼저 쓰고
`os.replace()`로 한 번에 교체합니다. 쓰는 도중 실패해도 원본 파일은 그대로 유지됩니다.

---

## 종료 코드 & 에러 처리

- 정상 종료: `0`
- 오류 종료(잘못된 입력, 존재하지 않는 id/카테고리 등): `1`
- 에러 발생 시 파이썬 스택트레이스 대신 아래 형식으로 출력됩니다.

```
[오류] 존재하지 않는 거래 id입니다: T9999
[해결 힌트] id 또는 이름을 다시 확인해 주세요. list 명령으로 목록을 확인할 수 있습니다.
```
