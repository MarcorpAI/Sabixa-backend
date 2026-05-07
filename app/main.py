from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.db.init_db import init_db


settings = get_settings()
init_db()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI proof-of-skill backend for Sabixa customer support hiring MVP.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.api_prefix)