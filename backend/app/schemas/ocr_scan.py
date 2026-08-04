from datetime import datetime
from pydantic import BaseModel


class OcrScanRead(BaseModel):
    id: int
    user_id: int
    store_id: int | None = None
    image_url: str
    raw_text: str | None = None
    parsed_data: dict | None = None
    status: str
    error_message: str | None = None
    created_at: datetime
    processed_at: datetime | None = None

    model_config = {"from_attributes": True}
