import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class RegisterRequest(BaseModel):
    email: str
    password: str
    role: Literal["customer", "merchant"]
    name: str
    merchant_name: str | None = None
    """Required when role == 'merchant' — validated in the service, not here,
    to keep the cross-field rule in one place with the transaction that acts
    on it."""


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    customer_id: uuid.UUID | None
    merchant_id: uuid.UUID | None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
