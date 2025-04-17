# file_processor/repository/dynamodb/abc_dynamo_repository.py

from abc import ABC, abstractmethod
from typing import List, Dict


#TODO: Bring this to shated_layer, since it can be used genrically from file_processor and context_engien etc..
# by just adding abstract emthod to reposity and call adapter, Also make sure all the classes we are calling here are absolutyl genetic from arguments to be
# pased and acallaed from any part of the project, for example ensure_table_exists FYI

class DynamoRepository(ABC):
    """
    Abstract base class defining core DynamoDB interactions.
    """

    @abstractmethod
    def ensure_table_exists(self, table_name: str) -> None:
        """Check or create the DynamoDB table if it doesn't exist."""
        pass

    @abstractmethod
    def put_item(self, table_name: str, item: Dict) -> None:
        """Insert a single item into DynamoDB."""
        pass

    @abstractmethod
    def batch_write_items(self, table_name: str, batch_items: List[Dict]) -> int:
        """
        Write multiple items to DynamoDB in batch.
        Returns number of failed items.
        """
        pass

    @abstractmethod
    def update_metadata_status(self, business_id: str, event_time: str, new_status: str, table_name: str):
        """Update the `status` attribute for an item in DynamoDB."""
        pass
