```
                        . - ~ ~ ~ - .
      ..     _      .-~               ~-.
     //|     \ `..~                      `.
    || |      }  }              /       \  \
(\   \\ \~^..'                 |         }  \
 \`.-~  o      /       }       |        /    \
 (__          |       /        |       /      `.
  `- - ~ ~ -._|      /_ - ~ ~ ^|      /- _      `.
              |     /          |     /     ~-.     ~- _
              |_____|          |_____|         ~ - . _ _~_-_
```

# llm-backend

FastAPI 기반 LLM 미들웨어 서버입니다. 사용자의 요청을 받아 LLM 서버로 전달하고, 응답을 다시 사용자에게 반환합니다.

## 아키텍처

```
사용자 → FastAPI Backend (이 서버) → LLM Server (/query, /documents, /capabilities, /health)
```

## 디렉토리 구조

```
llm-backend/
├── app/
│   ├── main.py                        # FastAPI 앱, 라우터 등록, lifespan
│   ├── core/
│   │   ├── config.py                  # 환경변수 (pydantic-settings)
│   │   ├── database.py                # SQLAlchemy 엔진, 세션
│   │   ├── deps.py                    # 인증 의존성 (get_current_user, get_current_admin)
│   │   ├── exceptions.py              # 커스텀 HTTP 예외 (세분화된 에러 코드)
│   │   ├── responses.py               # Swagger 공통 에러 응답 예시
│   │   └── logger.py                  # 로거
│   ├── models/
│   │   ├── user.py                    # User, UserRole, ApprovalStatus
│   │   ├── session.py                 # Session
│   │   ├── message.py                 # Message, RoleEnum
│   │   ├── source.py                  # Source (메시지 출처)
│   │   ├── attachment.py              # Attachment (AI 생성 문서, BYTEA 보관)
│   │   └── document.py                # Document (원본 문서 BYTEA 보관, VisibilityEnum)
│   ├── schemas/
│   │   ├── common.py                  # ApiResponse (공통 응답 래퍼)
│   │   ├── user.py                    # UserCreate, UserUpdate, UserResponse 등
│   │   ├── auth.py                    # LoginRequest, TokenResponse 등
│   │   ├── session.py                 # SessionCreate, SessionResponse, SessionPageResponse
│   │   ├── message.py                 # ChatRequest, RegenerateRequest, MessageResponse 등
│   │   ├── document.py                # DocumentListResponse
│   │   └── capability.py              # CapabilityResponse (domain·tool 목록)
│   ├── services/
│   │   ├── auth_service.py            # JWT 발급/검증, 로그인
│   │   ├── user_service.py            # 유저 CRUD, 승인/거절
│   │   ├── session_service.py         # 세션 CRUD, cursor 기반 페이지네이션
│   │   ├── message_service.py         # 메시지 저장, LLM 스트리밍, 출처 저장
│   │   ├── document_service.py        # LLM 서버 문서 목록 프록시
│   │   ├── capability_service.py      # LLM 서버 domain·tool 목록 프록시
│   │   ├── file_service.py            # 생성 문서(첨부) 조회 + 소유권 검증
│   │   ├── health_service.py          # DB / LLM 서버 헬스체크
│   │   └── llm_client.py              # LLM 서버 HTTP 스트리밍 클라이언트
│   └── api/v1/routes/
│       ├── health.py                  # GET /health
│       ├── auth.py                    # POST /auth/signup|login|refresh|logout
│       ├── user.py                    # GET /users/me
│       ├── session.py                 # CRUD /sessions
│       ├── message.py                 # GET|POST /sessions/{id}/messages
│       ├── admin.py                   # GET|PATCH|DELETE /admin/users
│       ├── document.py                # GET /documents
│       ├── capability.py              # GET /capabilities
│       └── file.py                    # GET /files/{attachment_id}
├── alembic/                           # DB 마이그레이션
├── main.py                            # 서버 실행 진입점
├── .env                               # 환경변수 (git 제외)
└── requirements.txt
```

## API 엔드포인트

| Method | Path | 설명 | 인증 |
|--------|------|------|------|
| GET | `/api/v1/health` | 서버·DB·LLM 연결 상태 확인 | 불필요 |
| POST | `/api/v1/auth/signup` | 회원가입 (승인 대기 상태로 등록) | 불필요 |
| POST | `/api/v1/auth/login` | 로그인 (승인된 계정만 가능) | 불필요 |
| POST | `/api/v1/auth/refresh` | 액세스 토큰 재발급 | 불필요 |
| POST | `/api/v1/auth/logout` | 로그아웃 (Refresh Token 무효화) | 불필요 |
| GET | `/api/v1/users/me` | 내 정보 조회 | 필요 |
| POST | `/api/v1/sessions` | 세션 생성 | 필요 |
| GET | `/api/v1/sessions` | 세션 목록 (cursor 기반 무한 스크롤) | 필요 |
| GET | `/api/v1/sessions/search` | 세션 검색 | 필요 |
| PATCH | `/api/v1/sessions/{id}` | 세션 제목 수정 | 필요 |
| PATCH | `/api/v1/sessions/{id}/favorite` | 세션 즐겨찾기 등록/해제 | 필요 |
| DELETE | `/api/v1/sessions/{id}` | 세션 삭제 (하위 메시지 함께 삭제) | 필요 |
| GET | `/api/v1/sessions/{id}/messages` | 메시지 이력 조회 (출처 포함) | 필요 |
| POST | `/api/v1/sessions/{id}/messages/stream` | LLM 스트리밍 채팅 (SSE) | 필요 |
| DELETE | `/api/v1/sessions/{id}/messages/{msg_id}` | 메시지 삭제 | 필요 |
| POST | `/api/v1/sessions/{id}/messages/{msg_id}/regenerate` | AI 응답 재생성 (SSE) | 필요 |
| GET | `/api/v1/documents` | RAG 문서 목록 (offset 기반, `domain` 필터) | 필요 |
| GET | `/api/v1/documents/{name}/download` | 원본 문서 다운로드 (문서명 조회, 최신본) | 필요 |
| GET | `/api/v1/capabilities` | 채팅에 사용 가능한 domain·tool 목록 | 필요 |
| GET | `/api/v1/files/{attachment_id}` | AI 생성 문서(HWPX 등) 다운로드 | 필요 |
| GET | `/api/v1/admin/users` | 전체 회원 목록 (cursor 기반, 필터/검색) | 관리자 |
| GET | `/api/v1/admin/users/{id}` | 회원 상세 조회 | 관리자 |
| PATCH | `/api/v1/admin/users/{id}/approve` | 회원 가입 승인 | 관리자 |
| PATCH | `/api/v1/admin/users/{id}/reject` | 회원 가입 거절 | 관리자 |
| DELETE | `/api/v1/admin/users/{id}` | 회원 삭제 | 관리자 |

## 공통 응답 형식

모든 API는 `ApiResponse`로 감싸진 일관된 형식으로 응답합니다.

**성공:**
```json
{
  "success": true,
  "status_code": 200,
  "data": { ... },
  "error": null
}
```

**실패:**
```json
{
  "success": false,
  "status_code": 404,
  "data": null,
  "error": {
    "code": "USER_NOT_FOUND",
    "detail": "사용자를 찾을 수 없습니다."
  }
}
```

### 에러 코드

| code | HTTP | 설명 |
|------|------|------|
| `INVALID_CREDENTIALS` | 401 | 이메일 또는 비밀번호 불일치 |
| `TOKEN_INVALID` | 401 | 유효하지 않은 토큰 |
| `APPROVAL_PENDING` | 403 | 승인 대기 중인 계정 |
| `APPROVAL_REJECTED` | 403 | 승인이 거절된 계정 |
| `ADMIN_REQUIRED` | 403 | 관리자 권한 필요 |
| `SESSION_ACCESS_DENIED` | 403 | 세션 접근 권한 없음 |
| `USER_NOT_FOUND` | 404 | 사용자 없음 |
| `SESSION_NOT_FOUND` | 404 | 세션 없음 |
| `MESSAGE_NOT_FOUND` | 404 | 메시지 없음 |
| `INVALID_MESSAGE_ROLE` | 400 | AI 메시지가 아닌 메시지로 재생성 요청 |
| `EMAIL_ALREADY_EXISTS` | 409 | 이메일 중복 |
| `VALIDATION_ERROR` | 422 | 요청 파라미터 유효성 오류 |
| `LLM_SERVER_ERROR` | 502 | LLM 서버 연결 오류 |

## 무한 스크롤 페이지네이션

### 세션 목록 — cursor 기반

`updated_at` 기준으로 최신순 정렬. 세션 업데이트 시 순서가 바뀌어도 중복/누락 없음.
`is_favorite=true` 쿼리 파라미터로 즐겨찾기한 세션만 필터링할 수 있음 (생략 시 전체).

```
첫 요청:  GET /api/v1/sessions?size=20
다음 요청: GET /api/v1/sessions?cursor={next_cursor}&size=20
즐겨찾기만: GET /api/v1/sessions?is_favorite=true&size=20
종료 조건: has_next == false
```

```json
{
  "items": [ { "session_id": "...", "title": "...", "is_favorite": false, "updated_at": "..." } ],
  "next_cursor": "2025-05-10T12:34:56.789Z",
  "has_next": true
}
```

### 문서 목록 — offset 기반

```
첫 요청:  GET /api/v1/documents?offset=0&limit=20
다음 요청: GET /api/v1/documents?offset=20&limit=20
종료 조건: has_more == false
```

### 관리자 회원 목록 — cursor 기반

`role`, `status`, `search` 필터 조합 가능.

```
GET /api/v1/admin/users?role=user&status=pending&search=홍길동&size=20
```

## 세션 즐겨찾기

`PATCH /api/v1/sessions/{id}/favorite` 로 즐겨찾기를 등록/해제합니다. 본인의 세션만 설정 가능합니다.

```json
// 요청
{ "is_favorite": true }

