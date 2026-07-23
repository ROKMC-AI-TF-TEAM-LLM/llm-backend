class AppHTTPException(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    detail: str = "Internal Server Error"

    def __init__(self, detail: str | None = None, error_code: str | None = None):
        self.detail = detail if detail is not None else self.__class__.detail
        self.error_code = error_code if error_code is not None else self.__class__.error_code
        super().__init__(self.detail)


# 400
class BadRequestError(AppHTTPException):
    status_code = 400
    error_code = "BAD_REQUEST"
    detail = "Bad Request"


# 401
class UnauthorizedError(AppHTTPException):
    status_code = 401
    error_code = "UNAUTHORIZED"
    detail = "Unauthorized"


class InvalidCredentialsError(AppHTTPException):
    status_code = 401
    error_code = "INVALID_CREDENTIALS"
    detail = "이메일 또는 비밀번호가 올바르지 않습니다."


class TokenInvalidError(AppHTTPException):
    status_code = 401
    error_code = "TOKEN_INVALID"
    detail = "유효하지 않은 토큰입니다."


# 403
class ForbiddenError(AppHTTPException):
    status_code = 403
    error_code = "FORBIDDEN"
    detail = "Forbidden"


class ApprovalPendingError(AppHTTPException):
    status_code = 403
    error_code = "APPROVAL_PENDING"
    detail = "승인 대기 중인 계정입니다."


class ApprovalRejectedError(AppHTTPException):
    status_code = 403
    error_code = "APPROVAL_REJECTED"
    detail = "승인이 거절된 계정입니다."


class AdminRequiredError(AppHTTPException):
    status_code = 403
    error_code = "ADMIN_REQUIRED"
    detail = "관리자 권한이 필요합니다."


class SessionAccessDeniedError(AppHTTPException):
    status_code = 403
    error_code = "SESSION_ACCESS_DENIED"
    detail = "접근 권한이 없습니다."


# 404
class NotFoundError(AppHTTPException):
    status_code = 404
    error_code = "NOT_FOUND"
    detail = "Not Found"


class UserNotFoundError(AppHTTPException):
    status_code = 404
    error_code = "USER_NOT_FOUND"
    detail = "사용자를 찾을 수 없습니다."


class SessionNotFoundError(AppHTTPException):
    status_code = 404
    error_code = "SESSION_NOT_FOUND"
    detail = "세션을 찾을 수 없습니다."


class MessageNotFoundError(AppHTTPException):
    status_code = 404
    error_code = "MESSAGE_NOT_FOUND"
    detail = "메시지를 찾을 수 없습니다."


class AttachmentNotFoundError(AppHTTPException):
    status_code = 404
    error_code = "FILE_NOT_FOUND"
    detail = "파일을 찾을 수 없습니다."


class DocumentNotFoundError(AppHTTPException):
    status_code = 404
    error_code = "DOCUMENT_NOT_FOUND"
    detail = "문서를 찾을 수 없습니다."


class InvalidMessageRoleError(AppHTTPException):
    status_code = 400
    error_code = "INVALID_MESSAGE_ROLE"
    detail = "AI 메시지만 재생성할 수 있습니다."


# 409
class ConflictError(AppHTTPException):
    status_code = 409
    error_code = "CONFLICT"
    detail = "Conflict"


class EmailAlreadyExistsError(AppHTTPException):
    status_code = 409
    error_code = "EMAIL_ALREADY_EXISTS"
    detail = "이미 사용 중인 이메일입니다."

# 413
class FileTooLargeError(AppHTTPException):
    status_code = 413
    error_code = "FILE_TOO_LARGE"
    detail = "업로드할 파일 용량이 50MB를 초과하였습니다."

# 502
class LLMServerError(AppHTTPException):
    status_code = 502
    error_code = "LLM_SERVER_ERROR"
    detail = "LLM 서버 오류가 발생했습니다."


# 500
class InternalServerError(AppHTTPException):
    status_code = 500
    error_code = "INTERNAL_ERROR"
    detail = "Internal Server Error"
