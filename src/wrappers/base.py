from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Tuple


class BaseMCPWrapper(ABC):
    tool_name: str

    @abstractmethod
    async def estimate_cost(self, params: dict) -> Decimal:
        """Return conservative cost estimate in USDT before making the call."""

    @abstractmethod
    async def call(self, params: dict) -> Tuple[dict, Decimal]:
        """Execute upstream call. Return (result_dict, actual_cost_usdt).
        Raise UpstreamError on upstream failure — caller must not debit.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if upstream API is reachable."""


class UpstreamError(Exception):
    """Raised when the upstream API returns an error after accepting the request."""

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code
