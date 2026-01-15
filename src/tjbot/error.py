from typing import Dict, Optional


class TJBotError(Exception):
    """
    TJBot specific error class.
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        context: Optional[Dict[str, object]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.code = code
        self.context = context
        self.cause = cause

        if cause:
            # Chain the exception
            self.__cause__ = cause
