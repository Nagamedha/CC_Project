# shared_layer.model.base.py

from pydantic import BaseModel

class DynamoDBSerializable(BaseModel):
    def to_dynamodb_item(self) -> dict:
        item = {}
        for field, value in self.dict(by_alias=True).items():
            if isinstance(value, str):
                item[field] = {"S": value}
            elif isinstance(value, (int, float)):
                item[field] = {"N": str(value)}
            elif isinstance(value, bool):
                item[field] = {"BOOL": value}
            elif value is None:
                item[field] = {"NULL": True}
            else:
                item[field] = {"S": str(value)}  # fallback
        return item
