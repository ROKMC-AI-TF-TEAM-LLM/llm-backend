# 채팅 SSE 하트비트 추가

## 완료 내용

- 작업 브랜치: `feat/Heartbeat`
- 채팅 스트리밍이 2분 넘게 조용하면 연결이 끊기는 문제를 막기 위해, 이벤트가 없는 동안 15초마다 하트비트를 보내도록 했다.
- 커밋·푸시는 하지 않았다. 프론트 코드는 변경하지 않았다.

## 원인

프론트 요청은 `브라우저 → Vercel(rewrite 프록시) → Cloud Run 백엔드` 경로로 간다. Vercel은 외부 주소로 보내는 rewrite 요청에 120초 제한을 둔다. 첫 바이트를 120초 안에 받아야 하고, 이후에도 120초마다 데이터가 와야 한다. 설정으로 늘릴 수 없다. AI 서버가 검색·생성 중에 2분 넘게 이벤트를 보내지 않으면 답변 전에 연결이 끊긴다.

## 동작

이벤트가 `sse_heartbeat_interval`(기본 15초) 동안 없으면 SSE 주석 라인을 보낸다.

```
data: {"type": "status", ...}

: ping

: ping

data: {"type": "text", ...}
```

`:`로 시작하는 줄은 SSE 표준상 주석이라 클라이언트가 이벤트로 처리하지 않는다. 프론트(`src/api/services/chat.ts`)도 `data:`로 시작하지 않는 줄을 건너뛰므로 수정이 필요 없다. 이벤트가 계속 오는 동안에는 하트비트를 보내지 않으며, 기존 이벤트의 종류·순서·내용은 그대로다.

## 변경 위치

- `app/core/sse.py` (신규): `with_heartbeat(stream, interval)`
  - 원래 스트림은 별도 task(producer)에서 끝까지 돌리고 queue로 넘긴다. 메인 루프는 queue를 interval초 동안 기다리다가 아무것도 없으면 하트비트를 보낸다. `wait_for(anext())`로 기다리면 timeout 때 원래 스트림이 취소되기 때문에 이렇게 나눴다.
  - queue 꺼내기 task(getter)는 timeout이 나도 취소하지 않고 유지한다. Python 3.11의 `wait_for`는 timeout과 아이템 도착이 겹치면 아이템을 잃어버릴 수 있다.
  - 클라이언트가 끊으면 producer에 취소를 전파해서 원래 스트림의 정리 코드(AI 서버 연결·DB 세션)가 실행되게 한다.
- `app/core/config.py`: `sse_heartbeat_interval: int = 15` 추가. `.env`의 `SSE_HEARTBEAT_INTERVAL`로 바꿀 수 있다.
- `app/api/v1/routes/message.py`: `POST /sessions/{id}/messages/stream`과 `POST /sessions/{id}/messages/{id}/regenerate`의 스트림을 `with_heartbeat`로 감쌌다. Swagger 설명에 하트비트 안내를 추가했다. `message_service`는 변경하지 않았다.

## 검증 결과

- **래퍼 단위 테스트 5개 통과**: 하트비트 삽입과 순서 유지, 바쁠 때 미전송, 예외 전파, 클라이언트 연결 끊김 시 원래 스트림 정리 및 남는 task 없음, `aclose` 정리
- **API 레벨 확인**: 실제 uvicorn에 앱을 띄우고, 인증·DB 의존성과 `message_service` 스트림만 7초 동안 조용한 가짜로 바꿨다. 간격은 2초로 줄였다.
  - 두 엔드포인트 모두 `200 text/event-stream`을 반환했다.
  - 조용한 구간에 `: ping`이 2초 간격으로 3회 온 뒤 `text → sources → done`이 정상 수신됐다.
  - 첫 ping 직후 연결을 끊어도 원래 스트림의 `finally`가 실행됐고 서버 로그에 오류가 없었다.
- **기존 테스트 18개 통과** (`pytest tests`)

실제 MySQL·AI 서버를 거치는 전체 흐름과 Vercel → Cloud Run 배포 경로는 검증하지 않았다.

## 특이사항과 주의점

1. **Cloud Run 요청 timeout은 막지 못한다.** Cloud Run은 요청 하나의 전체 시간으로 끊는다(기본 300초). 하트비트는 Vercel의 무응답 제한만 해결하므로, 응답이 5분을 넘을 수 있다면 배포 설정의 `--timeout`을 확인해야 한다.
2. **번역(`POST /translate`)은 적용 대상이 아니다.** 일반 JSON 응답이라 하트비트를 넣을 수 없다. 번역이 120초를 넘으면 Vercel에서 끊기므로 job_id + 폴링 방식이나 SSE 전환이 필요하다. 이번 범위에서는 제외했다.
3. **Swagger 설명의 "15초"는 글자로 적혀 있다.** `SSE_HEARTBEAT_INTERVAL`을 바꾸면 설명 문구도 함께 고쳐야 한다.
4. **테스트 의존성 `aiosqlite`가 `requirements.txt`에 없다.** 새 환경에서는 기존 테스트가 `ModuleNotFoundError`로 실패하므로 별도 설치가 필요하다.
5. 배포 후 AI 답변이 2분 넘게 걸리는 질문으로 끊기지 않는지 실제 확인이 필요하다.
