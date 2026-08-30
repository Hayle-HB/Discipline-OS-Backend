from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ApiSuccessResponse(BaseModel):
    success: bool = True
    data: Any
    message: str | None = None


class ApiErrorResponse(BaseModel):
    success: bool = False
    error: str
    code: str | None = None


def success_response(
    data: Any,
    message: str | None = None,
    status_code: int = 200,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ApiSuccessResponse(data=data, message=message).model_dump(exclude_none=True),
    )


def error_response(
    error: str,
    status_code: int = 400,
    code: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ApiErrorResponse(error=error, code=code).model_dump(exclude_none=True),
    )
