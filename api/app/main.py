from fastapi import FastAPI

from app.routers import catalog, health

app = FastAPI(title="AP2 Agentic Commerce API")

app.include_router(health.router)
app.include_router(catalog.router)