// 응답 (data)
{
  "session_id": "...",
  "title": "새 대화",
  "is_favorite": true,
  "updated_at": "2026-07-13T12:00:00Z"
}
```

> 즐겨찾기 변경은 `updated_at`을 갱신하지 않으므로 세션 목록(최근 수정순)의 순서에 영향을 주지 않습니다.

## LLM 스트리밍 요청/응답 형식

`POST /api/v1/sessions/{id}/messages/stream` 및 `POST /api/v1/sessions/{id}/messages/{msg_id}/regenerate` 는 `text/event-stream` (SSE) 형식으로 응답합니다.

**요청 body** — `domain`·`tool`은 선택이며, 둘 다 생략하면 기존과 동일하게 자동 분류로 동작합니다.

```json
// POST /sessions/{id}/messages/stream
{
  "question": "훈령에서 휴가 규정 알려줘",
  "domain": "DIRECTIVE",   // 선택: 검색 범위 한정
  "tool": "DOC_SEARCH"     // 선택: 처리 경로 강제
}

// POST /sessions/{id}/messages/{msg_id}/regenerate — body 자체가 선택
{ "domain": "MANUAL", "tool": "DOC_SEARCH" }
```

- `domain` — 검색 범위 한정: `HR | TECH | FINANCE_LEGAL | MANUAL(교범) | DIRECTIVE(훈령)`. 빈 값/`ALL` = 전체. 미지 값은 무시(전체). "교범에서만 검색" 모드는 이 필드로 구현
- `tool` — 처리 경로 강제: `DOC_SEARCH | DISCHARGE_DAYS`. 지정 시 자동 분류를 건너뛰고 무조건 해당 경로 (잡담 예외 없음). `SMALLTALK`은 강제 불가(무시됨)
- 조합: `tool=DOC_SEARCH` + `domain=DIRECTIVE` → 훈령 전용 검색 탭 UI
- 사용 가능한 값 목록은 `GET /api/v1/capabilities`로 조회 (하드코딩 대신 이 API를 데이터 소스로 권장)
- 재생성 시 원래 질문의 `domain`·`tool`은 저장되지 않으므로, 같은 모드로 재생성하려면 body에 다시 지정해야 함

```
// 진행 상태 (라우팅/검색/생성 단계 표시용)
data: {"type": "status", "stage": "route", "message": "질문을 분석하는 중..."}

