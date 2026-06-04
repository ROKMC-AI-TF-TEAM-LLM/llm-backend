# llm-backend

FastAPI 기반 LLM 미들웨어 서버입니다. 사용자의 요청을 받아 LLM 서버로 전달하고, 응답을 다시 사용자에게 반환합니다.

## 아키텍처

```
사용자 → FastAPI Backend (이 서버) → LLM Server (/api/rag/agent/stream)
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
│   │   └── source.py                  # Source (메시지 출처)
│   ├── schemas/
│   │   ├── common.py                  # ApiResponse (공통 응답 래퍼)
│   │   ├── user.py                    # UserCreate, UserUpdate, UserResponse 등
│   │   ├── auth.py                    # LoginRequest, TokenResponse 등
│   │   ├── session.py                 # SessionCreate, SessionResponse, SessionPageResponse
│   │   ├── message.py                 # ChatRequest, MessageResponse, MessageListResponse
│   │   └── document.py                # DocumentListResponse
│   ├── services/
│   │   ├── auth_service.py            # JWT 발급/검증, 로그인
│   │   ├── user_service.py            # 유저 CRUD, 승인/거절
│   │   ├── session_service.py         # 세션 CRUD, cursor 기반 페이지네이션
│   │   ├── message_service.py         # 메시지 저장, LLM 스트리밍, 출처 저장
│   │   ├── document_service.py        # LLM 서버 문서 목록 프록시
│   │   ├── health_service.py          # DB / LLM 서버 헬스체크
│   │   └── llm_client.py              # LLM 서버 HTTP 스트리밍 클라이언트
│   └── api/v1/routes/
│       ├── health.py                  # GET /health
│       ├── auth.py                    # POST /auth/signup|login|refresh|logout
│       ├── user.py                    # GET /users/me
│       ├── session.py                 # CRUD /sessions
│       ├── message.py                 # GET|POST /sessions/{id}/messages
│       ├── admin.py                   # GET|PATCH|DELETE /admin/users
│       └── document.py                # GET /documents
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
| DELETE | `/api/v1/sessions/{id}` | 세션 삭제 (하위 메시지 함께 삭제) | 필요 |
| GET | `/api/v1/sessions/{id}/messages` | 메시지 이력 조회 (출처 포함) | 필요 |
| POST | `/api/v1/sessions/{id}/messages/stream` | LLM 스트리밍 채팅 (SSE) | 필요 |
| GET | `/api/v1/documents` | RAG 문서 목록 (offset 기반 무한 스크롤) | 필요 |
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
| `EMAIL_ALREADY_EXISTS` | 409 | 이메일 중복 |
| `VALIDATION_ERROR` | 422 | 요청 파라미터 유효성 오류 |
| `LLM_SERVER_ERROR` | 502 | LLM 서버 연결 오류 |

## 무한 스크롤 페이지네이션

### 세션 목록 — cursor 기반

`updated_at` 기준으로 최신순 정렬. 세션 업데이트 시 순서가 바뀌어도 중복/누락 없음.

```
첫 요청:  GET /api/v1/sessions?size=20
다음 요청: GET /api/v1/sessions?cursor={next_cursor}&size=20
종료 조건: has_next == false
```

```json
{
  "items": [ { "session_id": "...", "title": "...", "updated_at": "..." } ],
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

## LLM 스트리밍 응답 형식

`POST /api/v1/sessions/{id}/messages/stream`은 `text/event-stream` (SSE) 형식으로 응답합니다.

```
// 텍스트 토큰 (토큰 단위 스트리밍)
data: 안녕

data: 하세요

// 참조 문서 출처
data: {"type": "sources", "items": [{"name": "doc.pdf", "page": "3"}]}

// 응답 완료
data: {"type": "done"}

// 오류 발생
data: {"type": "error", "message": "오류 내용"}
```

## 메시지 출처 (Source)

AI 응답에 참조한 문서 정보가 `sources` 배열로 함께 반환됩니다.

```json
// GET /api/v1/sessions/{id}/messages 응답 예시
{
  "session_id": "...",
  "messages": [
    {
      "role": "human",
      "content": "질문 내용",
      "created_at": "...",
      "sources": []
    },
    {
      "role": "ai",
      "content": "AI 응답 내용",
      "created_at": "...",
      "sources": [
        { "name": "doc.pdf", "page": "3" }
      ]
    }
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
| `DATABASE_URL` | — | PostgreSQL 연결 문자열 (`postgresql+asyncpg://user:pw@host:5432/db`) |
| `JWT_SECRET_KEY` | — | JWT 서명 키 (반드시 환경변수로 설정) |
| `JWT_ALGORITHM` | `HS256` | JWT 알고리즘 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | 액세스 토큰 만료 시간 (분) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | 리프레시 토큰 만료 시간 (일) |
| `LOG_LEVEL` | `INFO` | 로그 레벨 (`DEBUG`, `INFO`, `WARNING`) |
