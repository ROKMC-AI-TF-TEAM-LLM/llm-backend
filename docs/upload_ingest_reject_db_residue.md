# 문서 업로드 거부(400/413) 시 DB 잔여 행 문제

> 상태: **분석 완료, 미수정**
> 계열: 적재 상태 결함(my_docs/ingest_state_defects.md D 시리즈)과 같은 부류.
> 해당 문서가 git 추적 대상이 아니라 여기에 따로 남긴다. ID는 합류 시 부여할 것.

## 1. 증상

문서 업로드 시 MARS가 **400(지원하지 않는 형식·파라미터 오류)** 을 반환해 사용자에게
400이 나가는데도, `documents` 테이블에는 행이 원본 바이너리(LONGBLOB)까지 그대로 남는다.
413(용량 초과), 502(연결 실패)도 같은 경로를 탄다.

## 2. 근본 원인

### 2-1. `submit_ingest`가 실패를 커밋한다

`app/services/document_service.py:91-105`

```python
except Exception as e:
    doc.status = "error"
    doc.error = str(e)
    doc.job_id = None
    await db.commit()   # ← 실패 상태가 여기서 확정 저장된다
    raise
```

`except Exception`이 400/413/502를 구분하지 않는다. 이미 커밋했기 때문에 호출자가
rollback 해도 되돌아가지 않는다.

### 2-2. 두 업로드 경로 모두 "DB 먼저 → MARS 나중" 순서

| 경로 | 위치 |
|---|---|
| 관리자 업로드 | `app/services/document_service.py:249-263` (`upload_document`) — 라우트 `app/api/v1/routes/admin.py:141-157` |
| 프로젝트 참고파일 | `app/services/project_service.py:196-210` (`upload_project_document`) — 라우트 `app/api/v1/routes/project.py:243-259` |

둘 다 `db.add(doc)` → `commit()` → `submit_ingest(...)` 순서다.
삭제 경로(`delete_project`, `delete_project_document`, `delete_document_admin`)는 반대로
"MARS 먼저 → DB 나중"(ADR-17)을 지키고 있어, **업로드만 규칙이 어긋나 있다.**

### 2-3. 관리자 경로에 용량 사전 검증이 없다

`project_service.py:186-194`에는 `settings.max_document_size_mb` 사전 검증이 있으나
`document_service.upload_document`에는 없다. 50MB 초과 파일도 일단 DB에 통째로 저장된 뒤
MARS가 413을 준다.

## 3. 파급

1. **유령 행 노출** — `get_admin_documents`, `get_project_documents`가 `status="error"` 행을
   그대로 보여준다. 사용자는 400을 받았는데 목록에는 파일이 있다.
2. **다운로드 오염** — `get_document_file`(`document_service.py:376-390`)은 같은 `name` 중
   **가장 최근 등록본**을 반환한다. 정상 문서 업로드 후 같은 이름으로 지원하지 않는 형식을
   올려 400이 나면, 그 실패 행이 최신본이 되어 다운로드가 깨진 파일을 반환한다.
   (`name`에 unique 제약이 없다)
3. **무의미한 재시도** — `RETRYABLE_STATUSES`(`document_service.py:73`)가 실패 **사유**를
   구분하지 않고 `status == "error"`면 전부 재시도를 연다. 400으로 죽은 행도 재시도 대상이
   되지만 같은 파일이라 영원히 400이다.
4. **DB 용량** — 거부된 파일의 원본 바이트가 LONGBLOB으로 계속 남는다. 프로젝트 업로드는
   로그인만 하면 누구나 부를 수 있는 경로라 DB를 채우는 수단이 된다.

## 4. 수정 방침

판단 기준은 "재시도 가능성"이 아니라 **"MARS가 접수했을 가능성(청크가 남았을 수 있는가)"** 이다.

| 실패 | MARS 상태 | 처리 |
|---|---|---|
| 400 (형식/파라미터) | 접수 전 거부, 청크 없음 | **DB에 쓰지 않는다** |
| 413 (용량) | 접수 전 거부, 청크 없음 | **DB에 쓰지 않는다** |
| 502 / 타임아웃 / 연결 실패 | **접수됐을 수도 있음** (202 후 응답만 끊긴 경우) | `status="error"`로 행 유지 |

502에서 행을 남기는 이유는 재시도 편의만이 아니다. MARS가 접수한 뒤 응답이 끊기면
청크는 생겼는데 우리 쪽에 원본도 기록도 없는 고아 상태가 되고, 삭제 경로가 `job_id`로
청크 존재를 판단하므로 정리할 방법도 사라진다 (`submit_ingest` docstring ⚠ 항목 참조).

### 구현 형태

업로드 경로만 **`relay` 먼저 → 결과를 보고 INSERT** 로 뒤집는다.
지금 구조에 4xx 처리를 얹으면 "안 쓰는" 것이 아니라 **썼다가 지우는 보상 삭제**가 되어
50MB LONGBLOB을 한 번 쓰고 지우게 된다.

- relay 성공 → `job_id`/`status`를 채워 **한 번에 INSERT** (현재는 INSERT 후 UPDATE로 두 번 쓴다)
- relay 4xx → **DB 무접근**, 400/413 그대로 응답
- relay 5xx·네트워크 → `status="error"`로 INSERT 후 raise (재시도용 원본 보존)

## 5. 수정 대상 체크리스트

- [ ] `app/services/document_service.py` — 업로드용 경로와 재시도용 `submit_ingest` 분리
- [ ] `app/services/document_service.py:249-263` `upload_document` — relay 선행으로 전환
- [ ] `app/services/project_service.py:196-210` `upload_project_document` — 동일 전환
- [ ] `app/services/document_service.py` `upload_document` — 용량 사전 검증 추가
      (`project_service.py:186-194`와 동일 규칙, DB 쓰기 전에 413)
- [ ] `app/api/v1/routes/admin.py` 업로드 라우트 — `R_400_DOCUMENT`, `R_413_DOCUMENT` 응답 명세 추가
      (현재 `R_401`/`R_403_ADMIN`/`R_422`/`R_502_LLM`만 있어 400·413이 문서화돼 있지 않다)

## 6. 손대면 안 되는 것

- **`retry_ingest` 경로.** 이미 존재하는 행을 재사용하므로 기존 `submit_ingest`(실패 시
  `status="error"` 기록)를 그대로 써야 한다. 재시도 중 400이 나서 행이 사라지면
  사용자가 재업로드할 원본을 잃는다.
- **`get_document_status`의 job 404 처리.** 별개 사안(D6)이다.

## 7. 검증 관점

- 지원하지 않는 형식 업로드 → 400 응답 + `documents` 행 0건 (관리자/프로젝트 양쪽)
- 50MB 초과 업로드 → 413 응답 + 행 0건 + relay 호출 자체가 없어야 함(관리자 경로)
- MARS 다운 상태에서 업로드 → 502 응답 + `status="error"` 행 **존재** + 재시도 가능
- 같은 이름으로 정상 업로드 후 400 업로드 → `GET /documents/{name}/download`가
  여전히 정상 파일을 반환
