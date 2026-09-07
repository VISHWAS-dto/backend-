from fastapi import FastAPI

from app import models  # noqa: F401  (ensures models are registered on Base.metadata)
from app.database import Base, engine

# Create any missing tables on startup.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="catalyx-backend-py")


@app.get("/")
def health_check():
    return {"status": "ok", "message": "catalyx-backend-py is running"}
