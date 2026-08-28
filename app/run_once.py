from __future__ import annotations

import json
import logging
import os

from .config import AppConfig
from .service import RefreshService
from .sheets import SheetsRepository


def run() -> dict[str, object]:
    config = AppConfig.from_env()
    repository = SheetsRepository(config.spreadsheet_id, config.max_monitor_rows)
    force = os.environ.get("FORCE_REFRESH", "").strip().lower() in {
        "true",
        "1",
        "yes",
    }
    return RefreshService(repository).refresh(force=force)


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
