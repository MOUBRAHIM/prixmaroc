from datetime import datetime
from pydantic import BaseModel


class OcrScanRead(BaseModel):
    # Un scan d'invité n'est pas enregistré : il n'a donc ni identifiant ni
    # propriétaire. Les exiger faisait échouer la réponse après une lecture
    # pourtant réussie.
    id: int | None = None
    user_id: int | None = None
    store_id: int | None = None
    image_url: str
    raw_text: str | None = None
    parsed_data: dict | None = None
    status: str
    error_message: str | None = None
    created_at: datetime
    processed_at: datetime | None = None

    model_config = {"from_attributes": True}
