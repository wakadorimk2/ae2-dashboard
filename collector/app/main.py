from fastapi import FastAPI
from . import settings
from .routes import router

app = FastAPI(title=settings.APP_NAME)
app.include_router(router)
