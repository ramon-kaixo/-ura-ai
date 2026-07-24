from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum


class Status(StrEnum):
    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass
class ToolResult:
    name: str
    status: Status
    seconds: float = 0.0
    summary: str = ""
    detail: str = ""
    fixable: bool = False


class ToolBase(ABC):
    name: str = ""

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def run_check(self, files: list[str] | None = None) -> ToolResult: ...

    @abstractmethod
    def run_fix(self, files: list[str] | None = None) -> ToolResult: ...

    @abstractmethod
    def severity(self) -> str: ...
