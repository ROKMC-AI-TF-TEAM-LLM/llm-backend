"""프로젝트 워크스페이스 서비스 (1~11번).

프로젝트 자체(생성·조회·수정·삭제)와 프로젝트 참고 파일(업로드·목록·삭제)을
한 모듈에서 다룬다. 참고 파일은 프로젝트에 종속된 하위 리소스이고, 모든 경로가
같은 소유권 관문(`_get_project_owned`)을 지나므로 분리하면 관문만 모듈 밖으로
새어 나간다.

MARS 호출은 직접 하지 않고 전부 `document_service`를 거친다 — 적재/삭제 계약이
바뀔 때 고칠 곳을 한 모듈로 묶어두기 위해서다.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DocumentNotFoundError,
    ProjectAccessDeniedError,
    ProjectNotFoundError,
)
from app.core.logger import get_logger
from app.models.document import Document, VisibilityEnum
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectInstructionUpdate, ProjectUpdate
from app.services import document_service

logger = get_logger(__name__)

# [정렬 규칙] 프로젝트 목록은 updated_at desc(최근 수정순)로 정렬된다.
#   - 제목 변경  → updated_at 갱신    (목록 맨 위로 올라간다)
#   - 즐겨찾기   → 갱신하지 않음      (해제 시 원래 자리로 돌아가야 하므로)
#   - 지침 수정  → 갱신하지 않음      (수정으로 간주하지 않는다)
# 정렬에 영향을 주지 않아야 하는 UPDATE는 SET 절에 updated_at=Project.updated_at 을
# 반드시 명시할 것. ORM 속성 대입 후 commit 하면 모델의 onupdate가 무조건 발동한다.


# ══════════════════════════════════════════════════════════════════════
# 프로젝트 (1~8번)
# ══════════════════════════════════════════════════════════════════════


async def create_project(db: AsyncSession, user_id: uuid.UUID, data: ProjectCreate) -> Project:
    project = Project(
        user_id=user_id,
        title=data.title,
        # 프론트가 지침 칸을 비워 보내면 ""로 오므로 NULL로 정규화한다
        instructions=data.instructions or None,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def get_projects(
    db: AsyncSession,
    user_id: uuid.UUID,
    cursor: datetime | None = None,
    size: int = 20,
    is_favorite: bool | None = None,
) -> tuple[list[Project], bool]:
    query = (
        select(Project)
        .where(Project.user_id == user_id)
        .order_by(Project.updated_at.desc())
        .limit(size + 1)
    )
    if cursor:
        query = query.where(Project.updated_at < cursor)
    if is_favorite is not None:
        query = query.where(Project.is_favorite == is_favorite)

    result = await db.scalars(query)
    projects = list(result.all())
    has_next = len(projects) > size
    return projects[:size], has_next


async def _get_project_owned(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> Project:
    project = await db.scalar(select(Project).where(Project.project_id == project_id))
    if not project:
        raise ProjectNotFoundError()
    if project.user_id != user_id:
        raise ProjectAccessDeniedError()
    return project


async def get_project(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> Project:
    return await _get_project_owned(db, project_id, user_id)


async def update_project(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, data: ProjectUpdate
) -> Project:
    project = await _get_project_owned(db, project_id, user_id)
    project.title = data.title
    await db.commit()
    await db.refresh(project)
    return project


async def set_favorite(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, is_favorite: bool
) -> Project:
    project = await _get_project_owned(db, project_id, user_id)
    # updated_at을 SET에 그대로 명시해 onupdate 갱신을 막는다
    # (즐겨찾기 변경이 최근 수정순 목록의 순서를 바꾸지 않도록)
    await db.execute(
        update(Project)
        .where(Project.project_id == project_id)
        .values(is_favorite=is_favorite, updated_at=Project.updated_at)
    )
    await db.commit()
    await db.refresh(project)
    return project


async def update_instructions(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, data: ProjectInstructionUpdate
) -> Project:
    project = await _get_project_owned(db, project_id, user_id)
    # 지침 수정은 '수정'으로 보지 않는다 — updated_at을 SET에 그대로 명시해 onupdate 갱신을 막는다
    # 빈 문자열은 생성 시와 동일하게 NULL로 정규화한다 (지침 삭제)
    await db.execute(
        update(Project)
        .where(Project.project_id == project_id)
        .values(instructions=data.instructions or None, updated_at=Project.updated_at)
    )
    await db.commit()
    await db.refresh(project)
    return project



# ══════════════════════════════════════════════════════════════════════
# 프로젝트 참고 파일 (9~11번)
# ══════════════════════════════════════════════════════════════════════


async def upload_project_document(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    content_type: str,
    data: bytes,
) -> Document:
    """프로젝트에 참고 파일을 업로드한다 (9번).

    형식·용량 검증은 MARS가 한다 — 여기서 같은 규칙을 다시 구현하면 두 곳이
    어긋난다. MARS가 400/413을 주면 그 문구를 사용자에게 그대로 전달한다.

    `domain`/`visibility`는 사용자가 정하지 않는다. 프로젝트 파일은 주제 분류가
    없고(GENERAL) 부서 ACL도 쓰지 않으므로(ALL), 검색 범위는 `project_id`가
    단독으로 결정한다.
    """
    await _get_project_owned(db, project_id, user_id)

    doc = Document(
        name=filename,
        user_id=user_id,
        project_id=project_id,
        domain="GENERAL",
        visibility=VisibilityEnum.ALL,
        content_type=content_type or "application/octet-stream",
        size=len(data),
        data=data,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    try:
        relay = await document_service.relay_document(
            name=doc.name,
            domain=doc.domain,
            visibility=doc.visibility.value,
            data=data,
            project_id=str(project_id),
        )
    except Exception as e:
        # 관리자 업로드와 같은 처리 — 실패 기록을 남겨 목록에서 원인을 볼 수 있게 한다
        doc.status = "error"
        doc.error = str(e)
        await db.commit()
        raise

    doc.job_id = relay["job_id"]
    doc.status = relay.get("status", "queued")
    await db.commit()
    await db.refresh(doc)
    return doc


async def get_project_documents(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Document], int, bool]:
    """프로젝트 참고 파일 목록 (10번). 최근 업로드순.

    우리 DB만 읽는다. 색인 진행 상태 갱신은 `get_project_document_status`가 맡는다
    — 목록에 얹으면 갱신 대상이 현재 페이지로 한정되고, GET이 외부 호출과 DB 쓰기를
    하게 된다. MARS의 `GET /documents`는 벡터스토어 전체 스캔 집계라 여기 쓸 수 없다.
    """
    await _get_project_owned(db, project_id, user_id)

    # 소유권을 이미 확인했지만, 데이터가 어긋난 경우 남의 파일이 보이는 대신
    # 안 보이는 쪽으로 실패하도록 쿼리에도 project_id 조건을 둔다
    scope = Document.project_id == project_id

    total = await db.scalar(select(func.count()).select_from(Document).where(scope))
    result = await db.scalars(
        select(Document)
        .where(scope)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    documents = list(result.all())
    has_more = offset + len(documents) < total
    return documents, total or 0, has_more


async def get_project_document_status(
    db: AsyncSession,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Document:
    """참고 파일의 색인 진행 상태를 조회한다.

    AI 서버의 job 이력은 in-memory라 재시작하면 사라진다. MARS 문서가 권하는 대로
    **미들웨어가 job_id·상태를 자기 DB에 mirroring**하며, 그 갱신이 여기서 일어난다.
    관리자 문서와 같은 함수를 쓴다 — mirroring 규칙이 두 벌이 되면 정책이 갈린다.

    이미 끝난 파일(job_id 없음 또는 done/error)은 외부 호출 없이 DB 값을 돌려준다.
    """
    await _get_project_owned(db, project_id, user_id)

    doc = await db.scalar(
        select(Document).where(
            Document.document_id == document_id,
            Document.project_id == project_id,
        )
    )
    if doc is None:
        raise DocumentNotFoundError()

    if doc.status not in ("pending", "queued", "running"):
        return doc
    return await document_service.get_document_status(db, doc.document_id)


async def delete_project_document(
    db: AsyncSession,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """프로젝트 참고 파일 삭제 (11번). MARS 먼저 → DB 나중.

    반대 순서로 하면 DB 원본이 사라진 뒤 MARS 호출이 실패했을 때 청크만 남아
    검색에 계속 잡히고 복구할 원본도 없다. 실패 시 동작은 `delete_project` 참조.
    """
    await _get_project_owned(db, project_id, user_id)

    # 문서 조회에 project_id를 함께 건다 — 다른 프로젝트의 document_id를 넣어도
    # 존재 여부가 드러나지 않고 404로 끝난다
    doc = await db.scalar(
        select(Document).where(
            Document.document_id == document_id,
            Document.project_id == project_id,
        )
    )
    if doc is None:
        raise DocumentNotFoundError() 
    """Claude는 여기를 참고한다. 모종의 이유로 색인이 안된상태일 수 있는데, 그럴 경우, 사용자가 보는 화면에서 색인 안됨을 인지하고 재시도 or 미적재 결정을 할수 있게 설계 할 것이다. 따라서, 색인이 안된경우에도 삭제와 재시도가 되게끔 로직이 짜져야한다."""

    # 적재를 요청한 적 있는 문서만 MARS를 건드린다 (실패해 job_id가 없으면 청크도 없다)
    if doc.job_id is not None:
        await document_service.delete_document(doc.name)

    await db.delete(doc)
    await db.commit()
