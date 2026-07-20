import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.core.exceptions import AttachmentNotFoundError
from app.models.attachment import Attachment
from app.models.message import Message
from app.models.session import Session


async def get_attachment(
    db: AsyncSession, attachment_id: uuid.UUID, user_id: uuid.UUID
) -> Attachment:
    # 타인의 파일은 존재 여부를 드러내지 않도록 소유자 조건을 조회에 포함해 404로 처리한다
    attachment = await db.scalar(
        select(Attachment)
        .join(Message, Message.message_id == Attachment.message_id)
        .join(Session, Session.session_id == Message.session_id)
        .where(Attachment.attachment_id == attachment_id, Session.user_id == user_id)
        .options(undefer(Attachment.data))
    )
    if not attachment:
        raise AttachmentNotFoundError()
    return attachment
