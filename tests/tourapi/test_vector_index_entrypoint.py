from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from src.storage.tourapi import chroma_config_from_env
from src.common.paths import TOURAPI_DATA_ROOT, VECTORSTORE_ROOT
from src.embeddings.tourapi import run_tourapi_vector_index


class TourApiVectorIndexTests(unittest.TestCase):
    @patch("src.embeddings.tourapi.run_vector_index_cli")
    def test_tourapi_defaults_are_isolated(self, mock_run) -> None:
        mock_run.return_value = 0

        result = run_tourapi_vector_index(["--dry-run"])

        self.assertEqual(result, 0)
        defaults, argv = mock_run.call_args.args
        self.assertEqual(defaults.collection_name, "jeju_places")
        self.assertEqual(
            defaults.input_path,
            TOURAPI_DATA_ROOT / "processed" / "jeju_place_rag_documents.json",
        )
        self.assertEqual(
            defaults.persist_directory,
            VECTORSTORE_ROOT,
        )
        self.assertEqual(argv, ["--dry-run"])

    def test_tourapi_chroma_config_owns_jeju_collection_default(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            config = chroma_config_from_env(project_root=Path("C:/project"))

        self.assertEqual(config.collection_name, "jeju_places")
        self.assertEqual(
            config.persist_directory,
            Path("C:/project") / "data" / "vectorstore",
        )


if __name__ == "__main__":
    unittest.main()
