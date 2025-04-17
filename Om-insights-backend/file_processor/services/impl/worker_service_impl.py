from datetime import datetime

from file_processor.model.file_metadata_dto import ProcessingContext
from file_processor.model.workers_model import SQSMessage
from file_processor.data_formatters.data_formatter import DataFormatter
from file_processor.services.worker_service.worker_service import WorkerService

from shared_layer.aws.adapters.s3_adapter import S3Adapter
from shared_layer.repository.aoss_repository import AOSSRepository
from shared_layer.repository.dynamo_repository import DynamoRepository
from shared_layer.logging.logger import Logger

from file_processor.helpers.common.retry_helper import RetryHelper
from file_processor.helpers.worker.item_builder_helper import ItemBuilderHelper
from file_processor.helpers.worker.batch_writer_helper import BatchWriterHelper
from file_processor.helpers.common.metadata_helper import MetadataHelper

from shared_layer.exceptions.exception_handler import ExceptionHandler
from shared_layer.model.response import Response  # ✅ your DTO

logger = Logger()

class WorkerServiceImpl(WorkerService):
    """Service to process worker data from S3 with DLQ-friendly centralized exception handling."""

    def __init__(self, s3_adapter: S3Adapter, dynamo_repository: DynamoRepository, aoss_repository: AOSSRepository, config: dict):
        self.s3_adapter = s3_adapter
        self.repository = dynamo_repository
        self.aoss_repository = aoss_repository
        self.config = config
        self.metadata_helper = MetadataHelper(self.repository, config)
        self.BatchWriterHelper = BatchWriterHelper(self.repository)
        self.data_formatter = DataFormatter(s3_adapter= self.s3_adapter)
    def process_data(self, sqs_body: SQSMessage):
        """
        Processes worker data received from SQS.


        Returns:
            Dict: Processing result.
        """
        logger.info("🔹 **Processing Sales Data from SQS Message**")
        logger.info(sqs_body.dict())  # Log event for debugging
        try:
            context = ProcessingContext(**sqs_body.dict())

            logger.info(f"📂 Processing {context.data_type.upper()} data from: s3://{context.bucket_name}/{context.file_key} (Format: {context.file_format})")
            parsed_data = RetryHelper.retry(
                lambda: self.data_formatter.process_file(
                    context
                ),
                "DataFormatter.process_file",
                max_attempts=2
            )

            if not parsed_data:
                logger.warning("⚠️ No data returned after parsing.")
                return Response(
                    status="Skipped",
                    message ="No data found in file."
                ).dict()

            if context.file_format == "csv":
                # ✅ Structured → DynamoDB
                self.process_and_store_data(
                    structured_data=parsed_data,
                    context = context,
                    status=context.status
                )

            elif context.file_format == "txt":
                # ✅ Unstructured → OpenSearch (AOSS)
                logger.info("🔍 Indexing unstructured text data to AOSS...")
                # indexed_created = self.aoss_repository.index_unstructured_data(parsed_data)

            return Response(
                status="Success",
                message="Processed and stored records."
            ).dict()

        except Exception as e:
            return ExceptionHandler.handle("process_sales_data", e)

    def process_and_store_data(self, structured_data, context, status: str):
        table_name = f"{context.data_type}_table"
        self.repository.ensure_table_exists(table_name)

        #TODO: change sales_builder to take name dynamically
        total_records, failed_records = self.BatchWriterHelper.write_batches(
            structured_data=structured_data,
            table_name=table_name,
            record_to_item_fn=lambda record: ItemBuilderHelper.sales_builder(
                record, context, status
            )
        )

        final_status = "Processed" if failed_records == 0 else "Partially Processed"

        if isinstance(context.event_time, datetime):
            event_time = context.event_time.isoformat()
            self.metadata_helper.update_status_with_ids(context.business_id, event_time, final_status)

        logger.info(
            f"✅ Successfully stored {total_records - failed_records} records in {table_name}, {failed_records} failed."
        )