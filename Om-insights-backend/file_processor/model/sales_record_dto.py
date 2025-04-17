# file_processor/model/sales_record_dto.py

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

from shared_layer.model.DynamoDBSerializable import DynamoDBSerializable


class SalesRecordDTO(DynamoDBSerializable):
    business_id: str
    upload_timestamp: str
    business_region: str
    subscription_type: str

    product: str = Field(..., alias="Product")
    customer_id: str = Field(..., alias="Customer ID")
    price: float = Field(..., alias="Price")
    payment_method: str = Field(..., alias="Payment Method")
    quantity: int = Field(..., alias="Quantity")
    total_sales: float = Field(..., alias="Total Sales")
    date: str = Field(..., alias="Date")

    status: str

    class Config:
        allow_population_by_field_name = True
