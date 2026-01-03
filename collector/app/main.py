from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from . import settings
from .routes import router

app = FastAPI(title=settings.APP_NAME)
app.include_router(router)
ops_ui_static_dir = Path(__file__).resolve().parent / "ops_ui" / "static"
app.mount("/dashboard/ui/static", StaticFiles(directory=ops_ui_static_dir), name="dashboard_ui")
