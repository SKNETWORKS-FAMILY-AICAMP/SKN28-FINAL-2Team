from __future__ import annotations

from src.embeddings.tourapi import run_tourapi_vector_index


def main() -> int:
    return run_tourapi_vector_index()


if __name__ == "__main__":
    raise SystemExit(main())
