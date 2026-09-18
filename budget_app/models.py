"""데이터 모델 정의 모듈.

이 프로그램에서 다루는 세 가지 데이터(거래, 카테고리, 예산)를
dataclass로 정의한다. dataclass를 쓰면 필드 이름/타입이 코드만 봐도
분명해지고, 실수로 필드를 빠뜨리는 것도 줄어든다.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

# 허용되는 거래 타입. 다른 모듈에서도 이 값을 기준으로 검증한다.
ALLOWED_TYPES = ("income", "expense")


@dataclass
class Transaction:
    """거래 내역 한 건을 표현하는 데이터 클래스.

    Attributes:
        id: 거래를 구분하는 유일한 식별자. 예) "T0001"
        type: "income"(수입) 또는 "expense"(지출)
        date: "YYYY-MM-DD" 형식의 날짜 문자열
        amount: 0보다 큰 정수 금액
        category: 등록된 카테고리 이름
        memo: 선택 입력 메모
        tags: 선택 입력 태그 목록
    """

    id: str
    type: str
    date: str
    amount: int
    category: str
    memo: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """JSONL 한 줄로 저장하기 위한 dict 변환."""
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Transaction":
        """JSONL에서 읽은 dict를 다시 Transaction 객체로 변환."""
        return Transaction(
            id=data["id"],
            type=data["type"],
            date=data["date"],
            amount=int(data["amount"]),
            category=data["category"],
            memo=data.get("memo"),
            tags=list(data.get("tags") or []),
        )


@dataclass
class Category:
    """카테고리 한 건을 표현하는 데이터 클래스."""

    name: str

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Category":
        return Category(name=data["name"])


@dataclass
class Budget:
    """월별 예산 한 건을 표현하는 데이터 클래스."""

    month: str  # "YYYY-MM"
    amount: int

    def to_dict(self) -> Dict[str, Any]:
        return {"month": self.month, "amount": self.amount}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Budget":
        return Budget(month=data["month"], amount=int(data["amount"]))
