from fastapi import FastAPI

from app.routers import audit, cart, catalog, chat, health, intent, payment, webhooks

app = FastAPI(title="AP2 Agentic Commerce API")

app.include_router(health.router)
app.include_router(catalog.router)
app.include_router(intent.router)
app.include_router(cart.router)
app.include_router(payment.router)
app.include_router(webhooks.router)
app.include_router(chat.router)
app.include_router(audit.router)
