import abc
import asyncio
from typing import Any


class AbstractStore(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def put(self, key, value):
        """Put the value associated with the key into the store."""

    @abc.abstractmethod
    def get(self, key):
        """Return the value associated with the key."""

    @abc.abstractmethod
    def delete(self, key):
        """Delete the key and its value from the store."""
        pass

    @abc.abstractmethod
    def clear(self):
        """Clear the store."""
        pass

    @abc.abstractmethod
    def exists(self, key):
        """Return True if the key is in the store."""
        pass

    @abc.abstractmethod
    def keys(self):
        """Return a list of all the keys in the store."""
        pass

    @abc.abstractmethod
    def items(self):
        """Return a list of all the items in the store."""
        pass


class InMemoryStore(AbstractStore):
    def __init__(self):
        self.store = {}

    def put(self, key, value):
        self.store[key] = value

    def get(self, key):
        return self.store.get(key)

    def delete(self, key):
        del self.store[key]

    def clear(self):
        self.store.clear()

    def exists(self, key):
        return key in self.store

    def keys(self):
        return list(self.store.keys())

    def items(self):
        return list(self.store.items())


class AsyncInMemoryStore(AbstractStore):
    def __init__(self):
        self.store: dict[str, list[Any]] = {}
        self._lock = asyncio.Lock()

    async def put(self, key, value):
        async with self._lock:
            if key not in self.store:
                self.store[key] = []

            self.store[key].append(value)

    async def get(self, key) -> list[Any] | None:
        async with self._lock:
            return self.store.get(key)

    async def delete(self, key):
        async with self._lock:
            del self.store[key]

    async def clear(self):
        async with self._lock:
            self.store.clear()

    async def exists(self, key) -> bool:
        async with self._lock:
            return key in self.store

    async def keys(self) -> list[str]:
        async with self._lock:
            return list(self.store.keys())

    async def items(self) -> list[tuple[str, list[Any]]]:
        async with self._lock:
            return list(self.store.items())

    async def pop(self, key) -> list[Any] | None:
        async with self._lock:
            if key in self.store:
                return self.store.pop(key)
