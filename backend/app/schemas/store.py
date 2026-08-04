from datetime import datetime
from pydantic import BaseModel, HttpUrl


class StoreBase(BaseModel):
    name: str
    slug: str
    address: str | None = None
    city: str | None = None
    region: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    phone: str | None = None
    website: str | None = None
    logo_url: str | None = None


class StoreCreate(StoreBase):
    pass


class StoreUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    phone: str | None = None
    website: str | None = None
    logo_url: str | None = None
    is_active: bool | None = None
    scraping_enabled: bool | None = None
    scraping_url: str | None = None


class StoreRead(StoreBase):
    id: int
    is_active: bool
    scraping_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}
