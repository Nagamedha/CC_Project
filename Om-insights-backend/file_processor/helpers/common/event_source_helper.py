# file_processor/helpers/common/event_source_helper.py

import os
import json
from pydantic import ValidationError
from datetime import datetime
from shared_layer.exceptions.error_handler import MetadataExtractionException
from file_processor.model.routing_model import SQSEvent, S3Event
from shared_layer.exceptions.error_handler import InvalidS3EventException
from shared_layer.logging.logger import Logger

logger = Logger()  # Module-level logger

class EventSourceHelper:
    @staticmethod
    def parse_sqs_event(event: dict) -> S3Event:
        """Parses and validates incoming SQS event to extract the embedded S3 event."""
        try:
            sqs_event = SQSEvent.parse_obj(event)
            s3_body_str = sqs_event.Records[0].body
            s3_event_data = json.loads(s3_body_str)

            return S3Event.parse_obj(s3_event_data)

        except ValidationError as e:
            logger.error(f"❌ Validation failed while parsing SQS or S3 event: {str(e)}", exc_info=True)
            raise InvalidS3EventException(
                f"Event validation failed: {str(e)}",
                error_code="S3_EVENT_VALIDATION_ERROR"
            )

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decoding failed while parsing S3 body: {str(e)}", exc_info=True)
            raise InvalidS3EventException(
                f"Failed to decode S3 event JSON: {str(e)}",
                error_code="S3_JSON_DECODE_ERROR"
            )

    def extract_s3_metadata(s3_event: S3Event) -> dict:
        """Extracts metadata from a validated S3Event."""
        try:
            record = s3_event.Records[0]
            bucket = record.s3.bucket.name
            s3_key = record.s3.object.key
            file_size = record.s3.object.size
            event_time = record.eventTime

            # Convert event_time to ISO 8601 string
            if isinstance(event_time, datetime):
                event_time = event_time.isoformat()

            parts = s3_key.split("/")
            if len(parts) < 5:
                raise MetadataExtractionException(
                    f"Invalid S3 path format: {s3_key}",
                    s3_key=s3_key,
                    error_code="S3_PATH_FORMAT_ERROR"
                )

            business_region, subscription, company, data_type, file_name = parts[0:5]
            _, file_extension = os.path.splitext(file_name)
            file_format = file_extension.lstrip('.').lower()

            # TODO: Change to Pydantic objects for better data validation
            return {
                "business_region": business_region,
                "subscription": subscription,
                "company": company,
                "data_type": data_type,
                "file_name": file_name,
                "s3_key": s3_key,
                "bucket": bucket,
                "file_size": file_size,
                "event_time": event_time,
                "file_format": file_format,
                "status": "Received"
            }

        except Exception as e:
            logger.error(f"❌ Failed to extract metadata: {str(e)}", exc_info=True)
            raise
