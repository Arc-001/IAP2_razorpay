from fastapi import FastAPI

from app.routers import cart, catalog, health, intent, payment

app = FastAPI(title="AP2 Agentic Commerce API")

app.include_router(health.router)
app.include_router(catalog.router)
app.include_router(intent.router)
app.include_router(cart.router)
app.include_router(payment.router)
