# shared_layer/model/response.py

from typing import Optional
from pydantic import BaseModel

class Response(BaseModel):
    status: str
    message: Optional[str] = None
    context: Optional[str] = None
    s3_key: Optional[str] = None
    metadata: Optional[dict] = None
