---
name: verify
description: llm-backend 변경사항을 실제 서버를 띄워 API 레벨에서 검증하는 절차
---

# llm-backend 검증 절차

## 환경

- 프로젝트에 venv 없음. 전역 Python 3.11에도 의존성 없음 → 스크래치패드에 venv 생성 후 설치:
  `pip install "fastapi[standard]" "sqlalchemy[asyncio]" asyncpg "pydantic[email]" pydantic-settings httpx "python-jose[cryptography]" bcrypt alembic`
- DB: 로컬 PostgreSQL, 접속 정보는 `.env`의 `DATABASE_URL` (`postgresql+asyncpg://...@localhost:5432/llm_db`)
- 사용자가 자기 서버를 8080(main.py)에서 띄울 수 있으므로 검증용 서버는 **다른 포트**(예: 8123)로 실행:
  `python -m uvicorn app.main:app --host 127.0.0.1 --port 8123` (백그라운드)

## 검증 흐름

1. `python -m alembic upgrade head` 로 마이그레이션 적용 (`alembic current`로 head 확인)
2. `GET /api/v1/health` 로 db/llm_server 연결 확인
3. 인증이 필요한 API는: signup → **asyncpg로 직접 `UPDATE users SET status='approved'`** (관리자 승인 대체) → login으로 토큰 획득
4. httpx 드라이버 스크립트로 대상 엔드포인트 호출 + 에러 프로브(401/403/404/422)
5. asyncpg로 DB 상태 직접 조회해 영속화 확인

## 주의

- 테스트 유저 이메일은 식별 가능한 패턴(예: `fav-test-*@example.com`)으로 만들고, 끝나면
  `DELETE FROM users WHERE email LIKE '...%'` 로 정리 (sessions/messages는 FK CASCADE로 함께 삭제됨)
- **공유 DB**: 사용자가 동시에 자기 계정으로 테스트 중일 수 있음. 남의 데이터 건드리지 말 것
- PowerShell 콘솔은 cp949라 한국어 출력이 깨짐 → `[Console]::OutputEncoding = UTF8` + `python -X utf8`
- PowerShell 인라인 `python -c`에 따옴표 이스케이프가 잘 깨짐 → 스크립트 파일로 작성해 실행
