import struct

from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

#TODO: Remove classes that dont need from here, only routing pydantic objects are used here

# ✅ Define S3 Object details
class S3Object(BaseModel):
    key: str = Field(..., description="S3 file path")
    size: int = Field(..., description="File size in bytes")
    eTag: str = Field(..., description="File ETag identifier")
    versionId: Optional[str] = Field(None, description="S3 object version ID")
    sequencer: str = Field(..., description="S3 event sequencer ID")


# ✅ Define S3 Bucket details
class S3Bucket(BaseModel):
    name: str = Field(..., description="S3 bucket name")
    arn: str = Field(..., description="S3 bucket ARN")


# ✅ Define S3 structure that combines bucket and object
class S3(BaseModel):
    bucket: S3Bucket = Field(..., description="S3 bucket information")
    object: S3Object = Field(..., description="S3 object information")


# ✅ Define S3 Event details
class S3Record(BaseModel):
    eventVersion: str = Field(..., description="S3 event version")
    eventSource: str = Field(..., description="Source of the event")
    awsRegion: str = Field(..., description="AWS region where the event occurred")
    eventTime: datetime = Field(..., description="Time when the event occurred")
    eventName: str = Field(..., description="Event type (e.g., ObjectCreated:Put)")
    s3: S3 = Field(..., description="S3 bucket and object details")


# ✅ Define S3 Event Wrapper
class S3Event(BaseModel):
    Records: List[S3Record]


# ✅ Define SQS Message Record
class SQSMessageRecord(BaseModel):
    body: str = Field(..., description="SQS message body containing S3 event JSON")
    messageId: Optional[str] = Field(None, description="SQS message ID")  # ✅ FIXED (Optional)
    receiptHandle: Optional[str] = Field(None, description="SQS receipt handle")
    attributes: Optional[dict] = Field(None, description="SQS message attributes")
    messageAttributes: Optional[dict] = Field(None, description="SQS message metadata")
    md5OfBody: Optional[str] = Field(None, description="MD5 hash of message body")
    eventSource: Optional[str] = Field(None, description="Source of the event")
    eventSourceARN: Optional[str] = Field(None, description="ARN of the event source")
    awsRegion: Optional[str] = Field(None, description="AWS region where the event occurred")


# ✅ Define Full SQS Event Structure
class SQSEvent(BaseModel):
    Records: List[SQSMessageRecord]