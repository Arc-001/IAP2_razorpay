import uuid

from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    merchant_id: uuid.UUID
    merchant_name: str
    name: str
    description: str | None
    category: str | None
    price: int  # paise
    currency: str
    stock: int | None
    tags: list[str]
