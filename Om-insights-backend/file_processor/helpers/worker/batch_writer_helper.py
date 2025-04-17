from shared_layer.repository.dynamo_repository import DynamoRepository


class BatchWriterHelper:
  #TODO: change class nams accordin to file names
    def __init__(self, dynamo_client: DynamoRepository):
      self.dynamo_client = dynamo_client

    def write_batches(self, structured_data, table_name, record_to_item_fn, batch_size=25):
        """
        Handles writing structured data to DynamoDB in batches.

        Args:
            structured_data (Generator): Yields batches of parsed records.
            table_name (str): DynamoDB table name.
            record_to_item_fn (Callable): Function to convert raw record → DynamoDB item.
            repository: Instance with .batch_write_items(table_name, items)
            batch_size (int): Max items per batch (DynamoDB limit is 25).

        Returns:
            (total_records, failed_records)
        """
        total_records = 0
        failed_records = 0

        self.dynamo_client.ensure_table_exists(table_name)
        for batch in structured_data:
            batch_items = []

            for record in batch:
                item = record_to_item_fn(record)
                batch_items.append({"PutRequest": {"Item": item}})

                if len(batch_items) >= batch_size:
                    failed_records += self.dynamo_client.batch_write_items(table_name, batch_items)
                    total_records += len(batch_items)
                    batch_items = []

            if batch_items:
                failed_records += self.dynamo_client.batch_write_items(table_name, batch_items)
                total_records += len(batch_items)

        return total_records, failed_records
