from abc import ABC, abstractmethod
from typing import Any, Sequence


class BaseDatabase(ABC):
    @abstractmethod
    async def connect(self, dsn: str) -> None: ...

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

    @staticmethod
    @abstractmethod
    def python_to_sql_type(py_type: type) -> str: ...
