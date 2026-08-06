# 폐쇄망 MySQL 전환 작업보고서

> **대상** PostgreSQL → MySQL 8.0 전환 + 폐쇄망(오프라인) 드라이버 반입 대응
> **브랜치** `demo_v1`
> **작업일** 2026-08-06
> **상태** ✅ **완료** — 마이그레이션 적용 및 실DB 왕복 검증까지 통과
>
> 📄 프로젝트 전반 설계는 [개발문서.md](./개발문서.md), 프로젝트 API 작업은 [작업보고서.md](./작업보고서.md) 참고.
> 이 문서는 `demo_v1` 브랜치의 DB 전환 작업만 다룬다.

---

## 1. 배경

폐쇄망 장비에는 PyPI 접근이 불가능하다. MySQL을 쓰기 위해 순수 파이썬 드라이버인
`aiomysql`과 `pymysql` 소스를 `vendor/` 폴더에 직접 반입했고, 이를 설치 없이
사용할 수 있도록 코드를 준비하는 것이 이번 작업의 출발점이었다.

작업을 진행하며 확인된 사실:

- 코드베이스는 PostgreSQL(`asyncpg`) 기준으로 작성되어 있었다.
- `.env`는 이미 MySQL을 가리키고 있었으나 드라이버가 `mysql+asyncmy`였고, **asyncmy는 어디에도 없었다.**
- 마이그레이션 리비전 중 2개가 PostgreSQL 전용이라 MySQL에서 실행 불가였다.

---

## 2. 우리가 한 것 (변경 파일)

| 파일 | 변경 내용 |
|---|---|
| `app/__init__.py` | **신규 로직.** `vendor/`를 `sys.path`에 등록하는 부트스트랩 |
| `.env` | `mysql+asyncmy://...` → `mysql+aiomysql://...?charset=utf8mb4` |
| `app/core/config.py` | `database_url` 기본값을 MySQL로 변경 |
| `app/core/database.py` | `UtcDateTime`/`Timestamp` 타입 추가, `pool_pre_ping`·`pool_recycle` 추가, `connect_args` 드라이버별 분기 |
| `app/models/user.py` | `DateTime(timezone=True)` → `Timestamp` (2곳) |
| `app/models/session.py` | `DateTime(timezone=True)` → `Timestamp` (2곳) |
| `app/models/message.py` | `Timestamp` 적용, `content`를 MySQL에서 `MEDIUMTEXT`로 |
| `app/models/source.py` | `Timestamp` 적용, `message_id`에 `index=True` 추가 (P-11) |
| `app/main.py` | lifespan 종료 시 `engine.dispose()` 추가 (P-10) |
| `alembic/versions/` | PostgreSQL 리비전 7개 **삭제**, MySQL 베이스라인 `b7c1e94f2a30` 1개 **신규** |
| `requirements.txt` | `asyncpg` 제거, vendor 드라이버 안내 주석 추가 |
| `README.md` | DB 생성 안내, 환경변수 표, MySQL 마이그레이션 주의사항 갱신 |

### 삭제된 리비전 (PostgreSQL 계보)

```
1412e37519c6 → e9f6ca3bfbb0 → 63880cc901da → 0119517cb86f
             → 5f69628aa33d → f6d6325672ec → 3c7d2e1f4a8b
```

### 현재 리비전

```
b7c1e94f2a30 (head)  create initial schema for mysql
```

`users`, `sessions`, `messages`, `sources` 4개 테이블을 한 번에 생성한다.

---

## 3. 결정 사항 (Decision Log)

### D-01. 드라이버는 `asyncmy`가 아니라 `aiomysql`

