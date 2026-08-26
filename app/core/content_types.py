"""content_type(MIME) → 파일 확장자 변환.

MARS/브라우저가 주는 MIME 문자열은 벤더마다 표기가 달라(hwp는 표준 MIME 자체가 없다)
완전 일치 매핑 대신 키워드 포함 여부로 판별한다.

DB에 저장된 원본 content_type은 그대로 두고, 응답 스키마에서 표시용으로만 변환한다.
(다운로드 응답의 media_type에는 원본 content_type을 그대로 써야 한다)
"""

import re
from typing import Annotated

from pydantic import AfterValidator

# (키워드 패턴, 확장자) — 위에서부터 첫 매치를 사용하므로 구체적인 것을 먼저 둔다.
_EXT_PATTERNS: list[tuple[str, str]] = [
    (r"pdf", ".pdf"),                 # application/pdf
    (r"markdown", ".md"),             # text/markdown, text/x-markdown
    (r"hwp", ".hwp"),                 # application/x-hwp, application/haansofthwp
    (r"wordprocessingml", ".docx"),   # application/vnd.openxmlformats-...
    (r"plain", ".txt"),               # text/plain
]


def to_extension(content_type: str | None) -> str | None:
    """content_type을 확장자(.pdf 등)로 변환한다.

    매칭되는 키워드가 없으면 원본을 그대로 반환한다 (알 수 없는 타입을 숨기지 않기 위함).
    """
    if not content_type:
        return content_type

    for pattern, ext in _EXT_PATTERNS:
        if re.search(pattern, content_type, re.IGNORECASE):
            return ext
    return content_type


# 응답 스키마에서 content_type 필드에 쓰는 타입.
# 이 타입으로 선언하면 값이 자동으로 확장자(.pdf 등)로 변환된다.
ContentTypeExt = Annotated[str | None, AfterValidator(to_extension)]
