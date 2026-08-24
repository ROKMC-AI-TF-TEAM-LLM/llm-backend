from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

#: 번역 서버가 지원하는 언어. ko↔en 외의 조합은 번역 서버가 400을 주므로
#: 여기서 Literal로 막아 422로 먼저 거른다.
Lang = Literal["ko", "en"]

#: prompts/styles/*.yaml 에 있는 문체. 모르는 값은 번역 서버가 default로 떨어뜨리지만,
#: 문서에 드러나지 않는 값을 받아두면 오타가 조용히 다른 문체로 번역된다.
Style = Literal["press_release", "default"]


class TranslateRequest(BaseModel):
    # 길이 상한은 번역 서버(NDT_MAX_INPUT_CHARS)가 단일 출처다. 여기서 같이 검사하면
    # 상한이 두 곳이 되어 서로 어긋나므로, 초과 시 413을 그대로 중계만 한다.
    text: str = Field(min_length=1, description="번역할 원문")
    source: Lang = Field(description="원문 언어")
    target: Lang = Field(description="번역할 언어")
    style: Style | None = Field(
        default=None,
        description="번역 문체. 생략하면 번역 서버 기본값(press_release)",
    )


class TermApplied(BaseModel):
    """적용된 군사 용어 한 건. `spans`는 원문(정규화 전) 기준 좌표다."""

    source: str
    target: str
    term_id: str
    spans: list[list[int]] = Field(default_factory=list)
    confidence: str


class TranslateMeta(BaseModel):
    # 번역 서버가 필드를 늘렸을 때 여기서 막으면 응답에서 조용히 사라진다.
    model_config = ConfigDict(extra="allow")

    chunks: int
    retries: int
    elapsed_ms: int
    backend: str
    prompt_version: str
    glossary_version: int | None = None


class TranslateResponse(BaseModel):
    translation: str
    #: 용어 하이라이트 UI가 아직 없어도 그대로 내려준다. 나중에 붙일 때 백엔드를 고치지 않기 위해서다.
    terms_applied: list[TermApplied] = Field(default_factory=list)
    #: 종류마다 형태가 다르다 (term_missing / unknown_candidate / empty_chunk / wrong_language 등).
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    meta: TranslateMeta
