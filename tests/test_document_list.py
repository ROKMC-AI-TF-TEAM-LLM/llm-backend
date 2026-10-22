"""문서 목록 회귀 테스트. 실행에는 테스트용 aiosqlite가 필요하다."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID

import httpx
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.deps import get_current_user
from app.main import app
from app.models.document import Document, VisibilityEnum
from app.models.project import Project
from app.models.user import User
from app.services import document_service


class DocumentListTests(unittest.IsolatedAsyncioTestCase):
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
        self.user = User(
            user_id=UUID(int=100), name="Tester", email="tester@example.com", password="unused"
        )
        project_id = UUID(int=200)
        created_at = datetime(2026, 10, 22, tzinfo=timezone.utc)
        async with self.sessions() as db:
            db.add(self.user)
            await db.flush()
            db.add(Project(project_id=project_id, user_id=self.user.user_id, title="Private"))
            await db.flush()
            for number, name, domain, status, project in [
                (1, "hr-old.pdf", "HR", "done", None),
                (2, "hr-tie.pdf", "HR", "done", None),
                (3, "hr-new.pdf", "HR", "done", None),
                (4, "tech.pdf", "TECH", "done", None),
                (5, "pending.pdf", "HR", "pending", None),
                (6, "queued.pdf", "HR", "queued", None),
                (7, "running.pdf", "HR", "running", None),
                (8, "error.pdf", "HR", "error", None),
                (9, "private.pdf", "HR", "done", project_id),
            ]:
                db.add(Document(
                    document_id=UUID(int=number),
                    name=name,
                    domain=domain,
                    status=status,
                    project_id=project,
                    user_id=self.user.user_id,
                    visibility=VisibilityEnum.DEPT_ONLY if number == 3 else VisibilityEnum.ALL,
                    department="HR_TEAM" if number == 3 else None,
                    content_type="application/pdf",
                    data=b"private original bytes",
                    size=22,
                    created_at=created_at + timedelta(seconds=max(0, number - 2)),
                ))
            await db.commit()

        async def override_db():
            async with self.sessions() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )
        # 목록 조회가 외부 AI 서버를 호출하면 모든 테스트에서 즉시 실패한다.
        self.no_llm = patch(
            "app.services.document_service.httpx.AsyncClient",
            side_effect=AssertionError("Document listing must not call the LLM server"),
        )
        self.no_llm.start()

    async def asyncTearDown(self):
        self.no_llm.stop()
        app.dependency_overrides.clear()
        await self.client.aclose()
        await self.engine.dispose()

    async def get_page(self, **params):
        response = await self.client.get("/api/v1/documents", params=params)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["status_code"], 200)
        return body["data"]

    async def test_user_list_uses_db_and_keeps_response_contract(self):
        page = await self.get_page()
        self.assertEqual(page["total"], 4)
        self.assertEqual(page["offset"], 0)
        self.assertEqual(page["limit"], 20)
        self.assertFalse(page["has_more"])
        self.assertEqual(
            [doc["name"] for doc in page["documents"]],
            ["tech.pdf", "hr-new.pdf", "hr-tie.pdf", "hr-old.pdf"],
        )
        self.assertEqual(page["documents"][1], {
            "name": "hr-new.pdf",
            "type": None,
            "domain": "HR",
            "visibility": "DEPT_ONLY",
            "owning_department": "HR_TEAM",
            "applied_at": None,
        })

    async def test_domain_filter_first_next_last_and_out_of_range_pages(self):
        for offset, expected, has_more in [
            (0, ["hr-new.pdf"], True),
            (1, ["hr-tie.pdf"], True),
            (2, ["hr-old.pdf"], False),
            (3, [], False),
            (20, [], False),
        ]:
            with self.subTest(offset=offset):
                page = await self.get_page(domain="HR", offset=offset, limit=1)
                self.assertEqual(page["total"], 3)
                self.assertEqual(page["offset"], offset)
                self.assertEqual(page["limit"], 1)
                self.assertEqual(page["has_more"], has_more)
                self.assertEqual([doc["name"] for doc in page["documents"]], expected)

    async def test_pagination_without_domain(self):
        first = await self.get_page(offset=0, limit=2)
        last = await self.get_page(offset=2, limit=2)
        self.assertEqual(first["total"], 4)
        self.assertEqual(last["total"], 4)
        self.assertTrue(first["has_more"])
        self.assertFalse(last["has_more"])
        self.assertEqual(
            [doc["name"] for doc in first["documents"] + last["documents"]],
            ["tech.pdf", "hr-new.pdf", "hr-tie.pdf", "hr-old.pdf"],
        )

    async def test_unknown_domain_is_empty(self):
        page = await self.get_page(domain="UNKNOWN")
        self.assertEqual(page["documents"], [])
        self.assertEqual(page["total"], 0)
        self.assertFalse(page["has_more"])

    async def test_user_query_does_not_load_binary_or_uploader(self):
        async with self.sessions() as db:
            documents, total, _ = await document_service.get_documents(db, 0, 20)
            self.assertEqual(total, 4)
            for doc in documents:
                self.assertTrue({"data", "user", "job_id", "error"} <= inspect(doc).unloaded)

    async def test_admin_still_includes_all_statuses_and_supports_search(self):
        async with self.sessions() as db:
            documents, total, has_more = await document_service.get_admin_documents(
                db, offset=0, limit=20, domain="HR"
            )
            self.assertEqual(total, 7)
            self.assertFalse(has_more)
            self.assertEqual({doc.status for doc in documents}, {
                "pending", "queued", "running", "done", "error"
            })
            self.assertTrue(all(doc.project_id is None for doc in documents))
            self.assertTrue(all(doc.user.name == "Tester" for doc in documents))
            documents, total, _ = await document_service.get_admin_documents(
                db, offset=0, limit=20, domain="HR", search="running"
            )
            self.assertEqual(total, 1)
            self.assertEqual([doc.name for doc in documents], ["running.pdf"])

    async def test_pagination_input_limits_are_preserved(self):
        for params in [{"offset": -1}, {"limit": 0}, {"limit": 101}]:
            with self.subTest(params=params):
                response = await self.client.get("/api/v1/documents", params=params)
                self.assertEqual(response.status_code, 422)

    async def test_missing_authentication_is_rejected(self):
        del app.dependency_overrides[get_current_user]
        response = await self.client.get("/api/v1/documents")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
