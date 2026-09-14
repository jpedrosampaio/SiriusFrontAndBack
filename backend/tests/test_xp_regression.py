"""Exercise the real XP helper without initializing application integrations."""
import ast
import asyncio
import os
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from fastapi import HTTPException

SOURCE = Path(__file__).resolve().parents[1] / "server.py"
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"))


def load_xp(db):
    ns = {"db": db, "asyncio": asyncio, "HTTPException": HTTPException}
    selected = [n for n in TREE.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name in {"award_xp", "calculate_rank"}]
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"), ns)
    return ns


class XPRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_stale_balance_and_returns_applied_rank(self):
        users = SimpleNamespace(
            find_one=AsyncMock(side_effect=[{"xp": 190}, {"xp": 198}]),
            update_one=AsyncMock(side_effect=[
                SimpleNamespace(matched_count=0), SimpleNamespace(matched_count=1)]))
        ns = load_xp(SimpleNamespace(users=users))
        self.assertEqual(await ns["award_xp"]("alice", 8), (206, "Soldado"))
        self.assertEqual(users.update_one.call_args.args,
                         ({"user_id": "alice", "xp": 198},
                          {"$set": {"xp": 206, "rank": "Soldado"}}))

    async def test_zero_balance_deduction_uses_matched_count(self):
        users = SimpleNamespace(find_one=AsyncMock(return_value={"xp": 0}),
            update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1, modified_count=0)))
        self.assertEqual(await load_xp(SimpleNamespace(users=users))["award_xp"]("alice", -8),
                         (0, "Recruta"))
        users.update_one.assert_awaited_once()

    async def test_missing_xp_initialized_conditionally(self):
        users = SimpleNamespace(find_one=AsyncMock(return_value={}),
            update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)))
        self.assertEqual(await load_xp(SimpleNamespace(users=users))["award_xp"]("alice", 8),
                         (8, "Recruta"))
        self.assertEqual(users.update_one.call_args.args[0],
                         {"user_id": "alice", "xp": {"$exists": False}})

    async def test_deleted_user_is_not_recreated(self):
        users = SimpleNamespace(find_one=AsyncMock(return_value=None), update_one=AsyncMock())
        with self.assertRaises(HTTPException) as caught:
            await load_xp(SimpleNamespace(users=users))["award_xp"]("alice", 8)
        self.assertEqual(caught.exception.status_code, 404)
        users.update_one.assert_not_awaited()

    async def test_contention_has_bounded_retry(self):
        users = SimpleNamespace(find_one=AsyncMock(return_value={"xp": 100}),
            update_one=AsyncMock(return_value=SimpleNamespace(matched_count=0)))
        with self.assertRaises(HTTPException) as caught:
            await load_xp(SimpleNamespace(users=users))["award_xp"]("alice", 8)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(users.update_one.await_count, 100)


@unittest.skipUnless(os.environ.get("XP_TEST_MONGO_URI"), "isolated MongoDB not configured")
class XPMongoConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from motor.motor_asyncio import AsyncIOMotorClient
        self.client = AsyncIOMotorClient(os.environ["XP_TEST_MONGO_URI"], serverSelectionTimeoutMS=5000)
        self.db = self.client["sirius_xp_test_" + uuid.uuid4().hex]
        self.ns = load_xp(self.db)
        await self.db.users.insert_many([
            {"user_id": "alice", "xp": 190, "rank": "Recruta"},
            {"user_id": "bob", "xp": 500, "rank": "Cabo"}])

    async def asyncTearDown(self):
        await self.client.drop_database(self.db.name)
        self.client.close()

    async def test_concurrent_awards_do_not_overwrite_each_other(self):
        await asyncio.gather(*(self.ns["award_xp"]("alice", 8) for _ in range(40)))
        row = await self.db.users.find_one({"user_id": "alice"})
        self.assertEqual((row["xp"], row["rank"]), (510, "Cabo"))
        bob = await self.db.users.find_one({"user_id": "bob"})
        self.assertEqual((bob["xp"], bob["rank"]), (500, "Cabo"))

    async def test_concurrent_awards_and_deductions_keep_rank_consistent(self):
        await asyncio.gather(*(self.ns["award_xp"]("bob", amount)
                              for amount in [10, -8] * 20))
        row = await self.db.users.find_one({"user_id": "bob"})
        self.assertEqual((row["xp"], row["rank"]), (540, "Cabo"))

    async def test_concurrent_deductions_never_go_negative(self):
        await asyncio.gather(*(self.ns["award_xp"]("alice", -8) for _ in range(40)))
        row = await self.db.users.find_one({"user_id": "alice"})
        self.assertEqual((row["xp"], row["rank"]), (0, "Recruta"))

    async def test_concurrent_legacy_user_initialization(self):
        await self.db.users.insert_one({"user_id": "legacy"})
        await asyncio.gather(*(self.ns["award_xp"]("legacy", 8) for _ in range(30)))
        row = await self.db.users.find_one({"user_id": "legacy"})
        self.assertEqual((row["xp"], row["rank"]), (240, "Soldado"))


if __name__ == "__main__":
    unittest.main()
