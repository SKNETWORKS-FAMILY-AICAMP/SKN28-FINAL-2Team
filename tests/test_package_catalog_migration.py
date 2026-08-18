from __future__ import annotations

from contextlib import nullcontext
import unittest
from unittest.mock import Mock, patch

from scripts.storage import migrate_package_catalog as migration


class PackageCatalogMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.migration_path = migration.DEFAULT_MIGRATION
        self.repository = Mock()
        self.connection = Mock()
        self.repository.connect.return_value = nullcontext(self.connection)

    @patch.object(migration, "_record_migration")
    @patch.object(migration, "_verify_required_columns")
    @patch.object(migration, "_applied_checksum", return_value=None)
    @patch.object(migration, "_ensure_migration_table")
    def test_applies_and_records_unseen_migration(
        self,
        ensure_table: Mock,
        applied_checksum: Mock,
        verify_columns: Mock,
        record_migration: Mock,
    ) -> None:
        result = migration.migrate_package_catalog(
            self.repository,
            self.migration_path,
        )

        self.repository.apply_schema.assert_called_once_with(self.migration_path)
        record_migration.assert_called_once()
        self.assertEqual(result["result"], "applied")

    @patch.object(migration, "_verify_required_columns")
    @patch.object(migration, "_ensure_migration_table")
    def test_skips_migration_with_matching_checksum(
        self,
        ensure_table: Mock,
        verify_columns: Mock,
    ) -> None:
        checksum = migration._migration_checksum(self.migration_path)
        with patch.object(migration, "_applied_checksum", return_value=checksum):
            result = migration.migrate_package_catalog(
                self.repository,
                self.migration_path,
            )

        self.repository.apply_schema.assert_not_called()
        verify_columns.assert_called_once_with(self.connection)
        self.assertEqual(result["result"], "already_applied")


if __name__ == "__main__":
    unittest.main()
