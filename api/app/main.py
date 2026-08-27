from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    audit,
    auth,
    cart,
    catalog,
    chat,
    customer,
    health,
    intent,
    merchant,
    payment,
    webhooks,
)

app = FastAPI(title="AP2 Agentic Commerce API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,  # no cookies/session auth anywhere in this system
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(intent.router)
app.include_router(cart.router)
app.include_router(payment.router)
app.include_router(webhooks.router)
app.include_router(chat.router)
app.include_router(customer.router)
app.include_router(merchant.router)
app.include_router(audit.router)
