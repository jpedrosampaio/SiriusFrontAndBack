import asyncio
import tempfile
import unittest
from uuid import uuid4
from storage.objects import LocalDevelopmentStorage,UnconfiguredStorage,StorageUnavailable


class BinaryStorage(unittest.IsolatedAsyncioTestCase):
    async def test_binary_owner_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = LocalDevelopmentStorage(directory)
            owner,other = uuid4(),uuid4()
            stored = await storage.put(owner,b'%PDF-test')
            self.assertEqual(stored.size_bytes,9)
            self.assertEqual(len(stored.sha256),64)
            self.assertEqual(await storage.read(owner,stored.key),b'%PDF-test')
            with self.assertRaises(PermissionError):
                await storage.read(other,stored.key)
            with self.assertRaises((ValueError,PermissionError)):
                await storage.read(owner,f'{owner}/../../secrets')
            await storage.delete(owner,stored.key)
            with self.assertRaises(FileNotFoundError):
                await storage.read(owner,stored.key)

    async def test_missing_storage_is_explicit(self):
        with self.assertRaises(StorageUnavailable):
            await UnconfiguredStorage().put(uuid4(),b'test')
