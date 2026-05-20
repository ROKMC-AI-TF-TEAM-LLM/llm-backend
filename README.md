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
│   │   ├── exceptions.py              # 커스텀 HTTP 예외
│   │   └── logger.py                  # 로거
│   ├── models/
│   │   ├── user.py                    # User, UserRole
│   │   ├── session.py                 # Session
│   │   └── message.py                 # Message, RoleEnum
│   ├── schemas/
│   │   ├── user.py                    # UserCreate, UserUpdate, UserResponse
│   │   ├── auth.py                    # LoginRequest, TokenResponse 등
│   │   ├── session.py                 # SessionCreate, SessionUpdate, SessionResponse
│   │   └── message.py                 # ChatRequest, MessageResponse
│   ├── services/
│   │   ├── user_service.py            # 유저 CRUD
│   │   ├── auth_service.py            # JWT 발급/검증, 로그인
│   │   ├── session_service.py         # 세션 CRUD
│   │   ├── message_service.py         # 메시지 저장, LLM 스트리밍 오케스트레이션
│   │   └── llm_client.py              # LLM 서버 HTTP 스트리밍 클라이언트
│   └── api/v1/routes/
│       ├── health.py                  # GET /health, /database
│       ├── auth.py                    # POST /auth/signup, /login, /refresh, /logout
│       ├── user.py                    # GET·PATCH·DELETE /users/{id}
│       ├── session.py                 # POST·GET·PATCH·DELETE /sessions
│       └── message.py                 # GET /sessions/{id}/messages, POST /sessions/{id}/messages/stream
├── alembic/                           # DB 마이그레이션
├── main.py                            # 서버 실행 진입점
├── .env                               # 환경변수 (git 제외)
└── requirements.txt
```

## API 엔드포인트

| Method | Path | 설명 | 인증 |
|--------|------|------|------|
| GET | `/api/v1/health` | 앱 상태 확인 | 불필요 |
| GET | `/api/v1/database` | DB 연결 확인 | 불필요 |
| POST | `/api/v1/auth/signup` | 회원가입 | 불필요 |
| POST | `/api/v1/auth/login` | 로그인 | 불필요 |
| POST | `/api/v1/auth/refresh` | 액세스 토큰 재발급 | 불필요 |
| POST | `/api/v1/auth/logout` | 로그아웃 | 불필요 |
| GET | `/api/v1/users/{id}` | 유저 조회 | 필요 |
| PATCH | `/api/v1/users/{id}` | 유저 수정 | 필요 |
| DELETE | `/api/v1/users/{id}` | 유저 삭제 | 필요 |
| POST | `/api/v1/sessions` | 세션 생성 | 필요 |
| GET | `/api/v1/sessions` | 세션 목록 | 필요 |
| PATCH | `/api/v1/sessions/{id}` | 세션 이름 변경 | 필요 |
| DELETE | `/api/v1/sessions/{id}` | 세션 삭제 | 필요 |
| GET | `/api/v1/sessions/{id}/messages` | 메시지 이력 조회 | 필요 |
| POST | `/api/v1/sessions/{id}/messages/stream` | LLM 스트리밍 채팅 | 필요 |

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
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## DB 마이그레이션

```bash
# 마이그레이션 적용
alembic upgrade head

# 모델 변경 후 마이그레이션 파일 생성 → 적용
alembic revision --autogenerate -m "변경 내용"
alembic upgrade head
```

> Enum 컬럼 추가 시 자동 생성된 마이그레이션 파일에 `create()`/`drop()`을 수동으로 추가해야 합니다.

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `LLM_SERVER_URL` | `http://localhost:8001` | LLM 서버 주소 |
| `REQUEST_TIMEOUT` | `60` | 연결 타임아웃 (초, read는 무제한) |
| `DATABASE_URL` | — | PostgreSQL 연결 문자열 (`postgresql+asyncpg://user:pw@host:5432/db`) |
| `JWT_SECRET_KEY` | — | JWT 서명 키 |
| `JWT_ALGORITHM` | `HS256` | JWT 알고리즘 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | 액세스 토큰 만료 시간 (분) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | 리프레시 토큰 만료 시간 (일) |
