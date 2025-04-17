# file_processor/model/file_metadata_dto.py
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

from shared_layer.model.DynamoDBSerializable import DynamoDBSerializable


#TODO: change it to pydantic object

class FileMetadataDTO(DynamoDBSerializable):
    company: str = Field(..., alias="business_id")
    event_time: str = Field(..., alias="upload_timestamp") # ISO format
    data_type: str
    business_region: str
    subscription: str = Field(..., alias="subscription_type")
    file_name: str
    file_size: int
    file_format: str
    s3_key: str
    bucket: str
    status: str

    class Config:
        allow_population_by_field_name = True


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