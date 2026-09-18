"""CLI 계층: 사용자 입력을 파싱하고 서비스 계층을 호출한다.

이 파일은 "무엇을 어떻게 계산하는지"는 모른다. 오직
1) argparse로 옵션을 해석하고
2) add처럼 대화형이 필요한 명령은 input()으로 값을 받고
3) BudgetService에 위임한 뒤
4) 결과를 사람이 보기 좋은 형태로 출력하는 일만 한다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .services import BudgetService, validate_date
from .decorators import handle_errors, log_execution, measure_time, set_verbose
from .exceptions import ValidationError
from .models import Transaction


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="budget_app",
        description="파일 기반 콘솔 가계부 프로그램",
    )
    parser.add_argument("--data-dir", default="./data", help="데이터 저장 폴더 (기본값: ./data)")
    parser.add_argument("--verbose", action="store_true", help="실행 로그/실행 시간을 함께 출력")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("add", help="거래 추가 (대화형 입력)")

    p_list = sub.add_parser("list", help="거래 목록 조회 (최신순)")
    p_list.add_argument("--limit", type=int, default=20, help="출력할 최대 건수 (기본값: 20)")

    p_search = sub.add_parser("search", help="조건에 맞는 거래 검색")
    p_search.add_argument("--from", dest="date_from", help="검색 시작일 YYYY-MM-DD")
    p_search.add_argument("--to", dest="date_to", help="검색 종료일 YYYY-MM-DD")
    p_search.add_argument("--category", help="카테고리로 필터링")
    p_search.add_argument("--type", choices=["income", "expense"], help="타입으로 필터링")
    p_search.add_argument("--q", help="메모에 포함된 키워드로 필터링")
    p_search.add_argument("--tag", help="태그로 필터링")

    p_summary = sub.add_parser("summary", help="월별 요약 출력")
    p_summary.add_argument("--month", required=True, help="YYYY-MM")
    p_summary.add_argument("--top", type=int, default=3, help="카테고리별 지출 상위 N개 (기본값: 3)")

    p_budget = sub.add_parser("budget", help="예산 설정/조회")
    budget_sub = p_budget.add_subparsers(dest="budget_command", required=True)
    p_budget_set = budget_sub.add_parser("set", help="월 예산 설정")
    p_budget_set.add_argument("--month", required=True, help="YYYY-MM")
    p_budget_set.add_argument("--amount", required=True, help="예산 금액(양수 정수)")

    p_category = sub.add_parser("category", help="카테고리 관리")
    cat_sub = p_category.add_subparsers(dest="category_command", required=True)
    cat_sub.add_parser("list", help="카테고리 목록 조회")
    p_cat_add = cat_sub.add_parser("add", help="카테고리 추가")
    p_cat_add.add_argument("name")
    p_cat_remove = cat_sub.add_parser("remove", help="카테고리 삭제")
    p_cat_remove.add_argument("name")
    p_cat_remove.add_argument("--replacement", help="사용 중인 카테고리를 삭제할 때 대체할 카테고리")

    # update는 "옵션 기반"으로 고정한다 (README에도 명시).
    p_update = sub.add_parser("update", help="거래 수정 (옵션 기반, --id 필수)")
    p_update.add_argument("--id", required=True)
    p_update.add_argument("--date")
    p_update.add_argument("--type", choices=["income", "expense"])
    p_update.add_argument("--category")
    p_update.add_argument("--amount")
    p_update.add_argument("--memo")
    p_update.add_argument("--tags", help="쉼표(,)로 구분된 태그 목록")

    p_delete = sub.add_parser("delete", help="거래 삭제")
    p_delete.add_argument("--id", required=True)

    p_import = sub.add_parser("import", help="CSV 파일에서 거래 일괄 등록")
    p_import.add_argument("--from", dest="path", required=True, help="가져올 CSV 파일 경로")

    p_export = sub.add_parser("export", help="조건에 맞는 거래를 CSV로 내보내기")
    p_export.add_argument("--out", required=True, help="저장할 CSV 파일 경로")
    p_export.add_argument("--month", help="YYYY-MM")
    p_export.add_argument("--from", dest="date_from", help="YYYY-MM-DD (--to와 함께 사용)")
    p_export.add_argument("--to", dest="date_to", help="YYYY-MM-DD (--from과 함께 사용)")

    return parser


def _prompt(label: str) -> str:
    return input(f"{label}: ").strip()


def interactive_add(service: BudgetService) -> None:
    """add 명령의 대화형 입력 흐름. 형식이 틀리면 그 필드만 다시 물어본다."""
    print("=== 거래 추가 (Ctrl+C로 취소 가능) ===")

    while True:
        date = _prompt("날짜 (YYYY-MM-DD)")
        try:
            validate_date(date)
            break
        except ValidationError as e:
            print(f"  -> 다시 입력해주세요: {e}")

    while True:
        type_ = _prompt("타입 (income/expense)")
        if type_ in ("income", "expense"):
            break
        print("  -> 다시 입력해주세요: type은 income 또는 expense 여야 합니다.")

    categories = service.list_categories()
    print(f"등록된 카테고리: {', '.join(categories) if categories else '(없음, 먼저 category add로 등록하세요)'}")
    while True:
        category = _prompt("카테고리")
        if service.cat_store.exists(category):
            break
        print(f"  -> 등록되지 않은 카테고리입니다. 'category add {category}'로 먼저 등록하거나 다른 이름을 입력하세요.")

    while True:
        amount_str = _prompt("금액 (양수 정수)")
        try:
            amount = int(amount_str)
            if amount <= 0:
                raise ValueError
            break
        except ValueError:
            print("  -> 다시 입력해주세요: 금액은 0보다 큰 정수여야 합니다.")

    memo = _prompt("메모 (선택, 그냥 엔터 가능)") or None
    tags_str = _prompt("태그 (쉼표로 구분, 선택, 그냥 엔터 가능)")
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]

    tx = service.add_transaction(date=date, type_=type_, category=category, amount=amount, memo=memo, tags=tags)
    print(f"✅ 저장 완료! 생성된 거래 id: {tx.id}")


def print_transactions(transactions: List[Transaction]) -> None:
    if not transactions:
        print("표시할 거래가 없습니다.")
        return
    print(f"{'id':<8}{'date':<12}{'type':<9}{'category':<12}{'amount':>10}  memo/tags")
    print("-" * 72)
    for tx in transactions:
        tag_part = f" #{','.join(tx.tags)}" if tx.tags else ""
        memo_part = tx.memo or ""
        print(f"{tx.id:<8}{tx.date:<12}{tx.type:<9}{tx.category:<12}{tx.amount:>10}  {memo_part}{tag_part}")


@log_execution
@measure_time
@handle_errors
def dispatch(args: argparse.Namespace) -> int:
    service = BudgetService(Path(args.data_dir))

    if args.command == "add":
        interactive_add(service)

    elif args.command == "list":
        print_transactions(service.list_transactions(limit=args.limit))

    elif args.command == "search":
        txs = service.search_transactions(
            date_from=args.date_from,
            date_to=args.date_to,
            category=args.category,
            type_=args.type,
            q=args.q,
            tag=args.tag,
        )
        print_transactions(txs)

    elif args.command == "summary":
        result = service.monthly_summary(args.month, top_n=args.top)
        if not result["found_any"]:
            print(f"{args.month}: 데이터 없음")
        else:
            print(f"=== {args.month} 요약 ===")
            print(f"총수입: {result['income']:,}")
            print(f"총지출: {result['expense']:,}")
            print(f"잔액:   {result['balance']:,}")
            print(f"카테고리별 지출 TOP {args.top}:")
            if result["top_categories"]:
                for i, (cat, amt) in enumerate(result["top_categories"], start=1):
                    print(f"  {i}. {cat}: {amt:,}")
            else:
                print("  (지출 내역 없음)")
            if result["budget_amount"] is not None:
                print(f"예산: {result['budget_amount']:,} / 사용률: {result['usage_rate']}%")
                if result["over_budget"]:
                    print("⚠️  예산을 초과했습니다!")

    elif args.command == "budget":
        if args.budget_command == "set":
            service.set_budget(args.month, args.amount)
            print(f"✅ {args.month} 예산 {int(args.amount):,}원 저장 완료")

    elif args.command == "category":
        if args.category_command == "list":
            cats = service.list_categories()
            print("카테고리 목록:", ", ".join(cats) if cats else "(없음)")
        elif args.category_command == "add":
            service.add_category(args.name)
            print(f"✅ 카테고리 '{args.name}' 추가 완료")
        elif args.category_command == "remove":
            service.remove_category(args.name, replacement=args.replacement)
            print(f"✅ 카테고리 '{args.name}' 삭제 완료")

    elif args.command == "update":
        fields = {
            "date": args.date,
            "type": args.type,
            "category": args.category,
            "amount": args.amount,
            "memo": args.memo,
            "tags": (
                [t.strip() for t in args.tags.split(",") if t.strip()]
                if args.tags is not None
                else None
            ),
        }
        tx = service.update_transaction(args.id, **fields)
        print(f"✅ 거래 {tx.id} 수정 완료")

    elif args.command == "delete":
        service.delete_transaction(args.id)
        print(f"✅ 거래 {args.id} 삭제 완료")

    elif args.command == "import":
        count = service.import_csv(Path(args.path))
        print(f"✅ {count}건 가져오기 완료")

    elif args.command == "export":
        count = service.export_csv(
            Path(args.out), month=args.month, date_from=args.date_from, date_to=args.date_to
        )
        print(f"✅ {count}건을 '{args.out}' 파일로 내보내기 완료")

    return 0


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    set_verbose(args.verbose)
    exit_code = dispatch(args)
    sys.exit(exit_code if exit_code is not None else 0)
