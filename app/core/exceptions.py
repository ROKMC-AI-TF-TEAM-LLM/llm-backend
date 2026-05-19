class AppError(Exception):
    """프로젝트의 모든 커스텀 예외의 베이스 클래스."""


class UserError(AppError):
    """User 엔티티 전용 예외"""

# HTTP 예외 핸들러
class AppHTTPException(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    detail: str = "Internal Server Error"

    def __init__(self, detail: str | None = None, error_code: str | None = None):
        self.detail = detail if detail is not None else self.__class__.detail
        self.error_code = error_code if error_code is not None else self.__class__.error_code
        super().__init__(self.detail)


class BadRequestError(AppHTTPException):
    status_code = 400
    error_code = "BAD_REQUEST"
    detail = "Bad Request"


class UnauthorizedError(AppHTTPException):
    status_code = 401
    error_code = "UNAUTHORIZED"
    detail = "Unauthorized"


class ForbiddenError(AppHTTPException):
    status_code = 403
    error_code = "FORBIDDEN"
    detail = "Forbidden"


class NotFoundError(AppHTTPException):
    status_code = 404
    error_code = "NOT_FOUND"
    detail = "Not Found"


class ConflictError(AppHTTPException):
    status_code = 409
    error_code = "CONFLICT"
    detail = "Conflict"


class InternalServerError(AppHTTPException):
    status_code = 500
    error_code = "INTERNAL_ERROR"
    detail = "Internal Server Error"
