"""Create and verify the production RDS application account."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from typing import Any

import mysql.connector


_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")


def _required(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is not configured")
    return value


def _identifier(environ: Mapping[str, str], name: str) -> str:
    value = _required(environ, name)
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} may contain only letters, numbers, and underscores")
    return value


def bootstrap_rds(environ: Mapping[str, str]) -> dict[str, Any]:
    host = _required(environ, "MYSQL_HOST")
    port = int(environ.get("MYSQL_PORT", "3306"))
    admin_user = _identifier(environ, "MYSQL_ADMIN_USER")
    admin_password = _required(environ, "MYSQL_ADMIN_PASSWORD")
    app_user = _identifier(environ, "MYSQL_USER")
    app_password = _required(environ, "MYSQL_PASSWORD")
    databases = (
        _identifier(environ, "ACCOUNT_DB_NAME"),
        _identifier(environ, "TRAVEL_DB_NAME"),
    )

    if admin_user == app_user:
        raise ValueError("RDS administrator and application users must differ")
    if admin_password == app_password:
        raise ValueError("RDS administrator and application passwords must differ")
    if app_password.startswith("arn:"):
        raise ValueError("MYSQL_PASSWORD must contain the application password, not an ARN")
    if len(app_password) < 16:
        raise ValueError("MYSQL_PASSWORD must be at least 16 characters")
    if databases[0] == databases[1]:
        raise ValueError("ACCOUNT_DB_NAME and TRAVEL_DB_NAME must differ")

    account = f"'{app_user}'@'%'"
    admin_connection = mysql.connector.connect(
        host=host,
        port=port,
        user=admin_user,
        password=admin_password,
        connection_timeout=10,
    )
    try:
        cursor = admin_connection.cursor()
        try:
            for database in databases:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                )
            cursor.execute(
                f"CREATE USER IF NOT EXISTS {account} IDENTIFIED BY %s",
                (app_password,),
            )
            cursor.execute(
                f"ALTER USER {account} IDENTIFIED BY %s",
                (app_password,),
            )
            for database in databases:
                cursor.execute(
                    f"GRANT ALL PRIVILEGES ON `{database}`.* TO {account}"
                )
            admin_connection.commit()
        finally:
            cursor.close()
    finally:
        admin_connection.close()

    verified_databases: list[str] = []
    for database in databases:
        connection = mysql.connector.connect(
            host=host,
            port=port,
            user=app_user,
            password=app_password,
            database=database,
            connection_timeout=10,
        )
        try:
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT CURRENT_USER(), DATABASE()")
                current_user, current_database = cursor.fetchone()
                if not str(current_user).startswith(f"{app_user}@"):
                    raise RuntimeError("RDS application user verification failed")
                if str(current_database) != database:
                    raise RuntimeError("RDS application database verification failed")
                verified_databases.append(database)
            finally:
                cursor.close()
        finally:
            connection.close()

    return {
        "status": "ok",
        "application_user": app_user,
        "verified_databases": verified_databases,
    }


def main() -> int:
    result = bootstrap_rds(os.environ)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
