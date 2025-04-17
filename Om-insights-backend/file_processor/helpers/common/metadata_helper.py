# file_processor/helpers/common/metadata_helper.py

from shared_layer.logging.logger import Logger
from shared_layer.repository.dynamo_repository import DynamoRepository
from file_processor.model.file_metadata_dto import FileMetadataDTO

logger = Logger()
class MetadataHelper:
    def __init__(self, dynamo_client: DynamoRepository, config: dict):
        self.dynamo_client = dynamo_client
        self.config = config
        self.table_name = self.config["dynamodb"]["routing_metadata"]["table_name"]

    def store_metadata(self, metadata: FileMetadataDTO):
        try:
            item = metadata.to_dynamodb_item()
            self.dynamo_client.put_item(self.table_name, item)
            logger.info(f"✅ Metadata stored successfully for {metadata.file_name}")
        except Exception as e:
            logger.error(f"❌ Failed to store metadata in DynamoDB: {str(e)}", exc_info=True)

    def update_status(self, metadata: FileMetadataDTO, new_status: str):
        try:
            self.dynamo_client.update_metadata_status(
                business_id=metadata.company,
                event_time=metadata.event_time,
                new_status=new_status,
                table_name=self.table_name
            )
            logger.info(f"✅ Updated status to '{new_status}' for file: {metadata.file_name}")
        except Exception as e:
            logger.error(
                f"❌ Failed to update status to '{new_status}' for file: {metadata.file_name}: {str(e)}",
                exc_info=True
            )

    def update_status_with_ids(self, business_id: str, event_time: str, new_status: str):
        """Updates status of file metadata in DynamoDB."""
        try:

            self.dynamo_client.update_metadata_status(
                business_id=business_id,
                event_time=event_time,
                new_status=new_status,
                table_name=self.table_name
            )
            logger.info(f"✅ Updated routing-metadata status to '{new_status}' for {business_id} at {event_time}")

        except Exception as e:
            logger.error(f"❌ Failed to update routing-metadata status for {business_id}: {str(e)}", exc_info=True)
