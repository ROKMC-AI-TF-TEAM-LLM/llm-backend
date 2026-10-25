# ---- builder: 의존성 설치 ----
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements-release-prototype.txt .
RUN pip install -r requirements-release-prototype.txt

# ---- runtime: 실행 이미지 ----
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8080

RUN useradd --create-home app
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

USER app
EXPOSE 8080

# Cloud Run이 넣어주는 PORT 환경변수를 사용
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips="*"
