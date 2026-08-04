from datetime import datetime

from pydantic import BaseModel, Field

from app.models.souk_price import SoukCategory, SoukStatus


class SoukPriceCreate(BaseModel):
    item_name: str = Field(..., min_length=2, max_length=120, description="Ex : Tomates, Sardines, Poulet beldi")
    category: SoukCategory
    price: float = Field(..., gt=0, le=100_000, description="Prix en MAD pour l'unité indiquée")
    unit: str = Field("kg", max_length=20, description="kg, botte, pièce, caisse…")
    city: str = Field(..., min_length=2, max_length=100)
    neighborhood: str | None = Field(None, max_length=120, description="Quartier ou nom du souk")
    latitude: float | None = None
    longitude: float | None = None
    photo_url: str | None = Field(None, max_length=500)
    note: str | None = Field(None, max_length=500)


class SoukPriceRead(BaseModel):
    id: int
    user_id: int
    contributor: str | None = None          # username du contributeur
    item_name: str
    category: SoukCategory
    unit: str
    price: float
    currency: str
    city: str
    neighborhood: str | None
    latitude: float | None
    longitude: float | None
    photo_url: str | None
    note: str | None
    status: SoukStatus
    moderation_reason: str | None
    upvotes: int
    downvotes: int
    my_vote: int | None = None              # +1 / -1 / None pour l'utilisateur courant
    created_at: datetime

    model_config = {"from_attributes": True}


class SoukVoteCreate(BaseModel):
    value: int = Field(..., description="+1 (fiable) ou -1 (douteux)")


class SoukMedianItem(BaseModel):
    item_name: str
    category: SoukCategory
    unit: str
    median_price: float
    min_price: float
    max_price: float
    sample_count: int
    city: str
    last_updated: datetime | None = None


class SoukCategoryInfo(BaseModel):
    value: SoukCategory
    label: str
    icon: str
    suggestions: list[str]
