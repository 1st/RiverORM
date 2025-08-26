from abc import ABC, abstractmethod
from typing import Any, Sequence


class BaseDatabase(ABC):
    @abstractmethod
    def __init__(self, dsn: str, debug: bool = False) -> None: ...

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

    @staticmethod
    @abstractmethod
    def python_to_sql_type(py_type: type) -> str: ...

    # Helper methods for SQL generation

    @staticmethod
    @abstractmethod
    def auto_increment_primary_key_sql(name: str) -> str:
        """Return the SQL snippet for an auto-increment primary key field."""
        ...
