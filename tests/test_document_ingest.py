"""문서 UUID 전달 회귀 테스트. 실제 DB 대신 테스트용 aiosqlite를 사용한다."""

import unittest
from unittest.mock import patch
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.exceptions import BadRequestError
from app.models.document import Document
from app.models.project import Project
from app.models.user import User
from app.services import document_service, project_service


class DocumentIngestTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    sync_connection,
                    tables=[User.__table__, Project.__table__, Document.__table__],
                )
            )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.user_id = UUID(int=100)
        self.project_id = UUID(int=200)
        self.data = b"original document bytes"
        async with self.sessions() as db:
            db.add(User(
                user_id=self.user_id, name="Tester", email="ingest@example.com", password="unused"
            ))
            await db.flush()
            db.add(Project(project_id=self.project_id, user_id=self.user_id, title="Private"))
            await db.commit()

        self.requests = []
        self.response_status = 202
        real_async_client = httpx.AsyncClient
        self.client_patch = patch(
            "app.services.document_service.httpx.AsyncClient",
            side_effect=lambda **kwargs: real_async_client(
                transport=httpx.MockTransport(self.handle_ingest), **kwargs
            ),
        )
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)

    def handle_ingest(self, request):
        self.requests.append(request)
        if self.response_status == 400:
            return httpx.Response(400, json={"detail": "Invalid document_id"})
        return httpx.Response(202, json={
            "job_id": f"job-{len(self.requests)}", "status": "queued"
        })

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def upload(self, db, project=False):
        if project:
            return await project_service.upload_project_document(
                db, project_id=self.project_id, user_id=self.user_id,
                filename="manual.pdf", content_type="application/pdf", data=self.data,
            )
        return await document_service.upload_document(
            db, name="manual.pdf", domain="HR", visibility="DEPT_ONLY",
            data=self.data, content_type="application/pdf", department="HR_TEAM",
            user_id=self.user_id,
        )

    async def retry(self, db, document_id, project=False):
        if project:
            return await project_service.retry_project_document(
                db, self.project_id, document_id, self.user_id
            )
        return await document_service.retry_document_admin(db, document_id)

    def assert_request(self, request, document_id, project=False):
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.url.path, "/documents")
        self.assertEqual(request.headers["Content-Type"], "application/octet-stream")
        self.assertEqual(request.content, self.data)
        expected = {
            "document_id": str(document_id),
            "name": "manual.pdf",
            "domain": "GENERAL" if project else "HR",
            "visibility": "ALL" if project else "DEPT_ONLY",
        }
        if project:
            expected["project_id"] = str(self.project_id)
        else:
            expected["department"] = "HR_TEAM"
        self.assertEqual(dict(request.url.params), expected)

    async def test_admin_upload_sends_persisted_uuid_and_original_request(self):
        async with self.sessions() as db:
            doc = await self.upload(db)
            self.assertIsInstance(doc.document_id, UUID)
            self.assert_request(self.requests[-1], doc.document_id)
        async with self.sessions() as db:
            persisted = await db.get(Document, doc.document_id)
            self.assertEqual(str(persisted.document_id), self.requests[-1].url.params["document_id"])
            self.assertEqual(persisted.job_id, "job-1")

    async def test_project_upload_sends_persisted_uuid_and_project_scope(self):
        async with self.sessions() as db:
            doc = await self.upload(db, project=True)
            self.assert_request(self.requests[-1], doc.document_id, project=True)
            self.assertEqual(doc.project_id, self.project_id)

    async def test_retry_preserves_uuid_and_uses_new_job_for_both_scopes(self):
        for project in (False, True):
            for status in ("pending", "error"):
                with self.subTest(project=project, status=status):
                    async with self.sessions() as db:
                        doc = await self.upload(db, project)
                        document_id, old_job_id = doc.document_id, doc.job_id
                        doc.status = status
                        await db.commit()
                        total_before = await db.scalar(select(func.count()).select_from(Document))
                    async with self.sessions() as db:
                        retried = await self.retry(db, document_id, project)
                        self.assertEqual(retried.document_id, document_id)
                        self.assertNotEqual(retried.job_id, old_job_id)
                        self.assert_request(self.requests[-1], document_id, project)
                        self.assertEqual(
                            await db.scalar(select(func.count()).select_from(Document)), total_before
                        )

    async def test_same_name_uploads_have_distinct_uuids_within_each_scope(self):
        for project in (False, True):
            with self.subTest(project=project):
                async with self.sessions() as db:
                    first = await self.upload(db, project)
                    second = await self.upload(db, project)
                    self.assertNotEqual(first.document_id, second.document_id)
                    self.assert_request(self.requests[-2], first.document_id, project)
                    self.assert_request(self.requests[-1], second.document_id, project)

    async def test_rejected_ingest_keeps_uuid_for_retry_in_both_scopes(self):
        for project in (False, True):
            with self.subTest(project=project):
                self.response_status = 400
                async with self.sessions() as db:
                    with self.assertRaises(BadRequestError):
                        await self.upload(db, project)
                rejected_request = self.requests[-1]
                document_id = UUID(rejected_request.url.params["document_id"])
                async with self.sessions() as db:
                    failed = await db.get(Document, document_id)
                    self.assertEqual(failed.status, "error")
                    self.assertIsNone(failed.job_id)
                    self.response_status = 202
                    retried = await self.retry(db, document_id, project)
                    self.assertEqual(retried.document_id, document_id)
                    self.assertEqual(retried.status, "queued")
                    self.assert_request(self.requests[-1], document_id, project)


if __name__ == "__main__":
    unittest.main()
