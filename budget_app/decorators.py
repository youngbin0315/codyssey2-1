"""공통 관심사(로그, 실행 시간 측정, 예외 처리)를 함수 본문과 분리하는 데코레이터 모듈.

핵심 아이디어: "무엇을 하는가"(비즈니스 로직)와 "그 주변에서 항상
반복되는 일"(로그 남기기, 시간 재기, 에러 잡아서 보기 좋게 출력하기)을
분리한다. 이렇게 하면 cli.py의 명령어 처리 함수는 로직만 신경 쓰면 되고,
로그/시간/예외 처리는 데코레이터가 한 곳에서 책임진다.
"""
from __future__ import annotations

import functools
import sys
import time
from typing import Callable, TypeVar

from .exceptions import BudgetAppError

F = TypeVar("F", bound=Callable[..., object])

# --verbose 옵션으로 켜고 끄는 전역 스위치. 모듈 전역 변수라 데코레이터들이
# 공유해서 참조할 수 있다.
_VERBOSE = False


def set_verbose(verbose: bool) -> None:
    global _VERBOSE
    _VERBOSE = verbose


def log_execution(func: F) -> F:
    """함수 실행 시작/종료를 표준 에러로 로그 남기는 데코레이터."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if _VERBOSE:
            print(f"[LOG] '{func.__name__}' 명령 실행 시작", file=sys.stderr)
        result = func(*args, **kwargs)
        if _VERBOSE:
            print(f"[LOG] '{func.__name__}' 명령 실행 종료", file=sys.stderr)
        return result

    return wrapper  # type: ignore[return-value]


def measure_time(func: F) -> F:
    """함수 실행 시간을 측정해서 표준 에러로 출력하는 데코레이터."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            if _VERBOSE:
                print(f"[TIME] '{func.__name__}' 실행 시간: {elapsed:.4f}초", file=sys.stderr)

    return wrapper  # type: ignore[return-value]


def handle_errors(func: F) -> F:
    """예외를 잡아서 '원인 + 해결 힌트' 형태로 출력하고, 종료 코드를 결정하는 데코레이터.

    - BudgetAppError(및 그 하위 클래스): 우리가 예상한 사용자 오류 -> 메시지 + 힌트 출력, exit(1)
    - KeyboardInterrupt: 사용자가 Ctrl+C로 취소 -> 조용히 exit(1)
    - 그 외 모든 예외: 예상 못한 버그 -> 스택트레이스 대신 요약만 출력, exit(1)
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BudgetAppError as e:
            print(f"[오류] {e}", file=sys.stderr)
            print(f"[해결 힌트] {e.hint}", file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            print("\n[중단] 사용자가 작업을 취소했습니다.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:  # noqa: BLE001 - 의도적으로 모든 예외를 마지막에 잡는다.
            print(f"[알 수 없는 오류] {e}", file=sys.stderr)
            print("[해결 힌트] 입력값과 데이터 파일 상태를 확인해 주세요.", file=sys.stderr)
            sys.exit(1)

    return wrapper  # type: ignore[return-value]
