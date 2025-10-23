"""Database bootstrap for voice agent and GEPA optimizer tables."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy.exc import OperationalError

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from voice_ai_keep_gepa.gepa_optimizer import storage as gepa_storage  # noqa: E402
from voice_ai_keep_gepa.voice_agent import storage as va_storage  # noqa: E402


def main() -> None:
    database_url = os.getenv("DATABASE_URL", "")

    if not database_url:
        raise SystemExit("DATABASE_URL is not configured. Please set it in .env.")

    create_engine_from_dsn = va_storage.create_engine_from_dsn
    engine = create_engine_from_dsn(database_url)
    if engine is None:
        raise SystemExit("Failed to create engine from DATABASE_URL.")

    try:
        va_storage.create_tables(engine)
        gepa_storage.create_tables(engine)
    except OperationalError as exc:
        raise SystemExit(f"Failed to connect to database: {exc}") from exc

    print("[bootstrap] Voice agent + GEPA tables ensured.")


if __name__ == "__main__":
    main()