| 항목 | 내용 |
|---|---|
| **결정** | `mysql+aiomysql` 사용 |
| **이유** | 폐쇄망에 반입된 것이 `aiomysql`/`pymysql`이다. `asyncmy`는 **Cython 확장이라 컴파일이 필요**해 소스 반입만으로는 쓸 수 없다. `aiomysql`/`pymysql`은 순수 파이썬이라 경로만 잡으면 동작한다. |
| **영향** | `.env`, `config.py`. asyncmy 대비 성능은 다소 낮으나 폐쇄망 제약이 우선한다. |

### D-02. vendor 경로는 `app/__init__.py` 한 곳에서만 등록

| 항목 | 내용 |
|---|---|
| **결정** | `app/__init__.py`에서 `vendor/`를 `sys.path`에 **append** |
| **이유** | uvicorn(`app.main:app`), alembic(`app.core.config`), pytest 모두 `app` 패키지를 가장 먼저 import 한다. 진입점마다 중복으로 넣을 필요가 없다. `.pth` 파일이나 `sitecustomize.py`는 실행 위치·가상환경에 의존해 불안정하다. |
| **비고** | `insert(0)`이 아니라 `append` — 정상 설치된 패키지가 있으면 그쪽이 우선한다. `if _VENDOR_DIR.is_dir()` 가드가 있어 폴더가 없어도 import는 깨지지 않는다. |

### D-03. PostgreSQL 리비전 체인 폐기, MySQL 단일 베이스라인으로 재구성

| 항목 | 내용 |
|---|---|
| **결정** | 기존 7개 리비전을 삭제하고 `b7c1e94f2a30` 하나로 대체 |
| **이유** | 초기에는 방언 분기(`op.get_bind().dialect.name`)로 PG/MySQL 양쪽 호환을 유지하는 방식으로 구현했으나, PostgreSQL을 더 쓰지 않기로 한 이상 유지 비용만 남는다. 특히 `0119517cb86f`(Enum 값 변경)는 양쪽 코드가 완전히 달라 분기가 지저분해진다. |
| **대안** | ① 방언 분기 유지 ② PG 체인 위에 MySQL 전용 리비전을 얹기 |
| **영향** | **기존 PostgreSQL DB는 이 브랜치의 alembic으로 더 이상 관리할 수 없다.** demo_v1은 MySQL 신규 DB 전용이다. |

### D-04. 타임스탬프는 앱 레벨에서 UTC를 보존한다 (`UtcDateTime`)

| 항목 | 내용 |
|---|---|
| **결정** | `TypeDecorator`로 저장 시 UTC naive 정규화, 조회 시 UTC aware 복원. MySQL에서는 `DATETIME(fsp=6)` |
| **이유** | MySQL `DATETIME`은 타임존을 저장하지 않아 그냥 두면 조회 결과가 naive로 돌아오고 **API 응답에서 `+00:00`이 사라진다**(프론트 영향). 또 `fsp`를 지정하지 않으면 **마이크로초가 잘린다**. |
| **대안** | ① `TIMESTAMP` 컬럼 사용 (2038년 한계 + 서버 타임존 의존) ② 스키마 레벨에서 처리 |
| **영향** | DDL이 `DATETIME(6)`이 된다. PostgreSQL에서는 기존과 동일하게 `TIMESTAMP WITH TIME ZONE`. |

### D-05. `messages.content`는 MySQL에서 `MEDIUMTEXT`

| 항목 | 내용 |
|---|---|
| **결정** | `sa.Text().with_variant(mysql.MEDIUMTEXT(), 'mysql')` |
| **이유** | PostgreSQL `TEXT`는 길이 제한이 없지만 **MySQL `TEXT`는 64KB**다. 긴 LLM 답변이 조용히 잘릴 수 있다. `MEDIUMTEXT`는 16MB. |

### D-06. 삭제된 브랜치는 참고만, 머지하지 않는다

