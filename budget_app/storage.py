"""파일 기반 저장소(Repository) 모듈.

JSONL(줄마다 JSON 객체 하나) 포맷으로 데이터를 영구 저장한다.
거래 내역은 제너레이터(iter_all)로 한 줄씩 읽어 스트리밍 처리하고,
수정/삭제처럼 파일 전체가 바뀌어야 하는 작업은 "임시 파일에 먼저 쓰고
os.replace로 원자적으로 교체"하는 방식을 써서 중간에 프로그램이
죽어도 원본 파일이 깨지지 않도록 한다.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Iterator, List, Optional

from .models import Transaction, Category


class TransactionRepository:
    """transactions.jsonl 파일을 다루는 저장소."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()  # 최초 실행이면 빈 파일을 만든다.

    def append(self, tx: Transaction) -> None:
        """거래 한 건을 파일 맨 끝에 追加(append)한다. add 명령에서 사용."""
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(tx.to_dict(), ensure_ascii=False) + "\n")

    def iter_all(self) -> Iterator[Transaction]:
        """파일을 한 줄씩 읽어서 Transaction 객체를 yield하는 제너레이터.

        list()로 감싸서 강제로 다 읽지 않는 이상, 이 함수는 파일 전체를
        한 번에 메모리에 올리지 않는다. 호출하는 쪽(services.py)에서
        필요한 만큼만 소비(consume)하면 큰 파일도 메모리 걱정 없이 처리할 수 있다.
        """
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                yield Transaction.from_dict(data)

    def next_id(self) -> str:
        """가장 큰 숫자 id + 1을 "T0001" 형식으로 반환한다."""
        max_num = 0
        for tx in self.iter_all():
            digits = "".join(ch for ch in tx.id if ch.isdigit())
            if digits:
                max_num = max(max_num, int(digits))
        return f"T{max_num + 1:04d}"

    def rewrite_all(self, transactions: List[Transaction]) -> None:
        """전체 내역을 임시 파일에 쓴 뒤 원자적으로 교체한다.

        update/delete처럼 "일부만 바꾸고 나머지는 그대로 다시 써야 하는"
        작업에서 사용한다. 쓰다가 실패해도 원본 파일은 그대로 남는다.
        """
        fd, tmp_path = tempfile.mkstemp(dir=str(self.path.parent), prefix=".tmp_tx_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for tx in transactions:
                    f.write(json.dumps(tx.to_dict(), ensure_ascii=False) + "\n")
            os.replace(tmp_path, self.path)  # 원자적 교체
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise


class CategoryStore:
    """categories.jsonl 파일을 다루는 저장소."""

    # 카테고리 파일이 비어 있을 때 자동으로 채워 넣는 기본 카테고리(안 A 채택).
    DEFAULT_CATEGORIES = ["food", "transport", "rent", "salary", "etc"]

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self.path.exists()
        if is_new:
            self.path.touch()
            self._write_all([Category(name=n) for n in self.DEFAULT_CATEGORIES])

    def _write_all(self, cats: List[Category]) -> None:
        fd, tmp_path = tempfile.mkstemp(dir=str(self.path.parent), prefix=".tmp_cat_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for c in cats:
                f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
        os.replace(tmp_path, self.path)

    def list_all(self) -> List[str]:
        names: List[str] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                names.append(Category.from_dict(json.loads(line)).name)
        return names

    def exists(self, name: str) -> bool:
        return name in self.list_all()

    def add(self, name: str) -> None:
        cats = self.list_all()
        if name in cats:
            raise ValueError(f"duplicate category: {name}")
        cats.append(name)
        self._write_all([Category(name=n) for n in cats])

    def remove(self, name: str) -> None:
        cats = self.list_all()
        if name not in cats:
            raise KeyError(name)
        cats.remove(name)
        self._write_all([Category(name=n) for n in cats])


class BudgetStore:
    """budgets.jsonl 파일을 다루는 저장소. 월(month)을 키로 예산 금액을 저장한다."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def _read_all(self) -> dict:
        budgets: dict = {}
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                budgets[data["month"]] = int(data["amount"])
        return budgets

    def get(self, month: str) -> Optional[int]:
        return self._read_all().get(month)

    def set(self, month: str, amount: int) -> None:
        budgets = self._read_all()
        budgets[month] = amount
        fd, tmp_path = tempfile.mkstemp(dir=str(self.path.parent), prefix=".tmp_bud_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for m, a in budgets.items():
                f.write(json.dumps({"month": m, "amount": a}, ensure_ascii=False) + "\n")
        os.replace(tmp_path, self.path)
