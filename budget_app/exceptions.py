"""앱에서 사용하는 사용자 정의 예외 모음.

BudgetAppError를 상속한 예외는 handle_errors 데코레이터가 잡아서
"원인 + 해결 힌트" 형태로 사용자에게 보여주고, 프로그램은 0이 아닌
종료 코드로 끝난다. 스택트레이스를 그대로 보여주지 않기 위한 장치다.
"""
from __future__ import annotations


class BudgetAppError(Exception):
    """앱에서 발생하는 모든 '사용자에게 보여줄' 오류의 기반 클래스."""

    hint: str = "입력값을 확인한 뒤 다시 시도해 주세요."


class ValidationError(BudgetAppError):
    """입력 형식/값 검증 실패."""

    hint = "입력 형식을 확인해 주세요. (예: 날짜는 YYYY-MM-DD, 금액은 양수 정수)"


class NotFoundError(BudgetAppError):
    """id/이름으로 찾으려는 데이터가 없을 때."""

    hint = "id 또는 이름을 다시 확인해 주세요. list 명령으로 목록을 확인할 수 있습니다."


class CategoryInUseError(BudgetAppError):
    """사용 중인 카테고리를 대체 없이 삭제하려고 할 때."""

    hint = "해당 카테고리를 사용 중인 거래가 있습니다. --replacement 옵션으로 대체 카테고리를 지정하세요."


class DuplicateError(BudgetAppError):
    """이미 존재하는 값을 다시 추가하려고 할 때."""

    hint = "이미 존재하는 값입니다. list 명령으로 확인해 보세요."
