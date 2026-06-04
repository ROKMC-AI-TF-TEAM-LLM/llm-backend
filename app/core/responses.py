def _ex(status: int, code: str, detail: str) -> dict:
    return {
        "summary": code,
        "value": {
            "success": False,
            "status_code": status,
            "data": None,
            "error": {"code": code, "detail": detail},
        },
    }


def _resp(description: str, **examples) -> dict:
    return {
        "description": description,
        "content": {"application/json": {"examples": examples}},
    }


# 401
R_401 = {
    401: _resp(
        "인증 실패",
        no_token=_ex(401, "UNAUTHORIZED", "Unauthorized"),
        token_invalid=_ex(401, "TOKEN_INVALID", "유효하지 않은 토큰입니다."),
    )
}

R_401_CREDENTIALS = {
    401: _resp(
        "잘못된 인증 정보",
        invalid_credentials=_ex(401, "INVALID_CREDENTIALS", "이메일 또는 비밀번호가 올바르지 않습니다."),
    )
}

R_401_TOKEN = {
    401: _resp(
        "토큰 오류",
        token_invalid=_ex(401, "TOKEN_INVALID", "유효하지 않은 토큰입니다."),
    )
}

# 403
R_403_ADMIN = {
    403: _resp(
        "관리자 권한 필요",
        admin_required=_ex(403, "ADMIN_REQUIRED", "관리자 권한이 필요합니다."),
    )
}

R_403_APPROVAL = {
    403: _resp(
        "계정 미승인",
        approval_pending=_ex(403, "APPROVAL_PENDING", "승인 대기 중인 계정입니다."),
        approval_rejected=_ex(403, "APPROVAL_REJECTED", "승인이 거절된 계정입니다."),
    )
}

R_403_SESSION = {
    403: _resp(
        "세션 접근 거부",
        access_denied=_ex(403, "SESSION_ACCESS_DENIED", "접근 권한이 없습니다."),
    )
}

# 404
R_404_USER = {
    404: _resp(
        "사용자 없음",
        user_not_found=_ex(404, "USER_NOT_FOUND", "사용자를 찾을 수 없습니다."),
    )
}

R_404_SESSION = {
    404: _resp(
        "세션 없음",
        session_not_found=_ex(404, "SESSION_NOT_FOUND", "세션을 찾을 수 없습니다."),
    )
}

# 409
R_409_EMAIL = {
    409: _resp(
        "이메일 중복",
        email_exists=_ex(409, "EMAIL_ALREADY_EXISTS", "이미 사용 중인 이메일입니다."),
    )
}

# 422
R_422 = {
    422: _resp(
        "요청 유효성 오류",
        validation_error=_ex(422, "VALIDATION_ERROR", "요청 파라미터 유효성 검사 실패"),
    )
}
