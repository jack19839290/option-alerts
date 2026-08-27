from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class AppConfig:
    spreadsheet_id: str
    max_monitor_rows: int = 1000

    @classmethod
    def from_env(cls) -> "AppConfig":
        spreadsheet_id = os.environ.get("SPREADSHEET_ID", "").strip()
        if not spreadsheet_id:
            raise RuntimeError("SPREADSHEET_ID environment variable is required")
        return cls(
            spreadsheet_id=spreadsheet_id,
            max_monitor_rows=int(os.environ.get("MAX_MONITOR_ROWS", "1000")),
        )