| 항목 | 내용 |
|---|---|
| **결정** | `origin/10-fix/postgresql-mysql-migration`의 **판단만 차용**하고 파일·리비전은 가져오지 않는다 |
| **이유** | 해당 브랜치는 `documents`/`attachments`/`projects` 등 demo_v1에 없는 테이블을 포함한 **별개 프로젝트 계보**다. 머지하면 스키마가 어긋난다. |
| **차용한 것** | `fsp=6`, `MEDIUMTEXT`/`LONGBLOB` variant, `sa.Uuid()` 사용, `UtcDateTime` 패턴 |
| **차용하지 않은 것** | 리비전 파일, 추가 테이블, `asyncmy` 드라이버 선택 |

### D-07. 마이그레이션 적용 (완료)

방향 확정 후 적용하기로 했고, 사용자가 `prototype_db`에 `alembic upgrade head`를 실행했다.
적용 결과는 5절 검증 참고.

---

## 4. 발생한 문제와 해결

### P-01. `.env`가 존재하지 않는 드라이버를 가리킴

- **증상** `DATABASE_URL=mysql+asyncmy://...` — asyncmy 미설치·미반입
- **원인** 다른 브랜치(`10-fix`)에서 asyncmy 기준으로 작성된 `.env`가 남아 있었다
- **해결** `mysql+aiomysql://...?charset=utf8mb4`로 교체. `charset=utf8mb4`도 함께 명시

### P-02. `sa.UUID()`가 MySQL에서 컴파일 실패

- **증상** `3c7d2e1f4a8b`(sources 테이블)에서 `sa.UUID()`가 MySQL에 **존재하지 않는 `UUID` 타입**으로 컴파일됨
- **원인** `sa.UUID()`는 네이티브 UUID 타입을 요구한다. `sa.Uuid()`는 백엔드에 없으면 `CHAR(32)`로 폴백한다
- **해결** `sa.Uuid()`로 변경 (이후 D-03으로 리비전 자체가 통합되며 베이스라인에 반영)
- **검증** MySQL 방언 컴파일 결과 `sa.Uuid() → CHAR(32)`, `sa.UUID() → UUID` 확인

### P-03. Enum 값 변경 리비전이 PostgreSQL 전용 DDL

- **증상** `0119517cb86f`가 `ALTER COLUMN ... TYPE ... USING`, `DROP TYPE`, `ALTER TYPE ... RENAME` 사용
- **원인** MySQL은 ENUM이 **독립 타입이 아니라 컬럼 타입**이라 `ALTER TYPE`이 없다
- **해결** 초기에는 방언 분기 + `ALTER TABLE ... MODIFY` 3단계(값 집합 확장 → `UPDATE` → 축소)로 구현했고, 최종적으로 D-03에 따라 리비전 통합으로 문제 자체가 사라졌다. **다만 이후 Enum 값을 바꿀 때 같은 문제가 다시 발생하므로 3단계 패턴을 README에 남겼다**

### P-04. `connect_args={"ssl": False}`가 asyncpg 전용

- **증상** `database.py`에 asyncpg 전용 인자가 하드코딩되어 있었고, `DB_DISABLE_SSL` 설정은 무시되고 있었다
- **해결** 드라이버가 `asyncpg`일 때만 적용하도록 분기. aiomysql은 `ssl` 인자를 주지 않으면 평문 연결이라 별도 처리가 필요 없다. 덤으로 `DB_DISABLE_SSL` 설정이 이제 실제로 동작한다

### P-05. 마이크로초 절삭 — 커서 페이지네이션 손상 위험 ⚠️

- **증상** 1차 구현한 `UTCDateTime`이 MySQL에서 `DATETIME`(fsp 0)으로 컴파일되어 **마이크로초가 잘렸다**
- **영향** `created_at`/`updated_at`은 [user_service.py](app/services/user_service.py)와 [session_service.py](app/services/session_service.py)의 **커서 페이지네이션 키**다. 초 단위로 뭉개지면 동시각 레코드에서 `WHERE created_at < cursor` 비교가 흔들려 **항목 누락·중복**이 발생한다. PostgreSQL `timestamptz`는 마이크로초를 보존했으므로 명백한 동작 회귀였다
- **원인** MySQL `DATETIME`의 기본 정밀도는 초 단위다. 마이크로초를 쓰려면 `DATETIME(6)`을 명시해야 한다
- **해결** `load_dialect_impl`에서 MySQL일 때 `mysql.DATETIME(fsp=6)` 반환
- **검증** KST `2026-08-06 21:00:00.123456` → bind 결과 `2026-08-06 12:00:00.123456`(naive UTC), 조회 시 UTC aware 복원 확인