// 답변 텍스트 (토큰 단위 스트리밍)
data: {"type": "text", "content": "안녕"}

data: {"type": "text", "content": "하세요"}

// 참조 문서 출처
data: {"type": "sources", "items": [{"name": "doc.pdf", "page": "3"}]}

// AI 생성 문서 (미들웨어가 저장 후 done 직전에 전송 — 다운로드 버튼 렌더용)
data: {"type": "files", "items": [{"attachment_id": "...", "name": "MARS_답변_20260720.hwpx", "size": 34816, "url": "/api/v1/files/{attachment_id}"}]}

// 응답 완료
data: {"type": "done"}

// 오류 발생 (LLM 오류, 빈 응답, 메시지 없음, role 오류 포함)
data: {"type": "error", "message": "오류 내용"}
```

> **재생성 흐름:** `regenerate` 엔드포인트는 기존 AI 메시지를 삭제하고 동일한 질문으로 LLM에 재요청합니다. `message_id`는 반드시 `role: "ai"`인 메시지여야 합니다.

## AI 생성 문서 (첨부파일)

AI가 답변으로 문서(HWPX 등)를 생성하면 미들웨어가 **답변 완료 시점에 AI 서버에서 파일을 즉시 내려받아 DB에 보관**합니다.
AI 서버의 원본 파일은 정리 주기에 따라 삭제될 수 있지만, 미들웨어에 보관된 사본으로 과거 대화에서도 계속 다운로드할 수 있습니다.

- 답변 텍스트 속 `/files/...` 링크는 저장 시 `/api/v1/files/{attachment_id}`로 치환됨
- AI 서버가 보내는 `{"type": "file", "name": ...}` 이벤트는 미들웨어가 흡수해 저장에 사용하고 프론트로는 전달하지 않음 (프론트는 미들웨어의 `files` 이벤트만 처리하면 됨)
- 스트리밍 종료 직전 `{"type": "files", "items": [...]}` 이벤트로 프론트에 전달
- 메시지 이력 조회 시 각 메시지의 `attachments` 배열로 복원 가능
- 다운로드는 인증 필요 — `<a href>` 대신 **fetch → blob 방식** 사용 (Authorization 헤더 필요)
- 메시지/세션 삭제 시 첨부도 함께 삭제됨 (CASCADE)
- 파일 크기 상한: `MAX_ATTACHMENT_SIZE_MB` (기본 20MB, 초과 시 저장 생략)

## 메시지 이력 응답

AI 응답에 참조한 문서 정보가 `sources` 배열로, 생성 문서가 `attachments` 배열로 함께 반환됩니다. 각 메시지에 `message_id`가 포함됩니다.

```json
// GET /api/v1/sessions/{id}/messages 응답 예시
{
  "session_id": "...",
  "messages": [
    {
      "message_id": "765ada85-6b49-4705-8eb1-6c4e5c13de5c",
      "role": "human",
      "content": "질문 내용",
      "created_at": "2026-06-28T23:34:52Z",
      "sources": []
    },
    {
      "message_id": "2b771768-c406-4540-9b36-1a77c5dbeb13",
      "role": "ai",
      "content": "AI 응답 내용",
      "created_at": "2026-06-28T23:34:53Z",
      "sources": [
        { "name": "doc.pdf", "page": "3" }
      ],
      "attachments": [
        { "attachment_id": "8f14e45f-...", "name": "MARS_답변_20260720_105915.hwpx", "size": 34816 }
      ]
    }
  ]
}
```

## 내 정보 응답

```json
// GET /api/v1/users/me 응답 예시
{
  "name": "홍길동",
  "email": "user@example.com",
  "role": "user",
  "created_at": "2026-06-28T12:00:00Z"
}
```

## 문서 목록 응답

`domain` 쿼리 파라미터로 도메인별 필터링이 가능합니다 (예: `?domain=MANUAL`).

```json
// GET /api/v1/documents?offset=0&limit=20 응답 예시
{
  "documents": [
    {
      "name": "휴가규정.pdf",
      "type": "PDF",
      "domain": "HR",
      "visibility": "ALL",
      "owning_department": "HR_TEAM",
      "applied_at": "2026-07-05T19:09:47"
    }
  ],
  "total": 42,
  "offset": 0,
  "limit": 20,
  "has_more": true
}
```

## 사용 가능한 domain·tool 목록

프론트엔드 도메인 탭/검색 모드 UI의 데이터 소스입니다. `tools` 중 `forcible: true`인 항목만 `tool` 필드로 강제 지정할 수 있습니다.

```json
// GET /api/v1/capabilities 응답 예시 (data)
{
  "domains": [
    { "code": "HR", "label": "인사·복지" },
    { "code": "TECH", "label": "정보화·보안" },
    { "code": "FINANCE_LEGAL", "label": "재무·법무" },
    { "code": "GENERAL", "label": "일반" },
    { "code": "MANUAL", "label": "교범" },
    { "code": "DIRECTIVE", "label": "훈령" }
  ],
  "tools": [
    { "code": "DOC_SEARCH", "description": "군 내부 문서 검색이 필요한 업무·규정·행정 질문", "forcible": true },
    { "code": "SMALLTALK", "description": "인사, 자기소개, 감사, 잡담", "forcible": false },
    { "code": "DISCHARGE_DAYS", "description": "전역일이나 전역까지 남은 날짜를 묻는 질문", "forcible": true }
  ]
}
```

## 회원가입 승인 흐름

1. 회원가입 → `status: pending` 상태로 등록
2. 관리자가 `PATCH /api/v1/admin/users/{id}/approve` 로 승인
3. 승인된 계정만 로그인 가능

> 관리자 계정은 DB에서 직접 `role = 'admin'`, `status = 'approved'` 로 설정해야 합니다.

## 시작하기

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정
# .env 파일 생성 후 아래 환경변수 항목 참고

# 3. DB 생성 (PostgreSQL)
# psql에서: CREATE DATABASE llm_db;

# 4. 테이블 생성
alembic upgrade head

# 5. 서버 실행
python main.py
```

