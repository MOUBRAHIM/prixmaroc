from datetime import datetime, date
from pydantic import BaseModel
from app.models.price import PriceSource


class PriceBase(BaseModel):
    product_id: int
    store_id: int
    price: float
    currency: str = "MAD"
    is_promo: bool = False
    promo_price: float | None = None
    promo_start: date | None = None
    promo_end: date | None = None
    source: PriceSource = PriceSource.MANUAL


class PriceCreate(PriceBase):
    pass


class PriceUpdate(BaseModel):
    price: float | None = None
    is_promo: bool | None = None
    promo_price: float | None = None
    promo_start: date | None = None
    promo_end: date | None = None


class PriceRead(PriceBase):
    id: int
    recorded_at: datetime

    model_config = {"from_attributes": True}


class PriceComparison(BaseModel):
    product_id: int
    product_name: str
    prices: list[dict]  # [{store, price, is_promo, ...}]
    lowest_price: float
    highest_price: float
    average_price: float
