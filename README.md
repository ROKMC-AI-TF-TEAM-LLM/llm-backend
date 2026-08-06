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
| DELETE | `/api/v1/sessions/{id}/messages/{msg_id}` | 메시지 삭제 | 필요 |
| POST | `/api/v1/sessions/{id}/messages/{msg_id}/regenerate` | AI 응답 재생성 (SSE) | 필요 |
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
| `MESSAGE_NOT_FOUND` | 404 | 메시지 없음 |
| `INVALID_MESSAGE_ROLE` | 400 | AI 메시지가 아닌 메시지로 재생성 요청 |
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

`POST /api/v1/sessions/{id}/messages/stream` 및 `POST /api/v1/sessions/{id}/messages/{msg_id}/regenerate` 는 `text/event-stream` (SSE) 형식으로 응답합니다.

```
// 텍스트 토큰 (토큰 단위 스트리밍)
data: 안녕

data: 하세요

// 참조 문서 출처
data: {"type": "sources", "items": [{"name": "doc.pdf", "page": "3"}]}

// 응답 완료
data: {"type": "done"}

// 오류 발생 (LLM 오류, 빈 응답, 메시지 없음, role 오류 포함)
data: {"type": "error", "message": "오류 내용"}
```

> **재생성 흐름:** `regenerate` 엔드포인트는 기존 AI 메시지를 삭제하고 동일한 질문으로 LLM에 재요청합니다. `message_id`는 반드시 `role: "ai"`인 메시지여야 합니다.

## 메시지 이력 응답

AI 응답에 참조한 문서 정보가 `sources` 배열로 함께 반환됩니다. 각 메시지에 `message_id`가 포함됩니다.

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

```json
// GET /api/v1/documents?offset=0&limit=20 응답 예시
{
  "items": [
    {
      "name": "산업 디지털 전환법(20260701).pdf",
      "type": "PDF",
      "applied_at": "2026-05-26T19:00:52Z"
    }
  ],
  "total": 42,
  "offset": 0,
  "limit": 20,
  "has_more": true
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
# MySQL 드라이버(aiomysql, pymysql)는 폐쇄망 대응으로 vendor/ 에 동봉되어 있어
# 별도 설치가 필요 없습니다. (app/__init__.py 가 vendor/ 를 sys.path 에 등록)

# 2. 환경변수 설정
# .env 파일 생성 후 아래 환경변수 항목 참고

# 3. DB 생성 (MySQL 8.0)
# mysql에서: CREATE DATABASE prototype_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
# (기존 DB들과 collation을 맞춰야 JOIN 시 충돌이 없습니다)

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

기존 PostgreSQL 기준 리비전 체인은 폐기하고, MySQL 8.0 기준 단일 베이스라인
`b7c1e94f2a30_create_initial_schema_for_mysql.py` 하나로 재구성했습니다.

### MySQL 마이그레이션 주의사항

- **UUID**: `sa.UUID()`가 아니라 **`sa.Uuid()`**를 쓰세요. `sa.UUID()`는 MySQL에 없는
  `UUID` 타입으로 컴파일돼 실패합니다 (`sa.Uuid()` → `CHAR(32)`).
- **타임스탬프**: 모델에서는 `app.core.database.Timestamp`를 쓰고, 마이그레이션에서는
  `sa.DateTime(timezone=True).with_variant(mysql.DATETIME(fsp=6), 'mysql')`를 쓰세요.
  `fsp`를 빼면 마이크로초가 잘리는데, `created_at`/`updated_at`이 커서 페이지네이션
  키라 동시각 레코드에서 누락·중복이 생깁니다.
- **긴 텍스트**: MySQL `TEXT`는 64KB라 긴 LLM 답변이 잘립니다.
  `sa.Text().with_variant(mysql.MEDIUMTEXT(), 'mysql')`를 쓰세요.
- **Enum**: MySQL은 ENUM이 별도 타입이 아니라 컬럼 타입이라 `ALTER TYPE`이 없습니다.
  기존 Enum의 **값 집합을 바꿀 때는** `ALTER TABLE ... MODIFY`로 값 집합을 넓힌 뒤
  `UPDATE`로 데이터를 옮기고 다시 좁히는 3단계가 필요합니다.

적용 전 실제 실행될 SQL을 확인하려면:

```bash
alembic upgrade head --sql
```

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `LLM_SERVER_URL` | `http://localhost:8001` | LLM 서버 주소 |
| `REQUEST_TIMEOUT` | `60` | 연결 타임아웃 (초, read는 무제한) |
| `DATABASE_URL` | — | MySQL 연결 문자열 (`mysql+aiomysql://user:pw@host:3306/db?charset=utf8mb4`) |
| `JWT_SECRET_KEY` | — | JWT 서명 키 (반드시 환경변수로 설정) |
| `JWT_ALGORITHM` | `HS256` | JWT 알고리즘 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | 액세스 토큰 만료 시간 (분) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | 리프레시 토큰 만료 시간 (일) |
| `LOG_LEVEL` | `INFO` | 로그 레벨 (`DEBUG`, `INFO`, `WARNING`) |
| `DB_DISABLE_SSL` | `false` | DB SSL 비활성화 여부 (asyncpg 전용. aiomysql은 기본이 평문 연결이라 무시됨) |
