from typing import Dict

from file_processor.services.routing_service.routing_service import RoutingService
from file_processor.helpers.common.event_source_helper import EventSourceHelper
from file_processor.helpers.common.metadata_helper import MetadataHelper
from file_processor.model.file_metadata_dto import FileMetadataDTO
from shared_layer.model.response import Response

from shared_layer.aws.adapters.sqs_adapter import SQSAdapter
from shared_layer.logging.logger import Logger
from shared_layer.exceptions.exception_handler import ExceptionHandler, UnrecognizedFileTypeException
from shared_layer.repository.dynamo_repository import DynamoRepository

logger = Logger()

class RoutingServiceImpl(RoutingService):
    def __init__(self, dynamo_repository: DynamoRepository, sqs_adapter: SQSAdapter, ssm_client, config: dict):
        self.dynamo_repository = dynamo_repository
        self.sqs_adapter = sqs_adapter
        self.ssm_client = ssm_client
        self.config = config
        self.metadata_updater = MetadataHelper(self.dynamo_repository, config)

    def route_file(self, event: dict) -> Dict:
        file_metadata = None
        try:
            logger.info("📦 Starting file routing...")
            s3_event = EventSourceHelper.parse_sqs_event(event)
            file_metadata_dict = EventSourceHelper.extract_s3_metadata(s3_event)
            file_metadata = FileMetadataDTO(**file_metadata_dict)

            size_threshold = self.get_file_size_threshold()
            self.metadata_updater.store_metadata(file_metadata)

            if file_metadata.file_size > size_threshold:
                return self._process_large_file(file_metadata)
            else:
                return self._route_to_worker_queue(file_metadata)

        except Exception as e:
            return ExceptionHandler.handle("route_file", e, self.metadata_updater, file_metadata)

    def _process_large_file(self, file_metadata: FileMetadataDTO) -> Dict:
        try:
            logger.info(f"File size {file_metadata.file_size} exceeds threshold. Sending to AWS Batch.")
            result = self.submit_aws_batch_queue_job(file_metadata)
            self.metadata_updater.update_status(file_metadata, "BatchProcessing")
            return result
        except Exception as e:
            return ExceptionHandler.handle("_process_large_file", e, self.metadata_updater, file_metadata)

    def _route_to_worker_queue(self, file_metadata: FileMetadataDTO) -> Dict:
        try:
            data_type = file_metadata.data_type.lower()
            if data_type in self.config["queues"]:
                result = self.sqs_adapter.send_to_worker_queue(data_type, file_metadata.dict())
                self.metadata_updater.update_status(file_metadata, "Routed")
                return result
            else:
                raise UnrecognizedFileTypeException(file_metadata.s3_key)
        except Exception as e:
            return ExceptionHandler.handle("_route_to_worker_queue", e, self.metadata_updater, file_metadata)

    def submit_aws_batch_queue_job(self, file_metadata: FileMetadataDTO) -> Dict:
        return Response(
            status="Sent to AWS Batch",
            metadata=file_metadata.dict()
        ).dict()

    def get_file_size_threshold(self):
        try:
            response = self.ssm_client.get_parameter(Name=self.config["file_processing"]["size_threshold_param"])
            return int(response['Parameter']['Value'])
        except Exception as e:
            logger.warning(f"Failed to retrieve size threshold from SSM. Using default (10MB). Error: {str(e)}")
            return 10 * 1024 * 1024  # 10MB default
