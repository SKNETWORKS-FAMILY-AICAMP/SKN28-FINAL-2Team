"""Rebuild the shared MySQL data and Chroma collections from tracked artifacts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tour_recommender.aihub.storage import TABLE_FILES, validate_input_files
from tour_recommender.embeddings.indexer import load_rag_dataset
from tour_recommender.storage.mysql_mapper import build_mysql_import_data
from tour_recommender.utils.config import load_env_file

from bootstrap_mysql import bootstrap as bootstrap_mysql_account


TOURAPI_RAW = PROJECT_ROOT / "data" / "raw" / "korea_tour_openapi_jeju_places.csv"
TOURAPI_RAG = PROJECT_ROOT / "data" / "processed" / "jeju_place_rag_documents.json"
AIHUB_DATA_ROOT = PROJECT_ROOT / "data" / "processed" / "aihub"
AIHUB_RAG = PROJECT_ROOT / "data" / "processed" / "aihub_rag_documents.json"
PLACE_RULES = PROJECT_ROOT / "configs" / "place_rules.json"
PRODUCTS = PROJECT_ROOT / "configs" / "virtual_travel_products.json"
PRODUCT_DETAILS = PROJECT_ROOT / "configs" / "virtual_travel_product_details.json"
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class CommandStep:
    name: str
    command: tuple[str, ...]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate tracked data, load TourAPI/AIHub/product data into MySQL, "
            "and build the TourAPI and AIHub Chroma collections."
        )
    )
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate all tracked inputs and print the plan without changing storage.",
    )
    parser.add_argument("--skip-mysql", action="store_true")
    parser.add_argument("--skip-chroma", action="store_true")
    parser.add_argument("--skip-products", action="store_true")
    parser.add_argument(
        "--bootstrap-mysql-account",
        action="store_true",
        help=(
            "Create the two databases and tour_app account from MYSQL_ADMIN_* in "
            ".env before loading data. Use this only for first-time setup."
        ),
    )
    parser.add_argument(
        "--keep-existing-aihub",
        action="store_true",
        help="Do not replace existing AIHub table rows; loading fails if rows exist.",
    )
    parser.add_argument(
        "--recreate-tour-database",
        action="store_true",
        help="Drop and recreate only MYSQL_DATABASE before the TourAPI load.",
    )
    parser.add_argument(
        "--recreate-chroma",
        action="store_true",
        help="Delete and rebuild the two managed Chroma collections.",
    )
    return parser


def validate_shared_inputs() -> dict[str, object]:
    required_paths = (
        TOURAPI_RAW,
        TOURAPI_RAG,
        AIHUB_RAG,
        PLACE_RULES,
        PRODUCTS,
        PRODUCT_DETAILS,
        PROJECT_ROOT / "sql" / "mysql_schema.sql",
        PROJECT_ROOT / "sql" / "aihub_schema.sql",
        PROJECT_ROOT / "sql" / "product_schema.sql",
    )
    required_paths += tuple(AIHUB_DATA_ROOT / path for path in TABLE_FILES.values())
    missing = [str(path.relative_to(PROJECT_ROOT)) for path in required_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Required shared-data files are missing:\n- " + "\n- ".join(missing)
        )

    tour_dataset = load_rag_dataset(TOURAPI_RAG)
    aihub_dataset = load_rag_dataset(AIHUB_RAG)
    aihub_counts = validate_input_files(AIHUB_DATA_ROOT)
    tour_import = build_mysql_import_data(
        TOURAPI_RAW,
        TOURAPI_RAG,
        rules_path=PLACE_RULES,
    )

    product_payload = json.loads(PRODUCTS.read_text(encoding="utf-8"))
    detail_payload = json.loads(PRODUCT_DETAILS.read_text(encoding="utf-8"))
    product_count = len(product_payload.get("products", []))
    detail_count = len(detail_payload.get("products", {}))
    if product_count != 30 or detail_count != 30:
        raise ValueError(
            "The shared virtual-product artifacts must each contain exactly 30 products"
        )

    return {
        "tourapi_rag_documents": len(tour_dataset.documents),
        "aihub_rag_documents": len(aihub_dataset.documents),
        "tourapi_mysql_places": len(tour_import.places),
        "aihub_mysql_rows": sum(aihub_counts.values()),
        "aihub_mysql_tables": len(aihub_counts),
        "virtual_products": product_count,
    }


def build_steps(
    args: argparse.Namespace,
    *,
    python_executable: str = sys.executable,
) -> list[CommandStep]:
    scripts = PROJECT_ROOT / "scripts"
    env_file = str(args.env_file.resolve())
    steps: list[CommandStep] = []

    if not args.skip_mysql:
        tour_command = [
            python_executable,
            str(scripts / "manage_storage.py"),
            "--env-file",
            env_file,
            "mysql-load",
            "--raw",
            str(TOURAPI_RAW),
            "--rag",
            str(TOURAPI_RAG),
            "--rules",
            str(PLACE_RULES),
        ]
        if args.recreate_tour_database:
            tour_command.append("--recreate-database")
        steps.append(CommandStep("TourAPI MySQL 적재", tuple(tour_command)))

        aihub_command = [
            python_executable,
            str(scripts / "load_aihub_to_mysql.py"),
            "--data-root",
            str(AIHUB_DATA_ROOT),
        ]
        if not args.keep_existing_aihub:
            aihub_command.append("--replace")
        steps.append(CommandStep("AIHub MySQL 적재", tuple(aihub_command)))

        if not args.skip_products:
            steps.append(
                CommandStep(
                    "가상 여행상품 MySQL 적재",
                    (python_executable, str(scripts / "load_virtual_products.py")),
                )
            )

    if not args.skip_chroma:
        command = [
            python_executable,
            str(PROJECT_ROOT / "backend" / "chromadbinit" / "init_chromadb.py"),
            "--env-file",
            env_file,
            "--batch-size",
            str(args.batch_size),
        ]
        if args.recreate_chroma:
            command.append("--recreate")
        steps.append(CommandStep("ChromaDB collections initialization", tuple(command)))

    return steps


def _validate_configuration(args: argparse.Namespace) -> None:
    load_env_file(args.env_file)
    missing: list[str] = []
    if not args.skip_mysql:
        missing.extend(
            name
            for name in (
                "MYSQL_USER",
                "MYSQL_PASSWORD",
                "MYSQL_DATABASE",
                "AIHUB_MYSQL_DATABASE",
            )
            if not os.environ.get(name)
        )
    if not args.skip_chroma and not os.environ.get("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if missing:
        raise ValueError(
            f"Missing configuration in {args.env_file}: {', '.join(sorted(set(missing)))}"
        )


def _bootstrap_mysql(args: argparse.Namespace) -> dict[str, str] | None:
    if not args.bootstrap_mysql_account:
        return None
    if args.skip_mysql:
        raise ValueError("--bootstrap-mysql-account cannot be used with --skip-mysql")
    result = bootstrap_mysql_account(args.env_file.resolve())
    # The bootstrap writes generated app credentials to .env. Clear inherited
    # values so load_env_file reads the newly written credentials.
    for name in (
        "MYSQL_ADMIN_USER",
        "MYSQL_ADMIN_PASSWORD",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "MYSQL_DATABASE",
        "AIHUB_MYSQL_DATABASE",
    ):
        os.environ.pop(name, None)
    return result


def run_steps(steps: Sequence[CommandStep]) -> None:
    total = len(steps)
    for index, step in enumerate(steps, start=1):
        print(f"\n[{index}/{total}] {step.name}", flush=True)
        completed = subprocess.run(step.command, cwd=PROJECT_ROOT, check=False)
        if completed.returncode:
            raise RuntimeError(
                f"Step failed with exit code {completed.returncode}: {step.name}"
            )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.batch_size <= 0:
        print("Error: --batch-size must be greater than zero", file=sys.stderr)
        return 2
    if args.skip_mysql and args.skip_chroma:
        print("Error: --skip-mysql and --skip-chroma cannot both be set", file=sys.stderr)
        return 2

    try:
        validation = validate_shared_inputs()
        steps = build_steps(args)
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "status": "dry-run-ok",
                        "validation": validation,
                        "planned_steps": [step.name for step in steps],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        bootstrap_result = _bootstrap_mysql(args)
        _validate_configuration(args)
        run_steps(steps)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Shared data initialization failed: {exc}", file=sys.stderr)
        return 1

    print(
        "\n"
        + json.dumps(
            {
                "status": "initialized",
                "validation": validation,
                "mysql_bootstrap": bootstrap_result,
                "completed_steps": [step.name for step in steps],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
