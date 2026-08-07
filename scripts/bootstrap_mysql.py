"""Create the local account/travel databases and grant the application user access."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import secrets
import sys

import mysql.connector
from dotenv import load_dotenv, set_key

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")

def _identifier(value: str, name: str) -> str:
    if not IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{name} may contain only letters, numbers, and underscores")
    return value

def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is not configured")
    return value

def bootstrap(env_file: Path) -> dict[str, str]:
    load_dotenv(env_file, override=True)
    admin_user = _required("MYSQL_ADMIN_USER")
    admin_password = _required("MYSQL_ADMIN_PASSWORD")
    app_user = _identifier(os.getenv("MYSQL_USER", "tour_app"), "MYSQL_USER")
    account_database = _identifier(os.getenv("ACCOUNT_DB_NAME", "accounts_db"), "ACCOUNT_DB_NAME")
    travel_database = _identifier(
        os.getenv("TRAVEL_DB_NAME") or os.getenv("MYSQL_DATABASE", "tour_recommender"),
        "TRAVEL_DB_NAME",
    )
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    app_password = os.getenv("MYSQL_PASSWORD", "").strip() or secrets.token_urlsafe(32)

    connection = mysql.connector.connect(
        host=host, port=port, user=admin_user, password=admin_password, connection_timeout=10
    )
    try:
        cursor = connection.cursor()
        try:
            for database in (account_database, travel_database):
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                )
            for account_host in ("localhost", "127.0.0.1"):
                account = f"'{app_user}'@'{account_host}'"
                cursor.execute(f"CREATE USER IF NOT EXISTS {account} IDENTIFIED BY %s", (app_password,))
                cursor.execute(f"ALTER USER {account} IDENTIFIED BY %s", (app_password,))
                cursor.execute(f"GRANT ALL PRIVILEGES ON `{account_database}`.* TO {account}")
                cursor.execute(f"GRANT ALL PRIVILEGES ON `{travel_database}`.* TO {account}")
            connection.commit()
        finally:
            cursor.close()
    finally:
        connection.close()

    values = {
        "MYSQL_USER": app_user,
        "MYSQL_PASSWORD": app_password,
        "MYSQL_DATABASE": travel_database,
        "TRAVEL_DB_NAME": travel_database,
        "ACCOUNT_DB_NAME": account_database,
        "AIHUB_MYSQL_DATABASE": travel_database,
    }
    for key, value in values.items():
        set_key(str(env_file), key, value, quote_mode="never")
    return {"app_user": app_user, "account_database": account_database, "travel_database": travel_database}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    args = parser.parse_args()
    try:
        result = bootstrap(args.env_file.resolve())
    except Exception as exc:
        print(f"MySQL bootstrap failed: {exc}", file=sys.stderr)
        return 1
    print("MySQL bootstrap complete")
    print(f"  application user: {result['app_user']}")
    print(f"  account database: {result['account_database']}")
    print(f"  travel database: {result['travel_database']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
