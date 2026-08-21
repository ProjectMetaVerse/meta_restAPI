"""Repository abstractions used by application services."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

EntityT = TypeVar("EntityT")


class Repository(Generic[EntityT], ABC):
    """Minimal asynchronous repository contract."""

    @abstractmethod
    async def get(self, identifier: str) -> EntityT | None:
        """Retrieve an entity by its identifier."""
        raise NotImplementedError