### P-06. MySQL `TEXT`의 64KB 제한

- **증상/해결** D-05 참고

### P-07. `llm_db`가 다른 계보였음 ⚠️

- **증상** 로컬 MySQL의 `llm_db`에 `alembic_version = 'd1e2f3a4b5c6'`이 들어 있었는데, **이 브랜치에 없는 리비전**이었다. `attachments`, `documents`, `projects` 등 demo_v1에 없는 테이블도 있었다
- **원인** `llm_db`는 삭제된 `10-fix` 브랜치 계보로 마이그레이션된 DB다
- **영향** 만약 `llm_db`에 `alembic upgrade head`를 실행했다면 `Can't locate revision identified by 'd1e2f3a4b5c6'`로 실패했을 것이다
- **해결** demo_v1은 `.env`가 가리키는 **`prototype_db`만** 사용한다. `llm_db`는 건드리지 않았다

### P-08. `prototype_db` 접근 권한 누락

- **증상** 접속은 되는데 `SHOW DATABASES`에 `prototype_db`가 보이지 않음
- **해결** 사용자가 `GRANT ALL PRIVILEGES ON prototype_db.* TO 'rokmcllm'@'localhost'` 부여. 현재 정상

### P-09. 삭제한 브랜치가 계속 보임

- **증상** 원격에서 지운 `10-fix/postgresql-mysql-migration`이 `git branch -a`에 계속 표시됨
- **원인** 로컬의 **stale remote-tracking ref**. 실제 원격에는 없다(`git ls-remote`로 확인)
- **해결** `git fetch --prune` 또는 `git remote prune origin`

### P-10. 프로세스 종료 시 segfault 🔴

- **증상** DB 작업이 모두 끝난 뒤 **프로세스 종료 시점에 Segmentation fault (exit 139)**. 로직은 전부 정상 수행되고 출력도 다 나온 뒤에 크래시한다
- **재현/격리** 같은 코드에서 `await engine.dispose()`만 넣으면 `exit=0`, 빼면 `exit=139`로 100% 재현
- **원인** 커넥션 풀이 aiomysql 소켓을 쥔 채 이벤트 루프가 먼저 닫히고, 이후 **죽은 루프 위에서 소켓이 GC 되며** 크래시한다
- **영향** [app/main.py](app/main.py)의 `lifespan`이 시작 시 DB 연결만 확인하고 **종료 시 정리를 하지 않았다.** 그대로 두면 **uvicorn 종료 때마다 같은 크래시**가 난다
- **해결** `lifespan`의 `yield` 뒤에 `await engine.dispose()` 추가
- **검증** lifespan 시작→종료 전체 사이클 `exit=0` 확인

### P-11. 모델과 DB의 인덱스 불일치

- **증상** `alembic check` 실행 시 `Detected removed index 'ix_sources_message_id'` — autogenerate가 인덱스를 **지우려 한다**
- **원인** 마이그레이션은 `ix_sources_message_id`를 만드는데 `Source` 모델에는 `index=True` 선언이 없었다. **기존 PostgreSQL 리비전(`3c7d2e1f4a8b`) 때부터 있던 불일치**가 이번에 드러난 것이다
- **영향** 방치하면 다음 `--autogenerate` 실행 때 **인덱스를 삭제하는 마이그레이션이 자동 생성**된다
- **해결** `Source.message_id`에 `index=True` 추가 (기본 명명 규칙이 `ix_sources_message_id`라 이름도 그대로 일치)
- **검증** `alembic check` → `No new upgrade operations detected.`

