import asyncio
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4


class StorageUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredObject:
    provider: str
    key: str
    sha256: str
    size_bytes: int


class ObjectStorage(Protocol):
    async def put(self, owner: UUID, content: bytes) -> StoredObject: ...
    async def read(self, owner: UUID, key: str) -> bytes: ...
    async def delete(self, owner: UUID, key: str) -> None: ...


class UnconfiguredStorage:
    async def put(self, owner, content):
        raise StorageUnavailable('Configure object storage to retain binary files')

    async def read(self, owner, key):
        raise StorageUnavailable('Object storage is not configured')

    async def delete(self, owner, key):
        raise StorageUnavailable('Object storage is not configured')


class LocalDevelopmentStorage:
    """Explicit opt-in for local development only; never a Render durable fallback."""
    def __init__(self, directory):
        if os.getenv('RENDER') or os.getenv('ENVIRONMENT') == 'production':
            raise StorageUnavailable('Local storage is not supported in production')
        self.root = Path(directory).resolve()

    def path(self, owner, key):
        owner = str(UUID(str(owner)))
        parts = key.split('/')
        if len(parts) != 2 or parts[0] != owner:
            raise PermissionError('Object owner mismatch')
        object_id = str(UUID(parts[1]))
        path = (self.root / owner / object_id).resolve()
        if not path.is_relative_to(self.root):
            raise PermissionError('Invalid storage key')
        return path

    async def put(self, owner, content):
        if len(content) > 20 * 1024 * 1024:
            raise ValueError('Object exceeds 20 MB')
        key = f'{UUID(str(owner))}/{uuid4()}'
        path = self.path(owner,key)
        def write():
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as stream:
                stream.write(content)
        await asyncio.to_thread(write)
        return StoredObject('local_dev',key,hashlib.sha256(content).hexdigest(),len(content))

    async def read(self, owner, key):
        return await asyncio.to_thread(self.path(owner,key).read_bytes)

    async def delete(self, owner, key):
        await asyncio.to_thread(self.path(owner,key).unlink,missing_ok=True)
