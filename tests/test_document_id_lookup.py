"""MARS 삭제 요청·채팅 출처가 문서명이 아닌 document_id를 쓰는지 확인하는 회귀 테스트."""

import unittest
from unittest.mock import patch
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.attachment import Attachment
from app.models.document import Document
from app.models.message import Message
from app.models.project import Project
from app.models.session import Session
from app.models.source import Source
from app.models.user import User
from app.schemas.message import SourceResponse
from app.services import document_service, message_service, project_service


class DocumentIdLookupTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    sync_connection,
                    tables=[
                        User.__table__, Project.__table__, Document.__table__,
                        Session.__table__, Message.__table__, Source.__table__,
                        Attachment.__table__,
                    ],
                )
            )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.user_id = UUID(int=100)
        self.project_id = UUID(int=200)
        self.session_id = UUID(int=300)
        async with self.sessions() as db:
            db.add(User(
                user_id=self.user_id, name="Tester", email="lookup@example.com", password="unused"
            ))
            await db.flush()
            db.add(Project(project_id=self.project_id, user_id=self.user_id, title="Private"))
            db.add(Session(session_id=self.session_id, user_id=self.user_id))
            await db.commit()

        self.requests = []
        self.delete_status = 200
        real_async_client = httpx.AsyncClient
        self.client_patch = patch(
            "app.services.document_service.httpx.AsyncClient",
            side_effect=lambda **kwargs: real_async_client(
                transport=httpx.MockTransport(self.handle), **kwargs
            ),
        )
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)

    def handle(self, request):
        self.requests.append(request)
        if request.method == "DELETE":
            if self.delete_status == 404:
                return httpx.Response(404, json={"detail": "not found"})
            return httpx.Response(200, json={"deleted_chunks": 7})
        return httpx.Response(202, json={"job_id": f"job-{len(self.requests)}", "status": "queued"})

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def add_document(self, db, name="휴가 규정.pdf", project=False):
        doc = Document(
            name=name, domain="HR", visibility="ALL", data=b"bytes", size=5,
            content_type="application/pdf", user_id=self.user_id,
            project_id=self.project_id if project else None,
            job_id="job-x", status="done",
        )
        db.add(doc)
        await db.commit()
        return doc

    def assert_delete_by_id(self, request, document_id):
        self.assertEqual(request.method, "DELETE")
        self.assertEqual(request.url.path, f"/documents/by-id/{document_id}")
        self.assertEqual(dict(request.url.params), {})

    async def test_admin_delete_requests_mars_by_document_id(self):
        async with self.sessions() as db:
            doc = await self.add_document(db)
            result = await document_service.delete_document_admin(db, doc.document_id)
        self.assertEqual(result.deleted_chunks, 7)
        self.assert_delete_by_id(self.requests[-1], doc.document_id)
        async with self.sessions() as db:
            self.assertIsNone(await db.get(Document, doc.document_id))

    async def test_same_name_documents_are_deleted_separately(self):
        async with self.sessions() as db:
            first = await self.add_document(db)
            second = await self.add_document(db)
            await document_service.delete_document_admin(db, first.document_id)
        self.assert_delete_by_id(self.requests[-1], first.document_id)
        async with self.sessions() as db:
            self.assertIsNone(await db.get(Document, first.document_id))
            self.assertIsNotNone(await db.get(Document, second.document_id))

    async def test_admin_delete_is_idempotent_when_mars_has_no_document(self):
        self.delete_status = 404
        async with self.sessions() as db:
            doc = await self.add_document(db)
            result = await document_service.delete_document_admin(db, doc.document_id)
        self.assertEqual(result.deleted_chunks, 0)
        async with self.sessions() as db:
            self.assertIsNone(await db.get(Document, doc.document_id))

    async def test_project_delete_requests_mars_by_document_id(self):
        async with self.sessions() as db:
            doc = await self.add_document(db, project=True)
            await project_service.delete_project_document(
                db, self.project_id, doc.document_id, self.user_id
            )
        self.assert_delete_by_id(self.requests[-1], doc.document_id)

    async def test_sources_store_document_id_and_tolerate_bad_values(self):
        document_id = UUID(int=999)
        async with self.sessions() as db:
            session = await db.get(Session, self.session_id)
            await message_service._save_ai_message(
                db, session, self.session_id, "answer",
                [
                    {"name": "a.pdf", "document_id": str(document_id), "page": "3"},
                    {"name": "b.pdf", "document_id": "not-a-uuid"},
                    {"name": "c.pdf"},
                ],
            )
        async with self.sessions() as db:
            rows = {s.name: s for s in await db.scalars(select(Source))}
        self.assertEqual(rows["a.pdf"].document_id, document_id)
        self.assertIsNone(rows["b.pdf"].document_id)
        self.assertIsNone(rows["c.pdf"].document_id)
        self.assertEqual(SourceResponse.model_validate(rows["a.pdf"]).document_id, document_id)
        self.assertIsNone(SourceResponse.model_validate(rows["c.pdf"]).document_id)


if __name__ == "__main__":
    unittest.main()
