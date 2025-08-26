import os
from dataclasses import dataclass

from dotenv import load_dotenv

from riverorm import constants


@dataclass
class Config:
    POSTGRES_DSN: str
    MYSQL_DSN: str
    DB_TYPE: str
    DEBUG: bool


config: Config

# Ensure the .env file is loaded only once
if "config" not in globals():
    # Load environment variables from .env file
    load_dotenv()

    # Default DSNs, can be overridden by environment variables
    config = Config(
        POSTGRES_DSN=os.getenv(
            "POSTGRES_DSN", "postgresql://river_user:river_pass@localhost:5432/river_test"
        ),
        MYSQL_DSN=os.getenv("MYSQL_DSN", "mysql://river_user:river_pass@localhost:3306/river_test"),
        DB_TYPE=os.getenv("DB_TYPE", constants.DEFAULT_DB),
        DEBUG=os.getenv("DEBUG", "False").lower() in ("true", "1", "yes"),
    )
