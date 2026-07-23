"""Create least-privilege local MySQL databases and an application account."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import secrets
import sys

import mysql.connector
from dotenv import load_dotenv, set_key, unset_key


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
    tour_database = _identifier(
        os.getenv("MYSQL_DATABASE", "tour_recommender"), "MYSQL_DATABASE"
    )
    aihub_database = _identifier(
        os.getenv("AIHUB_MYSQL_DATABASE", "tour_recommender_aihub"),
        "AIHUB_MYSQL_DATABASE",
    )
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    app_password = secrets.token_urlsafe(32)

    connection = mysql.connector.connect(
        host=host,
        port=port,
        user=admin_user,
        password=admin_password,
        connection_timeout=10,
    )
    try:
        cursor = connection.cursor()
        try:
            for database in (tour_database, aihub_database):
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                )
            for account_host in ("localhost", "127.0.0.1"):
                account = f"'{app_user}'@'{account_host}'"
                cursor.execute(
                    f"CREATE USER IF NOT EXISTS {account} IDENTIFIED BY %s",
                    (app_password,),
                )
                cursor.execute(
                    f"ALTER USER {account} IDENTIFIED BY %s",
                    (app_password,),
                )
                cursor.execute(
                    f"GRANT ALL PRIVILEGES ON `{tour_database}`.* TO {account}"
                )
                cursor.execute(
                    f"GRANT ALL PRIVILEGES ON `{aihub_database}`.* TO {account}"
                )
            connection.commit()
        finally:
            cursor.close()
    finally:
        connection.close()

    set_key(str(env_file), "MYSQL_USER", app_user, quote_mode="never")
    set_key(str(env_file), "MYSQL_PASSWORD", app_password, quote_mode="never")
    set_key(str(env_file), "MYSQL_DATABASE", tour_database, quote_mode="never")
    set_key(
        str(env_file),
        "AIHUB_MYSQL_DATABASE",
        aihub_database,
        quote_mode="never",
    )
    unset_key(str(env_file), "MYSQL_ADMIN_USER")
    unset_key(str(env_file), "MYSQL_ADMIN_PASSWORD")
    return {
        "app_user": app_user,
        "tour_database": tour_database,
        "aihub_database": aihub_database,
    }


def prepare_workbench_sql(env_file: Path, output_path: Path) -> dict[str, str]:
    load_dotenv(env_file, override=True)
    app_user = _identifier(os.getenv("MYSQL_USER", "tour_app"), "MYSQL_USER")
    tour_database = _identifier(
        os.getenv("MYSQL_DATABASE", "tour_recommender"), "MYSQL_DATABASE"
    )
    aihub_database = _identifier(
        os.getenv("AIHUB_MYSQL_DATABASE", "tour_recommender_aihub"),
        "AIHUB_MYSQL_DATABASE",
    )
    app_password = secrets.token_urlsafe(32)
    statements = [
        "SELECT CURRENT_USER() AS authenticated_account;",
        (
            f"CREATE DATABASE IF NOT EXISTS `{tour_database}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
        ),
        (
            f"CREATE DATABASE IF NOT EXISTS `{aihub_database}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
        ),
    ]
    for account_host in ("localhost", "127.0.0.1"):
        account = f"'{app_user}'@'{account_host}'"
        statements.extend(
            [
                f"CREATE USER IF NOT EXISTS {account} IDENTIFIED BY '{app_password}';",
                f"ALTER USER {account} IDENTIFIED BY '{app_password}';",
                f"GRANT ALL PRIVILEGES ON `{tour_database}`.* TO {account};",
                f"GRANT ALL PRIVILEGES ON `{aihub_database}`.* TO {account};",
            ]
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n".join(statements) + "\n", encoding="utf-8")

    set_key(str(env_file), "MYSQL_USER", app_user, quote_mode="never")
    set_key(str(env_file), "MYSQL_PASSWORD", app_password, quote_mode="never")
    set_key(str(env_file), "MYSQL_DATABASE", tour_database, quote_mode="never")
    set_key(
        str(env_file),
        "AIHUB_MYSQL_DATABASE",
        aihub_database,
        quote_mode="never",
    )
    unset_key(str(env_file), "MYSQL_ADMIN_USER")
    unset_key(str(env_file), "MYSQL_ADMIN_PASSWORD")
    return {
        "app_user": app_user,
        "tour_database": tour_database,
        "aihub_database": aihub_database,
        "sql_output": str(output_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create local project databases and a least-privilege MySQL user."
    )
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument(
        "--workbench-sql",
        type=Path,
        help="Write a one-time ignored SQL script for an authenticated Workbench session.",
    )
    args = parser.parse_args()
    try:
        if args.workbench_sql is not None:
            result = prepare_workbench_sql(
                args.env_file.resolve(), args.workbench_sql.resolve()
            )
        else:
            result = bootstrap(args.env_file.resolve())
    except Exception as exc:
        print(f"MySQL bootstrap failed: {exc}", file=sys.stderr)
        return 1
    if args.workbench_sql is not None:
        print("MySQL Workbench bootstrap SQL prepared")
        print(f"  SQL file: {result['sql_output']}")
        print("  application password: stored only in the local .env and SQL file")
        print("  delete the SQL file immediately after successful execution")
        return 0
    print("MySQL bootstrap complete")
    print(f"  application user: {result['app_user']}")
    print(f"  TourAPI database: {result['tour_database']}")
    print(f"  AIHub database: {result['aihub_database']}")
    print("  application password: stored only in the local .env")
    print("  administrator credentials: removed from the local .env")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
