"""서비스 계층: CLI와 저장소(Repository) 사이에서 비즈니스 로직을 담당한다.

CLI는 "사용자 입력을 파싱해서 여기로 넘기는 일", 저장소는 "파일을
읽고 쓰는 일"만 하고, 검증/계산/조합 같은 실제 규칙은 전부 이 파일에
모아둔다. 이렇게 나누면 나중에 CLI를 웹 API로 바꾸더라도 이 파일은
거의 그대로 재사용할 수 있다.
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import Transaction, ALLOWED_TYPES
from .storage import TransactionRepository, CategoryStore, BudgetStore
from .exceptions import ValidationError, NotFoundError, CategoryInUseError, DuplicateError

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def validate_date(date_str: str) -> str:
    if not DATE_RE.match(date_str or ""):
        raise ValidationError(f"날짜 형식이 잘못되었습니다(YYYY-MM-DD): {date_str}")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        raise ValidationError(f"존재하지 않는 날짜입니다: {date_str}") from e
    return date_str


def validate_month(month_str: str) -> str:
    if not MONTH_RE.match(month_str or ""):
        raise ValidationError(f"월 형식이 잘못되었습니다(YYYY-MM): {month_str}")
    return month_str


def validate_type(type_str: str) -> str:
    if type_str not in ALLOWED_TYPES:
        raise ValidationError(f"type은 {ALLOWED_TYPES} 중 하나여야 합니다: {type_str}")
    return type_str


def validate_amount(amount) -> int:
    try:
        amount_int = int(str(amount).strip())
    except (TypeError, ValueError) as e:
        raise ValidationError(f"금액은 정수여야 합니다: {amount}") from e
    if amount_int <= 0:
        raise ValidationError("금액은 0보다 큰 양수여야 합니다.")
    return amount_int


class BudgetService:
    """가계부 기능을 제공하는 서비스 클래스. 세 개의 저장소를 조합해서 동작한다."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.tx_repo = TransactionRepository(self.data_dir / "transactions.jsonl")
        self.cat_store = CategoryStore(self.data_dir / "categories.jsonl")
        self.budget_store = BudgetStore(self.data_dir / "budgets.jsonl")

    # ---------------- 카테고리 ----------------
    def list_categories(self) -> List[str]:
        return self.cat_store.list_all()

    def add_category(self, name: str) -> None:
        try:
            self.cat_store.add(name)
        except ValueError as e:
            raise DuplicateError(f"이미 존재하는 카테고리입니다: {name}") from e

    def remove_category(self, name: str, replacement: Optional[str] = None) -> None:
        if not self.cat_store.exists(name):
            raise NotFoundError(f"존재하지 않는 카테고리입니다: {name}")

        in_use = any(tx.category == name for tx in self.tx_repo.iter_all())
        if in_use:
            if replacement is None:
                raise CategoryInUseError(
                    f"'{name}' 카테고리를 사용 중인 거래가 있습니다."
                )
            if not self.cat_store.exists(replacement):
                raise NotFoundError(f"대체 카테고리가 존재하지 않습니다: {replacement}")
            updated = []
            for tx in self.tx_repo.iter_all():
                if tx.category == name:
                    tx.category = replacement
                updated.append(tx)
            self.tx_repo.rewrite_all(updated)

        self.cat_store.remove(name)

    # ---------------- 거래 ----------------
    def add_transaction(
        self,
        date: str,
        type_: str,
        category: str,
        amount,
        memo: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Transaction:
        date = validate_date(date)
        type_ = validate_type(type_)
        amount_int = validate_amount(amount)
        if not self.cat_store.exists(category):
            raise ValidationError(f"등록되지 않은 카테고리입니다: {category}")

        tx = Transaction(
            id=self.tx_repo.next_id(),
            type=type_,
            date=date,
            amount=amount_int,
            category=category,
            memo=memo,
            tags=tags or [],
        )
        self.tx_repo.append(tx)
        return tx

    def list_transactions(self, limit: int = 20) -> List[Transaction]:
        """최신순으로 최대 limit개의 거래를 반환한다.

        tx_repo.iter_all()은 제너레이터이므로 파일을 한 줄씩 파싱하며 리스트에
        담는다(파싱 자체가 스트리밍). 이후 날짜 기준으로 정렬해 최신순 limit개만 취한다.
        """
        items = list(self.tx_repo.iter_all())
        items.sort(key=lambda t: (t.date, t.id), reverse=True)
        return items[:limit]

    def search_transactions(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        category: Optional[str] = None,
        type_: Optional[str] = None,
        q: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Transaction]:
        def matches(tx: Transaction) -> bool:
            if date_from and tx.date < date_from:
                return False
            if date_to and tx.date > date_to:
                return False
            if category and tx.category != category:
                return False
            if type_ and tx.type != type_:
                return False
            if q and (not tx.memo or q.lower() not in tx.memo.lower()):
                return False
            if tag and tag not in tx.tags:
                return False
            return True

        # iter_all()이 한 줄씩 yield하는 것을 바로 필터링한다(스트리밍 필터).
        result = [tx for tx in self.tx_repo.iter_all() if matches(tx)]
        result.sort(key=lambda t: (t.date, t.id), reverse=True)
        return result

    def update_transaction(self, tx_id: str, **fields) -> Transaction:
        found: Optional[Transaction] = None
        all_tx: List[Transaction] = []
        for tx in self.tx_repo.iter_all():
            if tx.id == tx_id:
                found = tx
            all_tx.append(tx)

        if found is None:
            raise NotFoundError(f"존재하지 않는 거래 id입니다: {tx_id}")

        if fields.get("date") is not None:
            found.date = validate_date(fields["date"])
        if fields.get("type") is not None:
            found.type = validate_type(fields["type"])
        if fields.get("category") is not None:
            if not self.cat_store.exists(fields["category"]):
                raise ValidationError(f"등록되지 않은 카테고리입니다: {fields['category']}")
            found.category = fields["category"]
        if fields.get("amount") is not None:
            found.amount = validate_amount(fields["amount"])
        if fields.get("memo") is not None:
            found.memo = fields["memo"]
        if fields.get("tags") is not None:
            found.tags = fields["tags"]

        self.tx_repo.rewrite_all(all_tx)
        return found

    def delete_transaction(self, tx_id: str) -> None:
        all_tx = list(self.tx_repo.iter_all())
        remaining = [tx for tx in all_tx if tx.id != tx_id]
        if len(remaining) == len(all_tx):
            raise NotFoundError(f"존재하지 않는 거래 id입니다: {tx_id}")
        self.tx_repo.rewrite_all(remaining)

    # ---------------- 요약/예산 ----------------
    def monthly_summary(self, month: str, top_n: int = 3) -> dict:
        month = validate_month(month)
        income = 0
        expense = 0
        by_category: dict = defaultdict(int)
        found_any = False

        for tx in self.tx_repo.iter_all():
            if not tx.date.startswith(month):
                continue
            found_any = True
            if tx.type == "income":
                income += tx.amount
            else:
                expense += tx.amount
                by_category[tx.category] += tx.amount

        top_categories = sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
        budget_amount = self.budget_store.get(month)
        usage_rate = None
        over_budget = False
        if budget_amount:
            usage_rate = round(expense / budget_amount * 100, 1)
            over_budget = expense > budget_amount

        return {
            "month": month,
            "found_any": found_any,
            "income": income,
            "expense": expense,
            "balance": income - expense,
            "top_categories": top_categories,
            "budget_amount": budget_amount,
            "usage_rate": usage_rate,
            "over_budget": over_budget,
        }

    def set_budget(self, month: str, amount) -> None:
        month = validate_month(month)
        amount_int = validate_amount(amount)
        self.budget_store.set(month, amount_int)

    # ---------------- import/export ----------------
    def import_csv(self, path: Path) -> int:
        path = Path(path)
        if not path.exists():
            raise ValidationError(f"파일을 찾을 수 없습니다: {path}")
        count = 0
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tags = [t.strip() for t in (row.get("tags") or "").split(",") if t.strip()]
                self.add_transaction(
                    date=row["date"],
                    type_=row["type"],
                    category=row["category"],
                    amount=row["amount"],
                    memo=(row.get("memo") or None),
                    tags=tags,
                )
                count += 1
        return count

    def export_csv(
        self,
        out_path: Path,
        month: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> int:
        if not month and not date_from and not date_to:
            raise ValidationError("export는 --month 또는 --from/--to 조건이 최소 하나 필요합니다.")
        if not month and bool(date_from) != bool(date_to):
            raise ValidationError("--from과 --to는 함께 지정해야 합니다.")

        if month:
            month = validate_month(month)
            df, dt = f"{month}-01", f"{month}-31"
        else:
            df, dt = date_from, date_to

        rows = self.search_transactions(date_from=df, date_to=dt)
        out_path = Path(out_path)
        with out_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "type", "category", "amount", "memo", "tags"])
            for tx in rows:
                writer.writerow(
                    [tx.date, tx.type, tx.category, tx.amount, tx.memo or "", ",".join(tx.tags)]
                )
        return len(rows)