---

## 5. 검증 결과

### 5.1 정적 검증

| 항목 | 방법 | 결과 |
|---|---|---|
| vendor import | `PYTHONPATH` 없이 `import app` 후 aiomysql/pymysql import | ✅ pymysql 1.2.0, aiomysql 로드 |
| 앱 기동 | `import app.main` | ✅ |
| 엔진 배선 | `engine.dialect` 확인 | ✅ `mysql+aiomysql`, pre_ping True, recycle 3600 |
| 마이그레이션 SQL | `alembic upgrade head --sql` | ✅ 유효한 MySQL DDL |
| 모델 ↔ 마이그레이션 일치 | 메타데이터 DDL과 마이그레이션 DDL 비교 | ✅ 완전 일치 |

### 5.2 실DB 검증 (`prototype_db`, MySQL 8.0.46)

**적용된 스키마** — 리비전 `b7c1e94f2a30`, 테이블 4개 + `alembic_version`

```sql
`user_id`    char(32)      -- sa.Uuid()
`role`       enum('user','admin')
`created_at` datetime(6)   -- fsp=6, 마이크로초 보존
`content`    mediumtext    -- 64KB 제한 회피
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

**ORM 왕복 검증** — 트랜잭션 내에서 실행 후 롤백, 데이터 잔여 없음 확인

| 검증 항목 | 결과 |
|---|---|
| UUID 왕복 (`CHAR(32)` ↔ `uuid.UUID`) | ✅ |
| 한글 보존 (utf8mb4) | ✅ |
| Enum 왕복 (`UserRole`, `RoleEnum`) | ✅ |
| tz-aware datetime 반환 | ✅ |
| **마이크로초 보존** (P-05 회귀 방지) | ✅ |
| **MEDIUMTEXT 무손실** — 120,000자(약 360KB) 저장/조회 | ✅ |
| 커서 페이지네이션 비교 (`created_at < cursor`) | ✅ |
| 스키마 드리프트 (`alembic check`) | ✅ `No new upgrade operations detected.` |
| 앱 lifespan 시작→종료 사이클 | ✅ `exit=0` (P-10 수정 후) |

### 검증하지 못한 것

- **폐쇄망 장비에서의 동작** — 현재 개발 장비 기준 검증만 수행
- **HTTP 레벨 E2E** (회원가입 → 로그인 → 세션 → 메시지) — ORM 레벨까지만 검증
- **부하/장시간 운용** — `pool_recycle` 동작, 커넥션 끊김 복구는 미검증

---

## 6. 앞으로 발생 가능한 문제

### R-01. `vendor/` 미반입 시 런타임 실패 🔴

`vendor/`는 git에 커밋되지 않았다. 폐쇄망 장비로 옮길 때 **프로젝트 루트 바로 아래(`llm-backend/vendor/`)** 에 함께 넣어야 한다.
누락 시 import는 통과하고 **DB 연결 시점에** `ModuleNotFoundError: aiomysql`로 드러난다.

### R-02. 새 컬럼 추가 시 `fsp` 누락 🟠

새 타임스탬프 컬럼을 만들 때 모델은 `Timestamp`, 마이그레이션은
`sa.DateTime(timezone=True).with_variant(mysql.DATETIME(fsp=6), 'mysql')`를 써야 한다.
`sa.DateTime()`을 그냥 쓰면 P-05가 재발하는데, **에러 없이 조용히 마이크로초만 잘린다**. 가장 놓치기 쉽다.

### R-03. Enum 값 변경 시 3단계 필요 🟠

MySQL은 `ALTER TYPE`이 없다. 값 집합 변경은 `ALTER TABLE ... MODIFY`로 넓히고 → `UPDATE` → 다시 좁히는 3단계다. autogenerate가 만들어주지 않으므로 수동 작성해야 한다.

### R-04. 스키마 드리프트 재발 🟡

`alembic check`로 확인한 결과 현재는 깨끗하다(`with_variant`도 문제 없음). 다만 P-11처럼
**마이그레이션에만 있고 모델에는 없는 요소**(인덱스·제약)가 생기면 다음 autogenerate가
그것을 **삭제하는** 마이그레이션을 만들어낸다. 마이그레이션 생성 후 `alembic check`를
습관적으로 돌릴 것.

### R-05. `ilike` 검색이 인덱스를 타지 못함 🟡

[user_service.py](app/services/user_service.py)의 사용자 검색은 `ilike`를 쓰는데, MySQL에서
`lower(users.name) LIKE lower(%s)`로 컴파일된다. 컬럼에 함수가 걸려 **인덱스를 못 탄다**.
게다가 앞뒤 와일드카드(`%검색어%`)라 어차피 풀스캔이다. 사용자 수가 늘면 느려진다.
MySQL 기본 collation이 대소문자 구분을 안 하므로 `like`로 바꿔도 결과는 같다.

### R-06. UUID PK의 InnoDB 단편화 🟡

`CHAR(32)` 랜덤 UUID를 클러스터형 기본키로 쓰면 삽입 위치가 흩어져 페이지 분할이 잦다.
PostgreSQL 때보다 체감이 클 수 있다. 데이터가 커지면 UUIDv7이나 `BINARY(16)` 전환을 검토한다.

### R-07. collation 통일 유지 🟡

`llm_db`, `prototype_db` 모두 `utf8mb4` / `utf8mb4_unicode_ci`이고, README의 DB 생성
안내도 여기에 맞춰두었다. **다른 collation으로 만든 테이블과 JOIN하면 충돌이 난다.**
앞으로 DB나 테이블을 새로 만들 때 `utf8mb4_unicode_ci`를 유지할 것.

### R-08. tz-aware datetime을 raw 쿼리로 넘길 때 🟡

`pymysql`의 `escape_datetime`은 **tzinfo를 조용히 버리고 wall clock만 저장**한다.
`Timestamp` 타입을 거치면 UTC로 정규화되어 안전하지만, `text()` 등 raw SQL로 aware datetime을
직접 넘기면 로컬시각이 UTC인 것처럼 저장될 수 있다.

### R-09. `llm_db` 오조작 🟠

`llm_db`는 다른 계보다(P-07). `.env`를 임시로 바꿔 실행하는 일이 없도록 주의한다.

---

## 7. 남은 작업

| # | 작업 | 상태 |
|---|---|---|
| 1 | `prototype_db`에 `alembic upgrade head` 실행 | ✅ 완료 |
| 2 | ORM 왕복 검증 (UUID/한글/Enum/시각/MEDIUMTEXT) | ✅ 완료 |
| 3 | 스키마 드리프트 확인 (`alembic check`) | ✅ 완료 |
| 4 | 종료 시 커넥션 풀 정리 (P-10) | ✅ 완료 |
| 5 | `vendor/` git 커밋 여부 결정 | ⚠️ **미정** |
| 6 | `git fetch --prune`으로 stale ref 정리 (P-09) | 📌 |
| 7 | HTTP 레벨 E2E (회원가입 → 로그인 → 세션 → 메시지) | 📌 |
| 8 | 폐쇄망 장비 실환경 검증 | 📌 |

---

## 8. 참고: 폐쇄망 반입 체크리스트

- `aiomysql`, `pymysql` → **`vendor/`로 반입 완료**
- `alembic`, `bcrypt`, `python-jose`, `SQLAlchemy`, `greenlet` 등 → [requirements_back_ai.txt](./requirements_back_ai.txt)에 포함, 별도 조치 불필요
- `asyncpg` → 더 이상 사용하지 않음 (requirements_back_ai.txt에는 남아 있으나 무해)
