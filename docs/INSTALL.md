# Installation Guide

RiverORM can be installed as a minimal base library, or with optional database backends as needed.

## Basic Installation

To install the base RiverORM package:

```sh
pip install riverorm
```

## With Database Backends

You can install RiverORM with support for specific databases using extras:

- **PostgreSQL**:
  ```sh
  pip install 'riverorm[postgres]'
  # or using uv
  uv add 'riverorm[postgres]'
  ```
  This will install the `asyncpg` driver.

- **MySQL**:
  ```sh
  pip install 'riverorm[mysql]'
  # or using uv
  uv add 'riverorm[mysql]'
  ```
  This will install the `aiomysql` driver.

- **Multiple Backends**:
  ```sh
  pip install 'riverorm[postgres,mysql]'
  # or using uv
  uv add 'riverorm[postgres,mysql]'
  ```

## Development Installation

For development, install with dev dependencies:

```sh
# Install main dependencies
uv sync
# Install with PostgreSQL support
uv pip install '.[postgres]'
# Install with MySQL support
uv pip install '.[mysql]'
# Alternatively, install with all extras
uv sync --all-extras
```

---

For more details, see the [README.md](../README.md) or other documentation files in the `docs/` folder.
