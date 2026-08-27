from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import Flask, jsonify, request

from .config import AppConfig
from .service import RefreshService
from .sheets import SheetsRepository


logging.basicConfig(level=logging.INFO)
app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "option-alerts",
            "time": datetime.now(timezone.utc).isoformat(),
        }
    )


@app.post("/refresh")
def refresh():
    config = AppConfig.from_env()
    repository = SheetsRepository(config.spreadsheet_id, config.max_monitor_rows)
    force = bool((request.get_json(silent=True) or {}).get("force", False))
    result = RefreshService(repository).refresh(force=force)
    return jsonify(result)


@app.errorhandler(Exception)
def handle_error(error: Exception):
    app.logger.exception("Unhandled refresh error")
    return jsonify({"status": "error", "message": str(error)}), 500