## 실행 방법

```bash
# 개발 서버 (자동 reload)
python main.py

# 운영 서버
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## DB 마이그레이션

```bash
# 마이그레이션 적용
alembic upgrade head

# 모델 변경 후 마이그레이션 파일 생성 → 적용
alembic revision --autogenerate -m "변경 내용"
alembic upgrade head
```

> Enum 컬럼 추가/변경 시 자동 생성된 마이그레이션 파일에 `create()`/`drop()`을 수동으로 추가해야 합니다.

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `LLM_SERVER_URL` | `http://localhost:8001` | LLM 서버 주소 |
| `REQUEST_TIMEOUT` | `60` | 연결 타임아웃 (초, read는 무제한) |
| `MAX_ATTACHMENT_SIZE_MB` | `20` | AI 생성 문서 저장 크기 상한 (MB) |
| `DATABASE_URL` | — | PostgreSQL 연결 문자열 (`postgresql+asyncpg://user:pw@host:5432/db`) |
| `JWT_SECRET_KEY` | — | JWT 서명 키 (반드시 환경변수로 설정) |
| `JWT_ALGORITHM` | `HS256` | JWT 알고리즘 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | 액세스 토큰 만료 시간 (분) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | 리프레시 토큰 만료 시간 (일) |
| `LOG_LEVEL` | `INFO` | 로그 레벨 (`DEBUG`, `INFO`, `WARNING`) |
| `DB_DISABLE_SSL` | `false` | DB SSL 비활성화 여부 (로컬 개발 환경에서 `true` 설정) |
