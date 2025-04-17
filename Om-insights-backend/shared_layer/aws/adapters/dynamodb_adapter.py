# file_processor/repository/dynamodb_adapter.py

from botocore.exceptions import ClientError, BotoCoreError
from typing import Dict, List
from shared_layer.logging.logger import Logger

from shared_layer.repository.dynamo_repository import DynamoRepository

logger = Logger()

class DynamoDBAdapter(DynamoRepository):
    """
    Concrete adapter implementing DynamoDB repository methods.
    """

    def __init__(self, dynamodb_client, config):
        self.dynamodb = dynamodb_client
        self.config = config


    def ensure_table_exists(self, table_name: str) -> None:
        """
        Creates the table if it does not exist and waits until it's active.
        """
        try:
            self.dynamodb.describe_table(TableName=table_name)
            logger.info(f"✅ Table {table_name} already exists.")
            return
        except self.dynamodb.exceptions.ResourceNotFoundException:
            logger.info(f"🛠️ Table {table_name} does not exist. Creating...")

        # Create the table
        try:
            self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {"AttributeName": "business_id", "KeyType": "HASH"},
                    {"AttributeName": "upload_timestamp", "KeyType": "RANGE"}
                ],
                AttributeDefinitions=[
                    {"AttributeName": "business_id", "AttributeType": "S"},
                    {"AttributeName": "upload_timestamp", "AttributeType": "S"}
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            logger.info(f"⏳ Waiting for {table_name} to become active...")
            self.dynamodb.get_waiter("table_exists").wait(TableName=table_name)
            logger.info(f"✅ Table {table_name} is now active.")
        except ClientError as e:
            logger.error(f"❌ Failed to create table {table_name}: {e}")
            raise

    def put_item(self, table_name: str, item: Dict) -> None:
        """
        Inserts a single item into DynamoDB, ensuring the table exists first.
        """
        try:
            self.ensure_table_exists(table_name)
            self.dynamodb.put_item(TableName=table_name, Item=item)
            logger.info(f"✅ Successfully inserted item into {table_name}")
        except ClientError as e:
            logger.error(f"❌ Error inserting item into {table_name}: {e}")
            raise

    def batch_write_items(self, table_name: str, batch_items: List[Dict]) -> int:
        """
        Writes multiple items to DynamoDB in batches of 25 (DynamoDB's limit).
        Returns number of unprocessed/failed items.
        """
        if not batch_items:
            return 0  # Nothing to process

        failed_records = 0
        try:
            response = self.dynamodb.batch_write_item(RequestItems={table_name: batch_items})
            unprocessed_items = response.get("UnprocessedItems", {}).get(table_name, [])
            if unprocessed_items:
                logger.warning(f"⚠️ {len(unprocessed_items)} records not processed in batch write.")
                failed_records += len(unprocessed_items)
            return failed_records
        except (ClientError, BotoCoreError) as e:
            logger.error(f"❌ Batch write error: {str(e)}")
            return len(batch_items)  # If there's a total failure, assume all failed

    def update_metadata_status(self, business_id: str, event_time: str, new_status: str, table_name: str):
        """
        Updates the status of a file metadata entry in the DynamoDB table.
        """
        upload_timestamp = event_time  # Convert if needed outside
        try:
            key = {
                "business_id": {"S": business_id},
                "upload_timestamp": {"S": upload_timestamp}
            }

            response = self.dynamodb.update_item(
                TableName=table_name,
                Key=key,
                UpdateExpression="SET #s = :new_status",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":new_status": {"S": new_status}},
                ConditionExpression="attribute_exists(business_id) AND attribute_exists(upload_timestamp)",
                ReturnValues="UPDATED_NEW"
            )
            logger.info(f"✅ Updated status for {business_id} at {upload_timestamp} -> {new_status}")
            return response
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"⚠️ Record not found for update: {business_id} | {upload_timestamp}")
            else:
                logger.error(f"❌ Failed to update metadata status: {str(e)}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error updating metadata status: {str(e)}", exc_info=True)
            return None
