from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.bootstrap_rds import bootstrap_rds


class _Cursor:
    def __init__(self, database: str | None = None) -> None:
        self.database = database
        self.statements: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> None:
        self.statements.append((sql, parameters))

    def fetchone(self):
        return ("tour_prod_app@%", self.database)

    def close(self) -> None:
        return None


class _Connection:
    def __init__(self, database: str | None = None) -> None:
        self.cursor_instance = _Cursor(database)

    def cursor(self):
        return self.cursor_instance

    def commit(self) -> None:
        return None

    def close(self) -> None:
        return None


class BootstrapRDSTests(unittest.TestCase):
    @patch("scripts.bootstrap_rds.mysql.connector.connect")
    def test_resets_and_verifies_application_credentials(self, mocked_connect) -> None:
        admin = _Connection()
        accounts = _Connection("accounts_db")
        travel = _Connection("tour_recommender")
        mocked_connect.side_effect = [admin, accounts, travel]

        result = bootstrap_rds(
            {
                "MYSQL_HOST": "db.example.com",
                "MYSQL_PORT": "3306",
                "MYSQL_ADMIN_USER": "touradmin",
                "MYSQL_ADMIN_PASSWORD": "admin-password-123456",
                "MYSQL_USER": "tour_prod_app",
                "MYSQL_PASSWORD": "application-password-123456",
                "ACCOUNT_DB_NAME": "accounts_db",
                "TRAVEL_DB_NAME": "tour_recommender",
            }
        )

        statements = [sql for sql, _params in admin.cursor_instance.statements]
        self.assertTrue(any(sql.startswith("ALTER USER") for sql in statements))
        self.assertEqual(sum(sql.startswith("GRANT ALL") for sql in statements), 2)
        self.assertEqual(result["verified_databases"], ["accounts_db", "tour_recommender"])
        self.assertEqual(mocked_connect.call_count, 3)


if __name__ == "__main__":
    unittest.main()
