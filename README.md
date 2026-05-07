# llm-backend

FastAPI 기반 LLM 미들웨어 서버입니다. 사용자의 요청을 받아 LLM 서버로 전달하고, 응답을 다시 사용자에게 반환합니다.

## 아키텍처

```
사용자 → FastAPI Backend (이 서버) → LLM Server (POST /api/rag/chat)
```

## 디렉토리 구조

```
llm-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 앱 진입점, 라우터 등록
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py              # 환경변수 설정 (pydantic-settings)
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── chat.py                # 요청/응답 Pydantic 스키마
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_client.py          # LLM 서버 HTTP 통신 (httpx I/O 전용)
│   │   └── chat_service.py        # 채팅 비즈니스 로직 (전처리/후처리)
│   │
│   └── api/
│       ├── __init__.py
│       └── v1/
│           ├── __init__.py
│           └── routes/
│               ├── __init__.py
│               └── chat.py        # POST /chat, POST /chat/stream 엔드포인트
│
├── tests/
│   └── __init__.py
│
├── .env.example                   # 환경변수 템플릿
├── requirements.txt               # 의존성 패키지
└── README.md
```

## 레이어 설명

| 레이어 | 파일 | 역할 |
|--------|------|------|
| Router | `api/v1/routes/chat.py` | HTTP 요청 수신, 응답 반환 |
| Service | `services/chat_service.py` | 비즈니스 로직, 전처리/후처리 |
| Client | `services/llm_client.py` | LLM 서버와 HTTP 통신 (httpx) |
| Schema | `schemas/chat.py` | 요청/응답 데이터 검증 |
| Config | `core/config.py` | 환경변수 관리 |

## LLM 서버 엔드포인트

| 방식 | 엔드포인트 |
|------|-----------|
| 기본 응답 | `POST /api/rag/chat` |
| SSE 스트리밍 | `POST /api/rag/chat/stream` |

## 시작하기

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env

# 서버 실행
uvicorn app.main:app --reload
python app/main.py
```

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `LLM_SERVER_URL` | `http://localhost:8001` | LLM 서버 주소 |
| `REQUEST_TIMEOUT` | `60` | HTTP 요청 타임아웃 (초) |
