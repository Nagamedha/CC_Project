# ✅ Define Pydantic Model for SQS Message
from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class SQSMessage(BaseModel):
    bucket: str = Field(..., title="S3 Bucket Name")
    s3_key: str = Field(..., title="S3 Object Key")
    file_size: int = Field(..., gt=0, title="File Size in Bytes")
    company: str = Field(..., title="Company Name")
    business_region: str = Field(..., title="Business Region")
    subscription: str = Field(..., title="Subscription Type")
    data_type: str = Field(..., title="Data Type (worker, inventory, etc.)")
    event_time: datetime = Field(..., title="Event Timestamp")
    file_format: str = Field(..., title="File Format (csv, txt, etc.)")
    status: str = Field(..., title="Processing Status")

class SQSRecords(BaseModel):
    Records: List[dict] = Field(..., title="List of SQS Records")
# ✅ Define Pydantic Model for SQS Message Validation


class ProcessingContext(BaseModel):
    bucket_name: str = Field(..., alias='bucket')
    file_key: str = Field(..., alias='s3_key')
    event_time: datetime
    file_format: str
    data_type: str
    business_id: str = Field(..., alias='company')
    business_region: str
    subscription_type: str = Field(..., alias='subscription')
    status: str

    class Config:
        allow_population_by_field_name = True