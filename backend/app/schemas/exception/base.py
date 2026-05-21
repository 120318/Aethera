from __future__ import annotations

from typing import Any


class AppException(Exception):
    """
    text
    text，text
    """

    def __init__(
        self,
        code: int,
        message_key: str,
        *,
        is_system_error: bool = False,
        data=None,
        params: dict[str, Any] | None = None,
    ):
        if type(self) is AppException:
            raise TypeError("AppException is a base class and cannot be instantiated directly. Use a concrete exception class.")

        self.code = code
        self.message = message_key
        self.is_system_error = is_system_error
        self.data = data
        self.message_key = message_key
        self.params = params or {}
        super().__init__(message_key)

    def __str__(self) -> str:
        return self.message

    def response_content(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message_key": self.message_key,
            "params": self.params,
            "data": self.data,
            "is_system_error": self.is_system_error,
        }
