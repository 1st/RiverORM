from abc import ABC, abstractmethod
from typing import Any, Sequence

from riverorm.sql import Compiler, Dialect


class BaseDatabase(ABC):
    is_connected: bool = False

    @abstractmethod
    def __init__(self, dsn: str, debug: bool = False) -> None: ...

    @property
    @abstractmethod
    def dialect(self) -> Dialect:
        """Return the SQL dialect describing this backend's syntax."""
        ...

    @property
    def compiler(self) -> Compiler:
        """A :class:`Compiler` bound to this backend's :attr:`dialect`."""
        return Compiler(self.dialect)

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def execute(self, query: str, *args: Any) -> Any: ...

    @abstractmethod
    async def fetch(self, query: str, *args: Any) -> Sequence[Any]: ...

    @abstractmethod
    async def fetchrow(self, query: str, *args: Any) -> Any: ...

    @abstractmethod
    async def update(self, query: str, *args: Any) -> Any: ...

    @abstractmethod
    async def execute_insert(self, query: str, *args: Any) -> Any:
        """Execute an ``INSERT`` and return the generated primary key.

        Used for backends without ``RETURNING`` support: the value comes from
        the driver after the insert (e.g. ``cursor.lastrowid``). Assumes a single
        integer auto-increment primary key.
        """
        ...
