from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str
    description: str | None = None
    category: str | None = None
    price: int = Field(ge=0, description="paise")
    stock: int | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    price: int | None = Field(default=None, ge=0)
    stock: int | None = None


class TagSuggestion(BaseModel):
    """AI-generated browse/search tags (CLAUDE.md §13 / SCRUM-44)."""

    tags: list[str] = Field(
        default_factory=list, description="3-6 short, lowercase, single-or-two-word tags"
    )
