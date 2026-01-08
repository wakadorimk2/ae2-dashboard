import json
import time
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from . import settings
from .db import get_inventory_latest_primary_key_columns
from .routes import router

app = FastAPI(title=settings.APP_NAME)
app.include_router(router)
ops_ui_static_dir = Path(__file__).resolve().parent / "ops_ui" / "static"
app.mount("/dashboard/ui/static", StaticFiles(directory=ops_ui_static_dir), name="dashboard_ui")


@app.on_event("startup")
def _warn_on_inventory_latest_pk() -> None:
    try:
        columns = get_inventory_latest_primary_key_columns()
    except RuntimeError:
        return
    except Exception as exc:
        print(
            json.dumps(
                {
                    "type": "db_constraint_check_error",
                    "table": "inventory_latest",
                    "error": str(exc),
                    "ts": time.time(),
                },
                ensure_ascii=False,
            )
        )
        return

    expected_columns = ("world_id", "kind", "raw_name")
    if tuple(columns) != expected_columns:
        print(
            json.dumps(
                {
                    "type": "db_constraint_warning",
                    "table": "inventory_latest",
                    "pk_columns": columns,
                    "expected_pk_columns": list(expected_columns),
                    "message": "inventory_latest primary key should include world_id to avoid cross-world conflicts.",
                    "migration_hint": "migrations/20240928_add_world_id_inventory_prev.sql",
                    "ts": time.time(),
                },
                ensure_ascii=False,
            )
        )
