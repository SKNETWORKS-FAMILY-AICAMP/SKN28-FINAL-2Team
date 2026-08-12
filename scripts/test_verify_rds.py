from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts import verify_rds


class _Cursor:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, _query, _parameters=()):
        return None

    def fetchone(self):
        return ("8.4.0",)


class _Connection:
    def cursor(self):
        return _Cursor()


class RDSVerificationPolicyTests(unittest.TestCase):
    @patch("scripts.verify_rds._column_names")
    @patch("scripts.verify_rds._scalar")
    @patch("scripts.verify_rds._table_names")
    def test_initial_load_does_not_require_aihub_mapping(
        self, mocked_table_names, mocked_scalar, mocked_column_names
    ) -> None:
        mocked_table_names.side_effect = [
            verify_rds.ACCOUNT_TABLES,
            verify_rds.TRAVEL_TABLES,
        ]
        mocked_column_names.side_effect = lambda _cursor, _database, table: (
            verify_rds.TRAVEL_COLUMN_CONTRACTS[table]
        )

        def scalar_result(_cursor, query, _parameters=()):
            if "LEFT JOIN" in query or "KEY_COLUMN_USAGE" in query:
                return 0
            return 1

        mocked_scalar.side_effect = scalar_result

        result = verify_rds._verify_connection(
            _Connection(),
            account_database="accounts",
            travel_database="travel",
        )

        self.assertNotIn("aihub_places", verify_rds.TRAVEL_TABLES)
        self.assertNotIn("aihub_mapped_places", result["row_counts"])
        self.assertFalse(
            any("aihub_places" in call.args[1] for call in mocked_scalar.call_args_list)
        )


if __name__ == "__main__":
    unittest.main()
