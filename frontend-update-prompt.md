# 백엔드 API 변경사항 — 프론트엔드 수정 가이드

아래 내용을 바탕으로 이 프론트엔드 코드베이스에서 백엔드 API 변경사항을 반영해줘.
각 항목별로 관련 파일을 찾아서 수정하고, 없는 기능은 새로 구현해줘.

## 2. `GET /api/v1/sessions/{id}/messages` — 각 메시지에 `message_id` 추가

**변경 전:**
```json
{
  "role": "human",
  "content": "질문",
  "created_at": "...",
  "sources": []
}
```

**변경 후:**
```json
{
  "message_id": "2b771768-c406-4540-9b36-1a77c5dbeb13",
  "role": "human",
  "content": "질문",
  "created_at": "...",
  "sources": []
}
```

**할 일:**
- 메시지 타입/인터페이스에 `message_id: string` (UUID) 필드 추가
- 메시지 렌더링 시 `key`로 `message_id`를 사용하도록 변경 (기존에 index 사용 중이라면)
- 이후 3번, 4번 기능을 위해 각 메시지 컴포넌트에서 `message_id`를 prop으로 전달할 수 있도록 준비

---

## 3. `DELETE /api/v1/sessions/{session_id}/messages/{message_id}` — 메시지 삭제 API (신규)

**요청:**
```
DELETE /api/v1/sessions/{session_id}/messages/{message_id}
Authorization: Bearer {access_token}
```

**성공 응답 (200):**
```json
{ "success": true, "status_code": 200, "data": null, "error": null }
```

**에러 응답:**
- `404 MESSAGE_NOT_FOUND` — 존재하지 않는 메시지
- `403 SESSION_ACCESS_DENIED` — 다른 사용자의 세션
- `401 UNAUTHORIZED` — 인증 필요

**할 일:**
- 메시지 삭제 API 호출 함수 추가
- AI 메시지 또는 사용자 메시지에 삭제 버튼 UI 추가 (예: 메시지 hover 시 노출)
- 삭제 후 해당 메시지를 로컬 상태에서도 제거
- AI 메시지 삭제 시 `sources`(출처 정보)도 함께 삭제됨을 유의

---

## 4. `POST /api/v1/sessions/{session_id}/messages/{message_id}/regenerate` — AI 응답 재생성 (신규, SSE)

**요청:**
```
POST /api/v1/sessions/{session_id}/messages/{message_id}/regenerate
Authorization: Bearer {access_token}
```
- body 없음
- `message_id`는 반드시 `role: "ai"`인 메시지의 ID여야 함

**응답:** SSE(`text/event-stream`) — 기존 채팅 스트리밍과 동일한 이벤트 형식

```
data: 안녕          ← 텍스트 토큰 (문자열)

data: {"type": "sources", "items": [{"name": "doc.pdf", "page": "3"}]}

data: {"type": "done"}

data: {"type": "error", "message": "AI 메시지만 재생성할 수 있습니다."}
```

**동작 방식:**
1. 기존 AI 응답(message_id)이 서버에서 삭제됨
2. 동일한 사용자 질문으로 LLM에 재요청
3. 새 AI 응답이 SSE로 스트리밍되어 저장됨

**에러 케이스 (SSE error 이벤트로 반환):**
- 메시지를 찾을 수 없을 때: `{"type": "error", "message": "메시지를 찾을 수 없습니다."}`
- human 메시지 id를 전달했을 때: `{"type": "error", "message": "AI 메시지만 재생성할 수 있습니다."}`
- 세션 권한 오류: `{"type": "error", "message": "접근 권한이 없습니다."}`

**할 일:**
- 재생성 SSE 스트리밍 함수 추가 (기존 `chat_stream` 함수 참고하여 구현)
- AI 메시지에 "재생성" 버튼 UI 추가 (예: 메시지 hover 시 또는 메시지 하단 버튼)
- 재생성 시작 시: 기존 AI 메시지를 로딩 상태로 전환
- 스트리밍 수신 중: 새 텍스트로 점진적 교체
- `done` 이벤트: 완료 처리
- `error` 이벤트: 에러 메시지 표시 및 이전 메시지 복원 또는 빈 상태 처리

## 공통 사항

### 인증 헤더
모든 인증 필요 API에 `Authorization: Bearer {access_token}` 헤더 포함 필요.

### 공통 에러 응답 형식
```json
{
  "success": false,
  "status_code": 404,
  "data": null,
  "error": {
    "code": "MESSAGE_NOT_FOUND",
    "detail": "메시지를 찾을 수 없습니다."
  }
}
```

### 신규 에러 코드
| code | HTTP | 설명 |
|---|---|---|
| `MESSAGE_NOT_FOUND` | 404 | 메시지를 찾을 수 없음 |
| `INVALID_MESSAGE_ROLE` | 400 | AI 메시지가 아닌 메시지로 재생성 요청 (SSE error 이벤트로 반환) |
| `LLM_SERVER_ERROR` | 502 | LLM 서버 오류 (`GET /documents` 등) |
